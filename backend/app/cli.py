"""CLI entrypoint for Cloud Run Jobs, local batch execution, and FastAPI server."""

from __future__ import annotations

import argparse
import json
from typing import Optional, Sequence

import uvicorn

from .config import Settings
from .genai_provider import GenAIMediaProvider, execute_jobs_file
from .pipeline import CampaignRequest, ProductionPipeline
from .project_store import ProjectStore
from .retention import prune_expired_data
from .storage import build_storage
from .store import JobStore


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Production google-genai shortform ad CLI")
    sub = p.add_subparsers(dest="cmd", required=True)

    rj = sub.add_parser("run-jobs", help="Execute a 05_jobs.json manifest via google-genai")
    rj.add_argument("--jobs", required=True, help="Path to 05_jobs.json")
    rj.add_argument("--project", required=True, help="Campaign working directory")
    rj.add_argument("--source", default=None, help="Optional source MP4 for missing anchor frames")
    rj.add_argument("--concurrency", type=int, default=None)
    rj.add_argument("--max-credits", type=int, default=None)
    rj.add_argument("--only-units", default=None, help="Comma-separated unit IDs to retry")
    rj.add_argument("--no-skip-existing", action="store_true")

    rc = sub.add_parser("run-campaign", help="Run full analyze -> lint -> generate -> assemble pipeline")
    rc.add_argument("--campaign-id", required=True)
    rc.add_argument("--source", default=None)
    rc.add_argument("--facts", required=True, help="Path to 00_product_facts.md")
    rc.add_argument("--spec", default=None, help="Optional pre-authored 05_ad_spec.json")
    rc.add_argument("--thumbs-spec", default=None)
    rc.add_argument("--vo-manifest", default=None)
    rc.add_argument("--res", choices=["360p", "720p"], default="720p")
    rc.add_argument("--track", default="A_bgrade_reversal")
    rc.add_argument("--normalize-cfr", action="store_true")
    rc.add_argument("--clean-copy", action="store_true")
    rc.add_argument("--dry-run", action="store_true")
    rc.add_argument("--max-credits", type=int, default=None)

    sv = sub.add_parser("serve", help="Launch FastAPI production HTTP server")
    sv.add_argument("--host", default="0.0.0.0")
    sv.add_argument("--port", type=int, default=8080)

    sub.add_parser("prune-expired", help="Delete 7-day expired projects, storage objects, and caches")
    return p


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = build_parser().parse_args(argv)
    settings = Settings()

    if args.cmd == "run-jobs":
        provider = GenAIMediaProvider(settings)
        only = [u.strip() for u in args.only_units.split(",") if u.strip()] if args.only_units else None
        report = execute_jobs_file(
            args.jobs,
            args.project,
            provider,
            source_video=args.source,
            concurrency=args.concurrency or settings.concurrency,
            max_credits=args.max_credits if args.max_credits is not None else settings.max_video_credits_per_job,
            skip_existing=not args.no_skip_existing,
            only_unit_ids=only,
        )
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return

    if args.cmd == "run-campaign":
        store = JobStore(settings.db_path)
        pipeline = ProductionPipeline(settings, store)
        req = CampaignRequest(
            campaign_id=args.campaign_id,
            source_video=args.source,
            facts_path=args.facts,
            spec_path=args.spec,
            thumbs_spec_path=args.thumbs_spec,
            vo_manifest_path=args.vo_manifest,
            track_archetype=args.track,
            resolution=args.res,
            normalize_cfr=args.normalize_cfr,
            clean_copy=args.clean_copy,
            dry_run=args.dry_run,
            max_credits=args.max_credits,
        )
        res = pipeline.run_campaign(req)
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return

    if args.cmd == "serve":
        uvicorn.run("app.server:app", host=args.host, port=args.port)
        return

    if args.cmd == "prune-expired":
        proj_store = ProjectStore(settings.db_path)
        job_store = JobStore(settings.db_path)
        storage = build_storage(settings)
        summary = prune_expired_data(proj_store, job_store, storage, settings)
        print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
