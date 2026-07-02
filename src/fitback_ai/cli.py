from __future__ import annotations

import argparse
import json
from pathlib import Path
from time import perf_counter

from .config import load_settings
from .mock_data import generate_records
from .neo4j_loader import load_graph, verify_graph


def main() -> None:
    parser = argparse.ArgumentParser(prog="fitback-ai", description="Mock GraphRAG ingestion utilities")
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate_parser = subparsers.add_parser("generate", help="Generate deterministic mock records")
    generate_parser.add_argument("--count", type=int, default=None)
    generate_parser.add_argument("--output", type=Path, default=None)

    load_parser = subparsers.add_parser("load", help="Generate and load mock records into Neo4j")
    load_parser.add_argument("--count", type=int, default=None)

    verify_parser = subparsers.add_parser("verify", help="Verify stored mock counts")
    verify_parser.add_argument("--batch-id", default=None)

    smoke_parser = subparsers.add_parser("smoke", help="Generate, load, and verify mock records")
    smoke_parser.add_argument("--count", type=int, default=None)

    args = parser.parse_args()
    settings = load_settings()

    if args.command == "generate":
        count = args.count or settings.mock_record_count
        payload = generate_records(count, settings.mock_store_id, settings.mock_batch_id)
        text = json.dumps(payload, ensure_ascii=False, indent=2)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(text, encoding="utf-8")
            print(json.dumps({"output": str(args.output), "recordCount": count}, ensure_ascii=False))
        else:
            print(text)
        return

    if args.command == "load":
        count = args.count or settings.mock_record_count
        payload = generate_records(count, settings.mock_store_id, settings.mock_batch_id)
        result = load_graph(settings, payload)
        print_result("load", result.elapsed_ms, result.counts)
        return

    if args.command == "verify":
        started = perf_counter()
        counts = verify_graph(settings, args.batch_id or settings.mock_batch_id)
        print_result("verify", (perf_counter() - started) * 1000, counts)
        return

    if args.command == "smoke":
        count = args.count or settings.mock_record_count
        payload = generate_records(count, settings.mock_store_id, settings.mock_batch_id)
        load_result = load_graph(settings, payload)
        verify_started = perf_counter()
        counts = verify_graph(settings, settings.mock_batch_id)
        print(
            json.dumps(
                {
                    "command": "smoke",
                    "requestedRecords": count,
                    "loadElapsedMs": round(load_result.elapsed_ms, 2),
                    "verifyElapsedMs": round((perf_counter() - verify_started) * 1000, 2),
                    "counts": counts,
                    "passed": counts.get("Customer") == count
                    and counts.get("Consultation") == count
                    and counts.get("EventTarget") == count,
                },
                ensure_ascii=False,
                indent=2,
            )
        )


def print_result(command: str, elapsed_ms: float, counts: dict[str, int]) -> None:
    print(
        json.dumps(
            {
                "command": command,
                "elapsedMs": round(elapsed_ms, 2),
                "counts": counts,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
