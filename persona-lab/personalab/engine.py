"""Run executor: individual fan-out, group discussion rounds, re-survey."""

from __future__ import annotations

import asyncio
import json
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

from anthropic import AsyncAnthropic, APIStatusError

from . import prompts
from .loader import load_material_blocks, load_personas
from .models import Persona, RunConfig, price_for


class CostMeter:
    def __init__(self) -> None:
        self.by_model: dict[str, dict[str, int]] = defaultdict(
            lambda: {"in": 0, "out": 0, "cache_read": 0, "cache_write": 0}
        )
        self.calls = 0

    def add(self, model: str, usage: Any) -> None:
        self.calls += 1
        b = self.by_model[model]
        b["in"] += getattr(usage, "input_tokens", 0) or 0
        b["out"] += getattr(usage, "output_tokens", 0) or 0
        b["cache_read"] += getattr(usage, "cache_read_input_tokens", 0) or 0
        b["cache_write"] += getattr(usage, "cache_creation_input_tokens", 0) or 0

    def report(self) -> dict[str, Any]:
        total = 0.0
        models = {}
        for model, b in self.by_model.items():
            p = price_for(model)
            cost = (
                b["in"] * p["in"]
                + b["out"] * p["out"]
                + b["cache_read"] * p["cache_read"]
                + b["cache_write"] * p["cache_write"]
            ) / 1_000_000
            models[model] = {**b, "est_cost_usd": round(cost, 4)}
            total += cost
        return {"calls": self.calls, "models": models, "est_total_usd": round(total, 4)}


class Runner:
    def __init__(self, cfg: RunConfig, out_dir: Path, dry_run: bool = False):
        self.cfg = cfg
        self.out = out_dir
        self.dry_run = dry_run
        self.client = None if dry_run else AsyncAnthropic()
        self.cost = CostMeter()
        self.personas: list[Persona] = load_personas(cfg.personas)
        self.material_blocks = load_material_blocks(cfg.materials)
        self.shared = prompts.shared_prefix_blocks(self.material_blocks, cfg.instructions)
        self.system = [
            {"type": "text", "text": prompts.SYSTEM_TEXT, "cache_control": {"type": "ephemeral"}}
        ]

    # ---------- low-level call ----------

    async def _call(self, model: str, user_blocks: list[dict], tool: dict | None) -> tuple[Any, Any]:
        """One message call with forced tool use and simple retry."""
        kwargs: dict[str, Any] = dict(
            model=model,
            max_tokens=self.cfg.max_output_tokens,
            temperature=self.cfg.temperature,
            system=self.system,
            messages=[{"role": "user", "content": user_blocks}],
        )
        if tool:
            kwargs["tools"] = [tool]
            kwargs["tool_choice"] = {"type": "tool", "name": tool["name"]}
        delay = 2.0
        for attempt in range(4):
            try:
                msg = await self.client.messages.create(**kwargs)
                self.cost.add(model, msg.usage)
                if tool:
                    for block in msg.content:
                        if block.type == "tool_use" and block.name == tool["name"]:
                            return block.input, msg
                    raise RuntimeError("model did not call the response tool")
                text = "".join(b.text for b in msg.content if b.type == "text")
                return text, msg
            except APIStatusError as e:
                if e.status_code in (429, 500, 502, 503, 529) and attempt < 3:
                    await asyncio.sleep(delay)
                    delay *= 2
                    continue
                raise

    # ---------- phases ----------

    async def individual_phase(self) -> dict[str, dict]:
        tool = prompts.response_tool(
            self.cfg.response_format.schema_, "Submit your reaction in the required format."
        )
        sem = asyncio.Semaphore(self.cfg.concurrency)
        results: dict[str, dict] = {}

        async def one(p: Persona) -> None:
            blocks = self.shared + [{"type": "text", "text": prompts.individual_task_text(p)}]
            async with sem:
                data, _ = await self._call(self.cfg.individual_model, blocks, tool)
            results[p.id] = data
            print(f"  ✓ {p.id} ({p.name})")

        # First call alone to warm the cache, then the rest in parallel.
        await one(self.personas[0])
        async with asyncio.TaskGroup() as tg:
            for p in self.personas[1:]:
                tg.create_task(one(p))
        return results

    def make_groups(self) -> dict[str, list[Persona]]:
        by_id = {p.id: p for p in self.personas}
        if self.cfg.groups.assignments:
            groups = {}
            for name, ids in self.cfg.groups.assignments.items():
                missing = [i for i in ids if i not in by_id]
                if missing:
                    raise ValueError(f"group {name}: unknown persona ids {missing}")
                groups[name] = [by_id[i] for i in ids]
            return groups
        size = max(2, self.cfg.groups.size)
        # Seeded shuffle before chunking so auto-groups mix categories and
        # departments instead of clustering by id order.
        import random

        pool = list(self.personas)
        random.Random(self.cfg.personas.seed).shuffle(pool)
        groups = {}
        for i in range(0, len(pool), size):
            chunk = pool[i : i + size]
            if len(chunk) == 1 and groups:  # fold a straggler into the last group
                groups[f"G{len(groups)}"].append(chunk[0])
            else:
                groups[f"G{len(groups) + 1}"] = chunk
        return groups

    async def group_phase(
        self, groups: dict[str, list[Persona]], initial: dict[str, dict]
    ) -> dict[str, dict]:
        gi = self.cfg.group_instructions or self.cfg.instructions
        tool = prompts.response_tool(prompts.GROUP_TURN_SCHEMA, "Take your discussion turn.")
        out: dict[str, dict] = {}

        async def run_group(name: str, members: list[Persona]) -> None:
            transcript: list[dict] = []
            roster = [m.name for m in members]
            for rnd in range(1, self.cfg.groups.rounds + 1):
                # Rotate speaking order each round to dilute first-speaker anchoring.
                order = members[(rnd - 1) % len(members):] + members[: (rnd - 1) % len(members)]
                for p in order:
                    text = prompts.group_turn_text(
                        p, name, roster, gi, self.cfg.groups.moderator_prompt,
                        transcript, json.dumps(initial[p.id], indent=1),
                        rnd, self.cfg.groups.rounds,
                    )
                    blocks = self.shared + [{"type": "text", "text": text}]
                    data, _ = await self._call(self.cfg.group_model, blocks, tool)
                    transcript.append(
                        {"round": rnd, "speaker": p.name, "speaker_id": p.id, **data}
                    )
                    print(f"  ✓ {name} r{rnd} — {p.name}")
            summary = None
            if self.cfg.groups.summarize:
                blocks = self.shared + [
                    {"type": "text", "text": prompts.group_summary_text(name, transcript)}
                ]
                summary, _ = await self._call(self.cfg.synthesis_model, blocks, None)
            out[name] = {"members": [p.id for p in members], "transcript": transcript,
                         "summary": summary}

        async with asyncio.TaskGroup() as tg:  # groups run concurrently; turns within a group are sequential
            for name, members in groups.items():
                tg.create_task(run_group(name, members))
        return out

    async def resurvey_phase(
        self, groups: dict[str, dict], initial: dict[str, dict]
    ) -> dict[str, dict]:
        tool = prompts.response_tool(
            self.cfg.response_format.schema_, "Submit your post-discussion answers."
        )
        sem = asyncio.Semaphore(self.cfg.concurrency)
        results: dict[str, dict] = {}
        by_id = {p.id: p for p in self.personas}

        async def one(pid: str, transcript: list[dict]) -> None:
            p = by_id[pid]
            text = prompts.resurvey_text(p, transcript, json.dumps(initial[pid], indent=1))
            blocks = self.shared + [{"type": "text", "text": text}]
            async with sem:
                data, _ = await self._call(self.cfg.individual_model, blocks, tool)
            results[pid] = data
            print(f"  ✓ resurvey {pid}")

        async with asyncio.TaskGroup() as tg:
            for g in groups.values():
                for pid in g["members"]:
                    tg.create_task(one(pid, g["transcript"]))
        return results

    # ---------- orchestration ----------

    async def execute(self) -> dict[str, Any]:
        started = time.time()
        self.out.mkdir(parents=True, exist_ok=True)
        run: dict[str, Any] = {
            "name": self.cfg.name,
            "config": json.loads(self.cfg.model_dump_json(by_alias=True)),
            "population": [
                {"id": p.id, "name": p.name, "role": p.role, "department": p.department,
                 "category": p.category}
                for p in self.personas
            ],
        }
        if self.dry_run:
            groups = self.make_groups() if self.cfg.groups.enabled else {}
            run["dry_run"] = {
                "personas": len(self.personas),
                "individual_calls": len(self.personas),
                "groups": {k: [p.id for p in v] for k, v in groups.items()},
                "group_calls": sum(len(v) for v in groups.values()) * self.cfg.groups.rounds
                + (len(groups) if self.cfg.groups.summarize else 0),
                "resurvey_calls": sum(len(v) for v in groups.values()) if self.cfg.resurvey else 0,
            }
            (self.out / "run.json").write_text(json.dumps(run, indent=2))
            return run

        print(f"Phase 1 — individual reactions ({len(self.personas)} personas)")
        initial = await self.individual_phase()
        run["individual"] = initial
        (self.out / "run.json").write_text(json.dumps(run, indent=2))  # checkpoint

        if self.cfg.groups.enabled:
            groups = self.make_groups()
            print(f"Phase 2 — group discussion ({len(groups)} groups, "
                  f"{self.cfg.groups.rounds} rounds)")
            run["groups"] = await self.group_phase(groups, initial)
            (self.out / "run.json").write_text(json.dumps(run, indent=2))
            if self.cfg.resurvey:
                print("Phase 3 — post-discussion re-survey")
                run["resurvey"] = await self.resurvey_phase(run["groups"], initial)

        run["cost"] = self.cost.report()
        run["elapsed_seconds"] = round(time.time() - started, 1)
        (self.out / "run.json").write_text(json.dumps(run, indent=2))
        return run
