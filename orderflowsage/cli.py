"""Command-line interface."""

from __future__ import annotations

import argparse
import json
import sys
from importlib.resources import files

from .core import OrderFlowError, atomic_json, canonical_bytes, load_json, load_jsonl
from .engine import run_pipeline
from .report import prompt, summary, verify


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(prog="orderflowsage", description="Validate and measure limit-order-book snapshot replays")
    sub = result.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run")
    run.add_argument("config")
    run.add_argument("events")
    run.add_argument("output")
    check = sub.add_parser("verify")
    check.add_argument("config")
    check.add_argument("events")
    check.add_argument("report")
    show = sub.add_parser("summary")
    show.add_argument("report")
    export = sub.add_parser("prompt")
    export.add_argument("report")
    export.add_argument("output", nargs="?", default="-")
    sub.add_parser("demo")
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "run":
            report = run_pipeline(load_json(args.config), load_jsonl(args.events))
            atomic_json(args.output, report)
            print(f"wrote deterministic report: {args.output}")
        elif args.command == "verify":
            verify(load_json(args.config), load_jsonl(args.events), load_json(args.report))
            print("report verified")
        elif args.command == "summary":
            sys.stdout.write(summary(load_json(args.report)))
        elif args.command == "prompt":
            material = prompt(load_json(args.report))
            if args.output == "-":
                sys.stdout.buffer.write(canonical_bytes(material))
            else:
                atomic_json(args.output, material)
        elif args.command == "demo":
            package = files("orderflowsage.data")
            config = json.loads(package.joinpath("demo_config.json").read_text())
            events = [json.loads(line) for line in package.joinpath("demo.jsonl").read_text().splitlines()]
            sys.stdout.write(summary(run_pipeline(config, events)))
        return 0
    except (OrderFlowError, OSError, KeyError, TypeError) as exc:
        print(f"orderflowsage: {exc}", file=sys.stderr)
        return 2
