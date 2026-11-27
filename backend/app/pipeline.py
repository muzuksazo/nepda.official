"""End-to-end production campaign pipeline orchestrator."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

from .config import Settings
from .genai_provider import GenAIMediaProvider, execute_jobs_file
from .storage import StorageBackend, build_storage
from .store import JobStore


class LintFailedError(RuntimeError):
    """Raised when Gate A lint blocks a campaign before paid generation."""


@dataclass
class CampaignRequest:
    campaign_id: str
    source_video: Optional[str] = None
    source_object_key: Optional[str] = None
    facts_path: Optional[str] = None
    facts_markdown: Optional[str] = None
    spec_path: Optional[str] = None
    spec_data: Optional[Dict[str, Any]] = None
    compare_abc_specs: Optional[List[str]] = None
    thumbs_spec_path: Optional[str] = None
    vo_manifest_path: Optional[str] = None
    track_archetype: str = "A_bgrade_reversal"
    resolution: str = "720p"
    normalize_cfr: bool = False
    clean_copy: bool = False
    dry_run: bool = False
    max_credits: Optional[int] = None
    concurrency: Optional[int] = None
    extra_past_specs: List[str] = field(default_factory=list)
    skip_cross_campaign_reskin: bool = False


def _run_script(
    scripts_dir: Path,
    script_name: str,
    args: Sequence[str],
    *,
    cwd: Optional[Path] = None,
) -> subprocess.CompletedProcess[str]:
    script_path = scripts_dir / script_name
    if not script_path.exists():
        raise FileNotFoundError(f"Missing core script: {script_path}")
    cmd = [sys.executable, str(script_path), *args]
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
    )


class ProductionPipeline:
    """State-machine runner wrapping core analysis, Gate A, google-genai & FFmpeg assembly."""

    def __init__(
        self,
        settings: Settings,
        store: JobStore,
        storage: Optional[StorageBackend] = None,
        provider_factory: Optional[Callable[[Settings], GenAIMediaProvider]] = None,
    ) -> None:
        self.settings = settings
        self.store = store
        self.storage = storage or build_storage(settings)
        self.provider_factory = provider_factory or (lambda s: GenAIMediaProvider(s))
        self.scripts_dir = settings.resolved_scripts_dir

    def run_campaign(self, req: CampaignRequest, *, job_id: Optional[str] = None) -> Dict[str, Any]:
        jid = job_id or f"job_{uuid.uuid4().hex[:12]}"
        if not self.store.get_job(jid):
            self.store.create_job(jid, req.campaign_id, req.__dict__, status="RUNNING", stage="INIT")

        work_dir = Path(self.settings.work_root).resolve() / req.campaign_id / jid
        work_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Resolve source video (local path or object storage download)
            src_local: Optional[Path] = None
            if req.source_object_key:
                dl_dest = work_dir / "source" / Path(req.source_object_key).name
                self.storage.download_file(req.source_object_key, dl_dest)
                src_local = dl_dest
            elif req.source_video:
                src_local = Path(req.source_video).expanduser().resolve()
                if not src_local.exists():
                    raise FileNotFoundError(f"Source video not found: {src_local}")

            # Stage 1: ANALYZING
            self.store.update_job(jid, status="RUNNING", stage="ANALYZING")
            analysis_dir = work_dir / "analysis"
            source_meta_path: Optional[Path] = None
            source_meta: Dict[str, Any] = {}
            contact_sheet_path = analysis_dir / "source_contact_sheet.png"

            if src_local is not None:
                effective_src = src_local
                if req.normalize_cfr:
                    cfr_out = work_dir / "source" / f"{src_local.stem}_cfr.mp4"
                    cfr_proc = _run_script(
                        self.scripts_dir,
                        "ad_source_analyzer.py",
                        ["normalize-cfr", "--input", str(src_local), "--out", str(cfr_out)],
                    )
                    if cfr_proc.returncode != 0:
                        raise RuntimeError(f"normalize-cfr failed: {cfr_proc.stderr or cfr_proc.stdout}")
                    effective_src = cfr_out

                an_proc = _run_script(
                    self.scripts_dir,
                    "ad_source_analyzer.py",
                    ["analyze", "--input", str(effective_src), "--out-dir", str(analysis_dir)],
                )
                if an_proc.returncode != 0:
                    raise RuntimeError(f"ad_source_analyzer failed: {an_proc.stderr or an_proc.stdout}")
                source_meta_path = analysis_dir / "source_metadata.json"
                if source_meta_path.exists():
                    source_meta = json.loads(source_meta_path.read_text(encoding="utf-8"))
            else:
                effective_src = None

            # Resolve product facts ledger
            facts_target = work_dir / "00_product_facts.md"
            if req.facts_markdown:
                facts_target.write_text(req.facts_markdown, encoding="utf-8")
            elif req.facts_path:
                fp = Path(req.facts_path).expanduser().resolve()
                if not fp.exists():
                    raise FileNotFoundError(f"Product facts file not found: {fp}")
                shutil.copy2(fp, facts_target)
            elif not facts_target.exists():
                raise ValueError(
                    "facts_path or facts_markdown is required to ground claims in 00_product_facts.md"
                )

            # Stage 2: PLANNING
            self.store.update_job(jid, status="RUNNING", stage="PLANNING")
            spec_target = work_dir / "05_ad_spec.json"
            if req.spec_data is not None:
                spec_data = dict(req.spec_data)
                spec_target.write_text(
                    json.dumps(spec_data, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                spec_base_dir = work_dir
            elif req.spec_path:
                sp = Path(req.spec_path).expanduser().resolve()
                if not sp.exists():
                    raise FileNotFoundError(f"Spec JSON not found: {sp}")
                spec_data = json.loads(sp.read_text(encoding="utf-8"))
                # Preserve relative assets next to source spec if running in external directory
                spec_target.write_text(json.dumps(spec_data, ensure_ascii=False, indent=2), encoding="utf-8")
                spec_base_dir = sp.parent
            else:
                provider = self.provider_factory(self.settings)
                past_archs = [
                    p.get("a_genre_archetype")
                    for p in self.store.list_past_campaigns()
                    if p.get("a_genre_archetype")
                ]
                spec_data = provider.plan_ad_spec(
                    facts_target.read_text(encoding="utf-8"),
                    source_meta,
                    contact_sheet_path,
                    track_archetype=req.track_archetype,
                    past_archetypes=past_archs,
                )
                spec_target.write_text(json.dumps(spec_data, ensure_ascii=False, indent=2), encoding="utf-8")
                spec_base_dir = work_dir

            # Compile 05_jobs.json & credit quote
            jobs_target = work_dir / "05_jobs.json"
            quote_target = work_dir / "05_credit_quote.md"
            fj_proc = _run_script(
                self.scripts_dir,
                "ad_flow_jobs.py",
                [
                    "--spec",
                    str(spec_target),
                    "--out-jobs",
                    str(jobs_target),
                    "--out-quote",
                    str(quote_target),
                    "--res",
                    req.resolution,
                ],
            )
            if fj_proc.returncode != 0:
                raise RuntimeError(f"ad_flow_jobs failed: {fj_proc.stderr or fj_proc.stdout}")
            jobs_summary = json.loads(fj_proc.stdout.strip())

            # Stage 3: LINTING (hard gate BEFORE spending paid generation credits)
            self.store.update_job(jid, status="RUNNING", stage="LINTING")
            lint_report_path = work_dir / "lint_report.md"
            lint_args = [
                "--spec",
                str(spec_target),
                "--facts",
                str(facts_target),
                "--jobs",
                str(jobs_target),
                "--out",
                str(lint_report_path),
            ]
            if source_meta_path and source_meta_path.exists():
                lint_args.extend(["--source-meta", str(source_meta_path)])
            if req.compare_abc_specs and len(req.compare_abc_specs) == 3:
                lint_args.extend(["--compare-abc", *req.compare_abc_specs])

            if spec_data.get("track_archetype") == "A_bgrade_reversal" and not req.skip_cross_campaign_reskin:
                prior_specs: List[str] = []
                for p in self.store.list_past_campaigns():
                    sp_old = p.get("spec_path")
                    if sp_old and p.get("campaign_id") != req.campaign_id and os.path.exists(sp_old):
                        prior_specs.append(sp_old)
                for extra_sp in req.extra_past_specs:
                    if os.path.exists(extra_sp) and extra_sp not in prior_specs:
                        prior_specs.append(extra_sp)
                if prior_specs:
                    lint_args.extend(["--compare-campaigns", *prior_specs, str(spec_target)])

            lint_proc = _run_script(self.scripts_dir, "ad_gate_a_lint.py", lint_args)
            lint_payload = {
                "passed": lint_proc.returncode == 0,
                "stdout": lint_proc.stdout.strip(),
                "stderr": lint_proc.stderr.strip(),
                "quote": jobs_summary,
                "report_path": str(lint_report_path),
            }
            if lint_proc.returncode != 0:
                self.store.update_job(
                    jid,
                    status="FAILED",
                    stage="LINT_FAILED",
                    lint=lint_payload,
                    error=lint_proc.stdout.strip() or lint_proc.stderr.strip() or "Gate A lint failed",
                )
                raise LintFailedError(lint_payload["stdout"] or "Gate A lint failed")

            self.store.update_job(jid, status="RUNNING", stage="LINT_PASSED", lint=lint_payload)

            if req.dry_run:
                artifacts = {
                    "spec": self.storage.upload_file(spec_target, f"{req.campaign_id}/{jid}/05_ad_spec.json"),
                    "jobs": self.storage.upload_file(jobs_target, f"{req.campaign_id}/{jid}/05_jobs.json"),
                    "credit_quote": self.storage.upload_file(quote_target, f"{req.campaign_id}/{jid}/05_credit_quote.md"),
                    "lint_report": self.storage.upload_file(lint_report_path, f"{req.campaign_id}/{jid}/lint_report.md"),
                }
                return self.store.update_job(
                    jid,
                    status="DRY_RUN_READY",
                    stage="DRY_RUN_READY",
                    lint=lint_payload,
                    artifacts=artifacts,
                )

            # Stage 4: GENERATING
            self.store.update_job(jid, status="RUNNING", stage="GENERATING")
            provider = self.provider_factory(self.settings)
            jobs_json_data = json.loads(jobs_target.read_text(encoding="utf-8"))
            has_work = bool(
                jobs_json_data.get("anchors")
                or jobs_json_data.get("references")
                or jobs_json_data.get("units")
                or jobs_json_data.get("tts_beats")
            )
            gen_report: Dict[str, Any] = {"skipped": True, "reason": "no_generative_jobs"}
            gen_project_dir = spec_base_dir if (req.spec_path and not has_work) else work_dir
            if has_work:
                gen_project_dir = work_dir
                gen_report = execute_jobs_file(
                    jobs_target,
                    gen_project_dir,
                    provider,
                    source_video=str(effective_src) if effective_src else spec_data.get("source_video"),
                    concurrency=req.concurrency or self.settings.concurrency,
                    max_credits=req.max_credits if req.max_credits is not None else self.settings.max_video_credits_per_job,
                    skip_existing=True,
                )
            self.store.update_job(jid, generation=gen_report)

            # Optional manifest VO prep
            if req.vo_manifest_path:
                vm = Path(req.vo_manifest_path).expanduser().resolve()
                vo_wav = work_dir / "audio" / "vo_master.wav"
                vo_json = work_dir / "audio" / "vo_segments.json"
                vo_proc = _run_script(
                    self.scripts_dir,
                    "ad_audio_prep.py",
                    ["--manifest", str(vm), "--out-wav", str(vo_wav), "--out-json", str(vo_json)],
                )
                if vo_proc.returncode != 0:
                    raise RuntimeError(f"ad_audio_prep failed: {vo_proc.stderr or vo_proc.stdout}")

            # Stage 5: ASSEMBLING
            self.store.update_job(jid, status="RUNNING", stage="ASSEMBLING")
            final_dir = work_dir / "final"
            qa_strip_path = final_dir / "qa_strip.png"
            base_dir_for_asm = gen_project_dir if not has_work else work_dir
            asm_args = [
                "--spec",
                str(spec_target),
                "--out-dir",
                str(final_dir),
                "--work-dir",
                str(work_dir / "work"),
                "--base-dir",
                str(base_dir_for_asm),
                "--qa-strip",
                str(qa_strip_path),
            ]
            if req.clean_copy:
                asm_args.append("--clean-copy")
            asm_proc = _run_script(self.scripts_dir, "ad_remix_assemble.py", asm_args)
            if asm_proc.returncode != 0:
                raise RuntimeError(f"ad_remix_assemble failed: {asm_proc.stderr or asm_proc.stdout}")
            asm_meta = json.loads(asm_proc.stdout.strip())

            thumb_res: Optional[Dict[str, Any]] = None
            if req.thumbs_spec_path:
                tsp = Path(req.thumbs_spec_path).expanduser().resolve()
                t_out = work_dir / "thumbnails"
                t_proc = _run_script(
                    self.scripts_dir,
                    "ad_thumbnail_builder.py",
                    ["--spec", str(tsp), "--out-dir", str(t_out)],
                )
                if t_proc.returncode != 0:
                    raise RuntimeError(f"ad_thumbnail_builder failed: {t_proc.stderr or t_proc.stdout}")
                thumb_res = json.loads(t_proc.stdout.strip())

            # Stage 6: QC_READY & Storage Upload
            artifacts: Dict[str, Any] = {
                "work_dir": str(work_dir),
                "spec": self.storage.upload_file(spec_target, f"{req.campaign_id}/{jid}/05_ad_spec.json"),
                "lint_report": self.storage.upload_file(lint_report_path, f"{req.campaign_id}/{jid}/lint_report.md"),
                "rendered": self._upload_rendered(asm_meta, req.campaign_id, jid),
            }
            if qa_strip_path.exists():
                artifacts["qa_strip"] = self.storage.upload_file(
                    qa_strip_path, f"{req.campaign_id}/{jid}/final/{qa_strip_path.name}"
                )
            if thumb_res:
                thumb_urls: List[Dict[str, Any]] = []
                for t in thumb_res.get("thumbnails") or []:
                    tp = t.get("path")
                    if tp and os.path.exists(tp):
                        thumb_urls.append({
                            "id": t.get("id"),
                            "safe_zone_ok": t.get("safe_zone_ok"),
                            "url": self.storage.upload_file(tp, f"{req.campaign_id}/{jid}/thumbnails/{Path(tp).name}"),
                        })
                artifacts["thumbnails"] = thumb_urls

            if spec_data.get("a_genre_archetype"):
                self.store.register_past_campaign(
                    req.campaign_id, spec_data.get("a_genre_archetype"), spec_target
                )

            return self.store.update_job(
                jid,
                status="QC_READY",
                stage="QC_READY",
                lint=lint_payload,
                generation=gen_report,
                artifacts=artifacts,
                error="",
            )

        except Exception as exc:
            existing = self.store.get_job(jid)
            if existing and existing.get("status") != "FAILED":
                self.store.update_job(jid, status="FAILED", stage=existing.get("stage", "FAILED"), error=str(exc))
            raise

    def _upload_rendered(self, asm_meta: Dict[str, Any], campaign_id: str, job_id: str) -> List[Dict[str, Any]]:
        rendered_out: List[Dict[str, Any]] = []
        for item in asm_meta.get("rendered") or []:
            entry: Dict[str, Any] = {
                "variant": item.get("variant"),
                "duration": item.get("duration"),
                "lufs": item.get("lufs"),
            }
            mp4_path = item.get("mp4") or item.get("master_mp4")
            if mp4_path and os.path.exists(mp4_path):
                entry["master_mp4"] = self.storage.upload_file(
                    mp4_path, f"{campaign_id}/{job_id}/final/{Path(mp4_path).name}"
                )
            for key in ("clean_mp4", "srt"):
                fpath = item.get(key)
                if key == "clean_mp4" and (not fpath or not os.path.exists(fpath)) and mp4_path:
                    sibling = Path(mp4_path).with_name(f"{Path(mp4_path).stem}_clean.mp4")
                    if sibling.is_file():
                        fpath = str(sibling)
                if fpath and os.path.exists(fpath):
                    entry[key] = self.storage.upload_file(
                        fpath, f"{campaign_id}/{job_id}/final/{Path(fpath).name}"
                    )
            rendered_out.append(entry)
        return rendered_out

    def retry_unit(self, job_id: str, unit_id: str) -> Dict[str, Any]:
        """Surgically regenerate one failed/rejected video unit and re-assemble."""
        job = self.store.get_job(job_id)
        if not job:
            raise KeyError(f"Unknown job_id: {job_id}")
        payload = job.get("payload") or {}
        campaign_id = job["campaign_id"]
        work_dir = Path(self.settings.work_root).resolve() / campaign_id / job_id
        jobs_target = work_dir / "05_jobs.json"
        spec_target = work_dir / "05_ad_spec.json"
        if not jobs_target.exists() or not spec_target.exists():
            raise FileNotFoundError(f"Missing 05_jobs.json or 05_ad_spec.json in {work_dir}")

        self.store.update_job(job_id, status="RUNNING", stage=f"RETRY_UNIT:{unit_id}")
        provider = self.provider_factory(self.settings)
        gen_report = execute_jobs_file(
            jobs_target,
            work_dir,
            provider,
            source_video=payload.get("source_video"),
            concurrency=1,
            max_credits=payload.get("max_credits") or self.settings.max_video_credits_per_job,
            skip_existing=False,
            only_unit_ids=[unit_id],
        )

        final_dir = work_dir / "final"
        qa_strip_path = final_dir / "qa_strip.png"
        asm_args = [
            "--spec",
            str(spec_target),
            "--out-dir",
            str(final_dir),
            "--work-dir",
            str(work_dir / "work"),
            "--base-dir",
            str(work_dir),
            "--qa-strip",
            str(qa_strip_path),
        ]
        if payload.get("clean_copy"):
            asm_args.append("--clean-copy")
        asm_proc = _run_script(self.scripts_dir, "ad_remix_assemble.py", asm_args)
        if asm_proc.returncode != 0:
            raise RuntimeError(f"ad_remix_assemble retry failed: {asm_proc.stderr or asm_proc.stdout}")
        asm_meta = json.loads(asm_proc.stdout.strip())

        artifacts = dict(job.get("artifacts") or {})
        artifacts["rendered"] = self._upload_rendered(asm_meta, campaign_id, job_id)

        return self.store.update_job(
            job_id,
            status="QC_READY",
            stage="QC_READY",
            generation=gen_report,
            artifacts=artifacts,
            error="",
        )
