"""Basic deterministic analysis over a completed run.

Aggregates structured response fields at the individual, group, and
population level; measures pre/post-discussion shift when a re-survey ran.
Everything here is plain statistics — no LLM calls — so it is exactly
reproducible from run.json.
"""

from __future__ import annotations

import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def _numeric_fields(responses: dict[str, dict]) -> dict[str, dict[str, float]]:
    values: dict[str, list[float]] = defaultdict(list)
    for r in responses.values():
        for k, v in r.items():
            if isinstance(v, bool):
                values[k].append(1.0 if v else 0.0)
            elif isinstance(v, (int, float)):
                values[k].append(float(v))
    out = {}
    for k, vals in values.items():
        out[k] = {
            "n": len(vals),
            "mean": round(statistics.fmean(vals), 3),
            "stdev": round(statistics.stdev(vals), 3) if len(vals) > 1 else 0.0,
            "min": min(vals),
            "max": max(vals),
        }
    return out


def _categorical_fields(responses: dict[str, dict]) -> dict[str, dict[str, int]]:
    counts: dict[str, Counter] = defaultdict(Counter)
    for r in responses.values():
        for k, v in r.items():
            if isinstance(v, str) and len(v) <= 40:
                counts[k][v] += 1
    # only keep fields that look categorical (few distinct values)
    return {k: dict(c.most_common()) for k, c in counts.items() if 1 < len(c) <= 8}


def analyze(run: dict[str, Any]) -> dict[str, Any]:
    population = {p["id"]: p for p in run["population"]}
    individual: dict[str, dict] = run.get("individual", {})
    report: dict[str, Any] = {"n_personas": len(population)}

    report["population"] = {
        "numeric": _numeric_fields(individual),
        "categorical": _categorical_fields(individual),
    }

    # By category (faculty vs staff) and by department
    for dim in ("category", "department"):
        buckets: dict[str, dict[str, dict]] = defaultdict(dict)
        for pid, resp in individual.items():
            buckets[population[pid][dim]][pid] = resp
        report[f"by_{dim}"] = {
            name: {"n": len(resps), "numeric": _numeric_fields(resps)}
            for name, resps in sorted(buckets.items())
        }

    # Group-level stats + discussion dynamics
    groups = run.get("groups") or {}
    if groups:
        gstats = {}
        for name, g in groups.items():
            resps = {pid: individual[pid] for pid in g["members"] if pid in individual}
            shifts = Counter(t.get("position_shift", "none") for t in g["transcript"])
            disagreements = sum(len(t.get("disagreements", [])) for t in g["transcript"])
            gstats[name] = {
                "members": g["members"],
                "numeric": _numeric_fields(resps),
                "turns": len(g["transcript"]),
                "position_shifts": dict(shifts),
                "explicit_disagreements": disagreements,
            }
        report["by_group"] = gstats
        # Variance-collapse warning: within-group stdev far below population stdev
        pop_num = report["population"]["numeric"]
        warnings = []
        for field, pstats in pop_num.items():
            if pstats["stdev"] == 0:
                warnings.append(f"population stdev for '{field}' is 0 — responses may be homogenized")
        report["warnings"] = warnings

    # Pre/post shift
    resurvey: dict[str, dict] = run.get("resurvey") or {}
    if resurvey:
        shifts = {}
        for pid, post in resurvey.items():
            pre = individual.get(pid, {})
            deltas = {}
            for k, v in post.items():
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    if isinstance(pre.get(k), (int, float)):
                        deltas[k] = round(float(v) - float(pre[k]), 3)
            shifts[pid] = deltas
        moved = [pid for pid, d in shifts.items() if any(abs(x) >= 1 for x in d.values())]
        report["shift"] = {
            "per_persona": shifts,
            "moved_at_least_one_point": moved,
            "n_moved": len(moved),
        }

    report["cost"] = run.get("cost")
    return report


def write_report(run_path: Path) -> Path:
    run = json.loads(run_path.read_text())
    report = analyze(run)
    out = run_path.parent / "analysis.json"
    out.write_text(json.dumps(report, indent=2))

    md = [f"# Analysis — {run.get('name')}", ""]
    md.append(f"Personas: {report['n_personas']}")
    if report.get("cost"):
        md.append(f"Estimated cost: ${report['cost'].get('est_total_usd')} "
                  f"({report['cost'].get('calls')} calls)")
    md.append("\n## Population — numeric fields\n")
    md.append("| field | n | mean | stdev | min | max |")
    md.append("|---|---|---|---|---|---|")
    for f, s in report["population"]["numeric"].items():
        md.append(f"| {f} | {s['n']} | {s['mean']} | {s['stdev']} | {s['min']} | {s['max']} |")
    for f, counts in report["population"]["categorical"].items():
        md.append(f"\n**{f}:** " + ", ".join(f"{k} ({v})" for k, v in counts.items()))
    if "by_category" in report:
        md.append("\n## Faculty vs staff (numeric means)\n")
        for cat, s in report["by_category"].items():
            means = {f: v["mean"] for f, v in s["numeric"].items()}
            md.append(f"- **{cat}** (n={s['n']}): {means}")
    if "by_group" in report:
        md.append("\n## Groups\n")
        for name, g in report["by_group"].items():
            md.append(f"- **{name}** ({len(g['members'])} members, {g['turns']} turns): "
                      f"shifts {g['position_shifts']}, "
                      f"explicit disagreements {g['explicit_disagreements']}")
    if "shift" in report:
        md.append(f"\n## Pre/post discussion shift\n")
        md.append(f"{report['shift']['n_moved']} personas moved ≥1 point on at least one "
                  f"numeric field: {', '.join(report['shift']['moved_at_least_one_point']) or '—'}")
    for w in report.get("warnings", []):
        md.append(f"\n⚠️ {w}")
    md_path = run_path.parent / "analysis.md"
    md_path.write_text("\n".join(md) + "\n")
    return md_path
