"""
CLI runner for UniGlobe Data Ingestion Infrastructure.
Usage:
    python -m app.ingestion.cli seed-countries
    python -m app.ingestion.cli ingest-openalex --countries US,CA,HT,FR,GB,DE,IN,NG --per-country 5
"""

import argparse
import sys
from app.database import SessionLocal
from app.ingestion.countries_seed import seed_countries
from app.ingestion.base import IngestionPipeline
from app.ingestion.openalex_ror import OpenAlexRorConnector


def main():
    parser = argparse.ArgumentParser(description="UniGlobe Institutional Data Ingestion CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("seed-countries", help="Seed ISO 3166-1 countries & ministries")

    oa_parser = subparsers.add_parser("ingest-openalex", help="Ingest global education institutions from OpenAlex/ROR (CC0)")
    oa_parser.add_argument("--countries", type=str, default="US,CA,HT,FR,GB,DE,IN,NG,BR,MX,JP,AU", help="Comma-separated ISO-2 country codes")
    oa_parser.add_argument("--per-country", type=int, default=5, help="Number of top institutions per country")

    args = parser.parse_args()
    db = SessionLocal()
    try:
        if args.command == "seed-countries":
            count = seed_countries(db)
            print(f"[seed-countries] Created/updated {count} country records.")
        elif args.command == "ingest-openalex":
            seed_countries(db)
            codes = [c.strip().upper() for c in args.countries.split(",") if c.strip()]
            pipeline = IngestionPipeline(db)
            connector = OpenAlexRorConnector()
            run = pipeline.run_connector(connector, country_codes=codes, per_country=args.per_country)
            print(
                f"[ingest-openalex] Run {run.id} status={run.status} "
                f"fetched={run.records_fetched} created={run.records_created} "
                f"updated={run.records_updated} flagged={run.records_flagged}"
            )
    except Exception as exc:
        print(f"Ingestion failed: {exc}", file=sys.stderr)
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
