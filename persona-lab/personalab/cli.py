"""Command-line interface for the Phase 0 spike.

Usage:
    python -m personalab validate personas/umw
    python -m personalab run examples/run-umw-demo.yaml [--dry-run] [--out DIR]
    python -m personalab analyze runs/<dir>/run.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from collections import Counter
from pathlib import Path

from .analysis import write_report
from .engine import Runner
from .loader import load_personas
from .models import PersonasConfig, RunConfig


def cmd_validate(args: argparse.Namespace) -> int:
    personas = load_personas(PersonasConfig(path=args.path))
    cats = Counter(p.category for p in personas)
    depts = Counter(p.department for p in personas)
    print(f"Loaded {len(personas)} personas from {args.path}")
    print(f"  by category:   {dict(cats)}")
    print("  by department:")
    for d, n in depts.most_common():
        print(f"    {n:2d}  {d}")
    if args.card:
        match = [p for p in personas if p.id == args.card]
        if not match:
            print(f"no persona with id '{args.card}'", file=sys.stderr)
            return 1
        print("\n" + match[0].card())
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    cfg = RunConfig.load(args.config)
    if not args.dry_run and not os.environ.get("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY is not set (use --dry-run to test without calling the API)",
              file=sys.stderr)
        return 1
    out = Path(args.out) if args.out else Path("runs") / time.strftime("%Y%m%d-%H%M%S")
    runner = Runner(cfg, out, dry_run=args.dry_run)
    run = asyncio.run(runner.execute())
    if args.dry_run:
        print(json.dumps(run["dry_run"], indent=2))
        print(f"\nDry run OK — wrote {out / 'run.json'}")
    else:
        print(f"\nRun complete — {out / 'run.json'}")
        print(json.dumps(run.get("cost", {}), indent=2))
        report = write_report(out / "run.json")
        print(f"Analysis — {report}")
    return 0


def cmd_analyze(args: argparse.Namespace) -> int:
    report = write_report(Path(args.run_json))
    print(f"Wrote {report}")
    print(report.read_text())
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="personalab", description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    v = sub.add_parser("validate", help="load and summarize a persona file/directory")
    v.add_argument("path")
    v.add_argument("--card", help="print the rendered card for this persona id")
    v.set_defaults(fn=cmd_validate)

    r = sub.add_parser("run", help="execute a run config")
    r.add_argument("config")
    r.add_argument("--dry-run", action="store_true",
                   help="validate config, personas, and materials; plan calls; no API usage")
    r.add_argument("--out", help="output directory (default runs/<timestamp>)")
    r.set_defaults(fn=cmd_run)

    a = sub.add_parser("analyze", help="(re)compute analysis for a finished run")
    a.add_argument("run_json")
    a.set_defaults(fn=cmd_analyze)

    args = parser.parse_args(argv)
    return args.fn(args)
