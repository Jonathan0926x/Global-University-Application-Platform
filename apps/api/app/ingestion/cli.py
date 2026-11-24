"""
CLI runner for UniGlobe Data Ingestion Infrastructure.
Usage:
    python -m app.ingestion.cli seed-countries
    python -m app.ingestion.cli ingest-openalex --countries US,CA,HT,FR,GB,DE,IN,NG --per-country 5
    python -m app.ingestion.cli ingest-ipeds
    python -m app.ingestion.cli ingest-scorecard
"""

import argparse
import json
import sys
from app.database import SessionLocal
from app.ingestion.countries_seed import seed_countries
from app.ingestion.base import IngestionPipeline
from app.ingestion.openalex_ror import OpenAlexRorConnector
from app.ingestion.ipeds import IPEDSConnector
from app.ingestion.scorecard import CollegeScorecardConnector


def _print_run_summary(tag: str, run):
    print(
        f"[{tag}] Run {run.id} status={run.status} "
        f"fetched={run.records_fetched} created={run.records_created} "
        f"updated={run.records_updated} flagged={run.records_flagged}"
    )
    vr = (run.metadata_json or {}).get("validation_report")
    if vr:
        print(f"[{tag}] Validation Report: {json.dumps(vr)}")


def main():
    parser = argparse.ArgumentParser(description="UniGlobe Institutional Data Ingestion CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("seed-countries", help="Seed ISO 3166-1 countries & ministries")

    oa_parser = subparsers.add_parser("ingest-openalex", help="Ingest global education institutions from OpenAlex/ROR (CC0)")
    oa_parser.add_argument("--countries", type=str, default="US,CA,HT,FR,GB,DE,IN,NG,BR,MX,JP,AU")
    oa_parser.add_argument("--per-country", type=int, default=5)

    ipeds_parser = subparsers.add_parser("ingest-ipeds", help="Ingest US Title IV institutions from official NCES IPEDS bulk CSVs")
    ipeds_parser.add_argument("--states", type=str, default=None, help="Optional comma-separated state codes e.g. CA,NY")
    ipeds_parser.add_argument("--limit", type=int, default=None, help="Optional row limit for testing")

    sc_parser = subparsers.add_parser("ingest-scorecard", help="Enrich US institutions from Dept. of Education College Scorecard")
    sc_parser.add_argument("--states", type=str, default=None, help="Optional comma-separated state codes")
    sc_parser.add_argument("--limit", type=int, default=None)
    sc_parser.add_argument("--mode", type=str, default="bulk", choices=["bulk", "api"])

    args = parser.parse_args()
    db = SessionLocal()
    try:
        seed_countries(db)
        pipeline = IngestionPipeline(db)

        if args.command == "seed-countries":
            print("[seed-countries] Country catalog verified.")
        elif args.command == "ingest-openalex":
            codes = [c.strip().upper() for c in args.countries.split(",") if c.strip()]
            run = pipeline.run_connector(OpenAlexRorConnector(), country_codes=codes, per_country=args.per_country)
            _print_run_summary("ingest-openalex", run)
        elif args.command == "ingest-ipeds":
            states = [s.strip().upper() for s in args.states.split(",") if s.strip()] if args.states else None
            run = pipeline.run_connector(IPEDSConnector(), states=states, limit=args.limit)
            _print_run_summary("ingest-ipeds", run)
        elif args.command == "ingest-scorecard":
            states = [s.strip().upper() for s in args.states.split(",") if s.strip()] if args.states else None
            run = pipeline.run_connector(CollegeScorecardConnector(), states=states, limit=args.limit, mode=args.mode)
            _print_run_summary("ingest-scorecard", run)
    except Exception as exc:
        print(f"Ingestion failed: {exc}", file=sys.stderr)
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
