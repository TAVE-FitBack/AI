from __future__ import annotations

import argparse
import json
from pathlib import Path
from time import perf_counter

from .config import load_settings
from .neo4j_loader import initialize_graph, load_graph, verify_graph


def main() -> None:
    parser = argparse.ArgumentParser(prog="fitback-ai", description="Fitback AI graph operations")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("init", help="Initialize Neo4j schema and ontology without loading business data")

    load_parser = subparsers.add_parser("load", help="Load production graph payload JSON into Neo4j")
    load_parser.add_argument("--input", type=Path, default=None, help="JSON payload path. Omit to initialize an empty graph.")

    subparsers.add_parser("verify", help="Verify production graph counts")

    args = parser.parse_args()
    settings = load_settings()

    if args.command == "init":
        result = initialize_graph(settings)
        print_result("init", result.elapsed_ms, result.counts, record_count=result.record_count)
        return

    if args.command == "load":
        payload = _read_payload(args.input)
        result = load_graph(settings, payload)
        print_result("load", result.elapsed_ms, result.counts, record_count=result.record_count)
        return

    if args.command == "verify":
        started = perf_counter()
        counts = verify_graph(settings)
        print_result("verify", (perf_counter() - started) * 1000, counts)
        return


def _read_payload(path: Path | None) -> dict:
    if path is None:
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def print_result(command: str, elapsed_ms: float, counts: dict[str, int], record_count: int | None = None) -> None:
    body = {
        "command": command,
        "elapsedMs": round(elapsed_ms, 2),
        "counts": counts,
    }
    if record_count is not None:
        body["recordCount"] = record_count
    print(
        json.dumps(
            body,
            ensure_ascii=False,
            indent=2,
        )
    )
