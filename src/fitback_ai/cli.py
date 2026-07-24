from __future__ import annotations

import argparse
import json
from pathlib import Path
from time import perf_counter

from .config import load_rds_sync_settings, load_settings
from .neo4j_loader import initialize_graph, load_graph, verify_graph, verify_graph_quality
from .rds_sync import sync_initial, verify_sync


def main() -> None:
    parser = argparse.ArgumentParser(prog="fitback-ai", description="Fitback AI graph operations")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("init", help="Initialize Neo4j schema and ontology without loading business data")

    load_parser = subparsers.add_parser("load", help="Load production graph payload JSON into Neo4j")
    load_parser.add_argument("--input", type=Path, default=None, help="JSON payload path. Omit to initialize an empty graph.")

    subparsers.add_parser("verify", help="Verify production graph counts")

    rds_sync_parser = subparsers.add_parser("rds-sync", help="Backfill RDS consultation analysis data into AuraDB")
    rds_sync_parser.add_argument("--dry-run", action="store_true", help="Read RDS and report expected work without AuraDB writes")
    rds_sync_parser.add_argument("--limit", type=int, default=None, help="Optional maximum consultation count")
    rds_sync_parser.add_argument("--batch-size", type=int, default=None, help="Override RDS_SYNC_BATCH_SIZE")

    subparsers.add_parser("rds-verify", help="Compare RDS table counts with AuraDB label counts")

    args = parser.parse_args()

    if args.command == "init":
        settings = load_settings()
        result = initialize_graph(settings)
        print_result("init", result.elapsed_ms, result.counts, record_count=result.record_count)
        return

    if args.command == "load":
        settings = load_settings()
        payload = _read_payload(args.input)
        result = load_graph(settings, payload)
        print_result("load", result.elapsed_ms, result.counts, record_count=result.record_count)
        return

    if args.command == "verify":
        settings = load_settings()
        started = perf_counter()
        counts = verify_graph(settings)
        print_result("verify", (perf_counter() - started) * 1000, counts)
        return

    if args.command == "rds-sync":
        started = perf_counter()
        rds_settings = load_rds_sync_settings()
        if args.batch_size is not None:
            rds_settings = rds_settings.__class__(
                database_url=rds_settings.database_url,
                username=rds_settings.username,
                password=rds_settings.password,
                batch_size=args.batch_size,
                include_pii=rds_settings.include_pii,
            )
        result = sync_initial(rds_settings, dry_run=args.dry_run, limit=args.limit)
        print_json(
            {
                "command": "rds-sync",
                "dryRun": result.dry_run,
                "elapsedMs": round((perf_counter() - started) * 1000, 2),
                "scanned": result.scanned,
                "succeeded": result.succeeded,
                "failed": result.failed,
                "rdsCounts": result.rds_counts,
                "auraCounts": result.aura_counts,
                "errors": result.errors[:20],
            }
        )
        return

    if args.command == "rds-verify":
        started = perf_counter()
        rds_settings = load_rds_sync_settings()
        neo4j_settings = load_settings()
        result = verify_sync(
            rds_settings,
            graph_counts=lambda: verify_graph_quality(neo4j_settings),
        )
        print_json(
            {
                "command": "rds-verify",
                "elapsedMs": round((perf_counter() - started) * 1000, 2),
                "rdsCounts": result.rds_counts,
                "auraCounts": result.aura_counts,
                "comparisons": result.comparisons,
            }
        )
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
    print_json(body)


def print_json(body: dict) -> None:
    print(json.dumps(body, ensure_ascii=False, indent=2, default=str))
