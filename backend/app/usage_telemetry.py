"""Per-request & per-stage API usage telemetry and cost estimation helpers."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("napda.usage_telemetry")

PRICING_VERSION = "2026-11"

# Standard list prices (USD per 1M tokens) matching `backend/bridge-dev/b/src/cost.ts`.
# Cache discounts and batch pricing are not applied; actual invoiced charges come from vendor billing.
LLM_PRICING_PER_1M_USD: Dict[str, Tuple[float, float]] = {
    "claude-fable-5-2": (8.0, 40.0),
    "claude-opus-5-5": (4.0, 20.0),
    "claude-opus-5": (5.0, 25.0),
    "claude-sonnet-5-5": (2.0, 10.0),
    "claude-sonnet-5": (2.0, 10.0),
    "claude-sonnet-4-5": (3.0, 15.0),
    "claude-haiku-5-5": (0.1, 0.5),
    "gemini-3.8-flash": (0.75, 3.75),
    "gemini-3.5-flash": (1.5, 9.0),
    "gemini-2.5-flash": (0.3, 2.5),
    "gemini-4-hydrogen": (1.5, 7.5),
    "gemini-4-neon": (3.0, 15.0),
}

# Estimated per-unit list prices (USD per image / sec / char) for media generation models.
# Override via USAGE_PRICING_OVERRIDES_JSON for exact contract/tier pricing.
MEDIA_PRICING_PER_UNIT_USD: Dict[str, Tuple[float, str]] = {
    "gemini-nano-banana-2.1": (0.0336, "image"),
    "gemini-2.5-flash-image": (0.039, "image"),
    "gemini-omni-flash-preview": (0.10, "sec"),
    "gemini-omni-1.2-flash": (0.07, "sec"),
    "gemini-omni-1.1-flash": (0.07, "sec"),
    "inworld-tts-2": (0.000025, "char"),
    "inworld-tts-2-flash": (0.000015, "char"),
    "gemini-3.8-flash-tts": (0.000016, "char"),
}


def parse_pricing_overrides(raw_json: Optional[str]) -> Dict[str, Any]:
    """Parse optional `USAGE_PRICING_OVERRIDES_JSON` safely without throwing."""
    if not raw_json or not str(raw_json).strip():
        return {}
    try:
        parsed = json.loads(str(raw_json))
    except ValueError as exc:
        logger.warning("Invalid USAGE_PRICING_OVERRIDES_JSON ignored: %s", exc)
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _match_token_pricing(
    model: str,
    overrides: Dict[str, Any],
) -> Optional[Tuple[Optional[float], Optional[float], Optional[float], Optional[str]]]:
    """Return (input_per_1m, output_per_1m, per_unit, unit) if known."""
    norm = (model or "").strip().lower()
    if not norm:
        return None

    for k, v in overrides.items():
        if str(k).strip().lower() == norm and isinstance(v, dict):
            if "per_unit" in v and v["per_unit"] is not None:
                return None, None, float(v["per_unit"]), str(v.get("unit") or "unit")
            if "input" in v and "output" in v:
                return float(v["input"]), float(v["output"]), None, None

    if norm in LLM_PRICING_PER_1M_USD:
        in_p, out_p = LLM_PRICING_PER_1M_USD[norm]
        return in_p, out_p, None, None

    # Prefix match for dated snapshots (longest match first)
    for known in sorted(LLM_PRICING_PER_1M_USD.keys(), key=len, reverse=True):
        if norm.startswith(known):
            in_p, out_p = LLM_PRICING_PER_1M_USD[known]
            return in_p, out_p, None, None

    if norm in MEDIA_PRICING_PER_UNIT_USD:
        per_u, unit_name = MEDIA_PRICING_PER_UNIT_USD[norm]
        return None, None, per_u, unit_name

    for known in sorted(MEDIA_PRICING_PER_UNIT_USD.keys(), key=len, reverse=True):
        if norm.startswith(known):
            per_u, unit_name = MEDIA_PRICING_PER_UNIT_USD[known]
            return None, None, per_u, unit_name
    return None


def estimate_cost_usd(
    model: str,
    *,
    input_tokens: int = 0,
    output_tokens: int = 0,
    cached_tokens: int = 0,
    thinking_tokens: int = 0,
    media_unit: Optional[str] = None,
    media_qty: float = 0.0,
    cache_hit: bool = False,
    overrides: Optional[Dict[str, Any]] = None,
) -> Tuple[Optional[float], str]:
    """Estimate USD cost and return a human-readable applied unit-price label."""
    if cache_hit:
        return 0.0, "cache_hit ($0)"

    ov = overrides or {}
    matched = _match_token_pricing(model, ov)
    if matched is None:
        return None, "단가 미등록"

    in_per_1m, out_per_1m, per_unit, ov_unit = matched
    if per_unit is not None:
        qty = float(media_qty or 0.0)
        unit_label = ov_unit or media_unit or "unit"
        label = (
            f"${per_unit * 1_000_000:g} / 1M char"
            if unit_label == "char" and per_unit < 0.001
            else f"${per_unit:g} / {unit_label}"
        )
        return round(qty * per_unit, 6), label

    if in_per_1m is not None and out_per_1m is not None:
        billable_in = max(0, int(input_tokens or 0))
        billable_out = max(0, int(output_tokens or 0) + int(thinking_tokens or 0))
        usd = (billable_in * in_per_1m + billable_out * out_per_1m) / 1_000_000.0
        return round(usd, 6), f"${in_per_1m:g}/${out_per_1m:g} / 1M tok"

    return None, "단가 미등록"


def pricing_catalog(overrides: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """Return sorted pricing table rows for the Admin Usage dashboard."""
    ov = overrides or {}
    rows: List[Dict[str, Any]] = []
    seen = set()

    for model_id, (in_p, out_p) in LLM_PRICING_PER_1M_USD.items():
        seen.add(model_id.lower())
        entry: Dict[str, Any] = {
            "model": model_id,
            "kind": "llm_1m_tokens",
            "input_usd_per_1m": in_p,
            "output_usd_per_1m": out_p,
            "per_unit_usd": None,
            "unit": "1M tokens",
            "source": "builtin",
        }
        for k, v in ov.items():
            if str(k).strip().lower() == model_id.lower() and isinstance(v, dict) and "input" in v and "output" in v:
                entry["input_usd_per_1m"] = float(v["input"])
                entry["output_usd_per_1m"] = float(v["output"])
                entry["source"] = "override"
        rows.append(entry)

    for model_id, (per_u, unit_name) in MEDIA_PRICING_PER_UNIT_USD.items():
        seen.add(model_id.lower())
        entry = {
            "model": model_id,
            "kind": "media_per_unit",
            "input_usd_per_1m": None,
            "output_usd_per_1m": None,
            "per_unit_usd": per_u,
            "unit": unit_name,
            "source": "builtin",
        }
        for k, v in ov.items():
            if str(k).strip().lower() == model_id.lower() and isinstance(v, dict) and v.get("per_unit") is not None:
                entry["per_unit_usd"] = float(v["per_unit"])
                entry["unit"] = str(v.get("unit") or unit_name)
                entry["source"] = "override"
        rows.append(entry)

    for k, v in ov.items():
        norm = str(k).strip().lower()
        if norm in seen or not isinstance(v, dict):
            continue
        if "per_unit" in v and v["per_unit"] is not None:
            rows.append(
                {
                    "model": str(k),
                    "kind": "media_per_unit",
                    "input_usd_per_1m": None,
                    "output_usd_per_1m": None,
                    "per_unit_usd": float(v["per_unit"]),
                    "unit": str(v.get("unit") or "unit"),
                    "source": "override",
                }
            )
        elif "input" in v and "output" in v:
            rows.append(
                {
                    "model": str(k),
                    "kind": "llm_1m_tokens",
                    "input_usd_per_1m": float(v["input"]),
                    "output_usd_per_1m": float(v["output"]),
                    "per_unit_usd": None,
                    "unit": "1M tokens",
                    "source": "override",
                }
            )
    return rows


def record_usage_safe(
    project_store: Any,
    settings: Any,
    *,
    project_id: Optional[str] = None,
    user_id: Optional[str] = None,
    job_id: Optional[str] = None,
    hook_type: Optional[str] = None,
    stage: str,
    step_name: Optional[str] = None,
    provider: str,
    model: str,
    input_tokens: Optional[int] = None,
    output_tokens: Optional[int] = None,
    cached_tokens: Optional[int] = None,
    thinking_tokens: Optional[int] = None,
    media_unit: Optional[str] = None,
    media_qty: Optional[float] = None,
    latency_ms: int = 0,
    cache_hit: bool = False,
    status: str = "ok",
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """Compute cost estimate and write `api_usage_events` row without ever failing callers."""
    if project_store is None or not hasattr(project_store, "record_api_usage"):
        return
    try:
        enriched_meta = dict(metadata or {})
        if str(provider or "").strip().lower() == "google" and not enriched_meta.get("vertex_profile"):
            try:
                from .genai_provider import get_last_vertex_profile, parse_vertex_profiles

                last_prof = get_last_vertex_profile()
                if last_prof and last_prof.get("vertex_profile"):
                    enriched_meta["vertex_profile"] = last_prof["vertex_profile"]
                    if last_prof.get("gcp_project"):
                        enriched_meta["gcp_project"] = last_prof["gcp_project"]
                elif getattr(settings, "google_genai_use_vertexai", False):
                    profs = parse_vertex_profiles(settings)
                    if len(profs) == 1:
                        enriched_meta["vertex_profile"] = profs[0].name
                        if profs[0].project:
                            enriched_meta["gcp_project"] = profs[0].project
                else:
                    enriched_meta["vertex_profile"] = "ai_studio"
            except Exception:
                pass

        overrides = parse_pricing_overrides(getattr(settings, "usage_pricing_overrides_json", None))
        est_usd, price_label = estimate_cost_usd(
            model,
            input_tokens=int(input_tokens or 0),
            output_tokens=int(output_tokens or 0),
            cached_tokens=int(cached_tokens or 0),
            thinking_tokens=int(thinking_tokens or 0),
            media_unit=media_unit,
            media_qty=float(media_qty or 0.0),
            cache_hit=bool(cache_hit),
            overrides=overrides,
        )
        project_store.record_api_usage(
            project_id=project_id,
            user_id=user_id,
            job_id=job_id,
            hook_type=hook_type,
            stage=stage,
            step_name=step_name,
            provider=provider,
            model=model,
            input_tokens=int(input_tokens or 0),
            output_tokens=int(output_tokens or 0),
            cached_tokens=int(cached_tokens or 0),
            thinking_tokens=int(thinking_tokens or 0),
            media_unit=media_unit,
            media_qty=float(media_qty) if media_qty is not None else None,
            estimated_cost_usd=est_usd,
            unit_price_label=price_label,
            pricing_version=PRICING_VERSION,
            latency_ms=max(0, int(latency_ms or 0)),
            cache_hit=bool(cache_hit),
            status=status,
            metadata=enriched_meta,
        )
    except Exception as exc:  # pragma: no cover - defensive guard
        logger.warning("Failed to record API usage telemetry (%s/%s): %s", stage, model, exc)
