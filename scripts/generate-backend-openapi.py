#!/usr/bin/env python3
"""Generate FastAPI/Pydantic v2 schemas & typed route contracts from contracts/openapi.json."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
OPENAPI_JSON = ROOT / "contracts" / "openapi.json"
OUT_SCHEMAS = ROOT / "backend" / "app" / "generated_schemas.py"
OUT_CONTRACT = ROOT / "backend" / "app" / "generated_contract.py"


def _resolve_ref_name(schema: Optional[Dict]) -> Optional[str]:
    if not isinstance(schema, dict):
        return None
    ref = schema.get("$ref")
    if isinstance(ref, str) and ref.startswith("#/components/schemas/"):
        return ref.rsplit("/", 1)[-1]
    return None


def _run_datamodel_codegen() -> None:
    codegen_bin = Path(sys.executable).parent / "datamodel-codegen"
    if not codegen_bin.exists():
        raise FileNotFoundError(f"datamodel-codegen not found next to {sys.executable}")
    cmd = [
        str(codegen_bin),
        "--input",
        str(OPENAPI_JSON),
        "--input-file-type",
        "openapi",
        "--output",
        str(OUT_SCHEMAS),
        "--output-model-type",
        "pydantic_v2.BaseModel",
        "--target-python-version",
        "3.12",
        "--use-standard-collections",
        "--use-union-operator",
        "--use-double-quotes",
        "--disable-timestamp",
        "--collapse-root-models",
    ]
    subprocess.run(cmd, check=True)


def _generate_contract() -> Tuple[int, List[str]]:
    spec = json.loads(OPENAPI_JSON.read_text(encoding="utf-8"))
    version = str((spec.get("info") or {}).get("version") or "0.0.0")
    schema_names = set((spec.get("components") or {}).get("schemas", {}).keys())

    ops: List[Dict] = []
    for path, methods in spec.get("paths", {}).items():
        if not isinstance(methods, dict):
            continue
        for method in ("get", "post", "put", "patch", "delete"):
            op = methods.get(method)
            if not isinstance(op, dict):
                continue
            op_id = str(op.get("operationId") or f"{method}_{path}")
            tags = tuple(str(t) for t in (op.get("tags") or []))

            req_schema = None
            rb = op.get("requestBody")
            if isinstance(rb, dict):
                app_json = ((rb.get("content") or {}).get("application/json") or {})
                req_schema = _resolve_ref_name(app_json.get("schema"))

            success_status = 200
            resp_schema = None
            responses = op.get("responses") or {}
            for code_str in sorted(responses.keys()):
                if code_str.startswith("2") and code_str.isdigit():
                    success_status = int(code_str)
                    r_obj = responses[code_str] or {}
                    app_json = ((r_obj.get("content") or {}).get("application/json") or {})
                    resp_schema = _resolve_ref_name(app_json.get("schema"))
                    break

            path_params: List[Tuple[str, str]] = []
            query_params: List[Tuple[str, str, bool]] = []
            for param in op.get("parameters") or []:
                if not isinstance(param, dict):
                    continue
                p_name = str(param.get("name"))
                p_in = param.get("in")
                p_req = bool(param.get("required"))
                p_type = (param.get("schema") or {}).get("type", "string")
                py_type = {"integer": "int", "number": "float", "boolean": "bool"}.get(p_type, "str")
                if p_in == "path":
                    path_params.append((p_name, py_type))
                elif p_in == "query":
                    query_params.append((p_name, py_type, p_req))

            ops.append(
                {
                    "method": method.upper(),
                    "path": path,
                    "operation_id": op_id,
                    "tags": tags,
                    "success_status": success_status,
                    "request_schema": req_schema if req_schema in schema_names else None,
                    "response_schema": resp_schema if resp_schema in schema_names else None,
                    "path_params": path_params,
                    "query_params": query_params,
                }
            )

    imported = sorted(
        {
            s
            for o in ops
            for s in (o["request_schema"], o["response_schema"])
            if s is not None
        }
    )

    lines: List[str] = [
        '# Auto-generated from contracts/openapi.json by scripts/generate-backend-openapi.py',
        '# Do not edit manually.',
        '',
        'from __future__ import annotations',
        '',
        'from dataclasses import dataclass',
        'from typing import Any, Dict, Protocol, Tuple',
        '',
    ]
    if imported:
        lines.append('from .generated_schemas import (')
        for name in imported:
            lines.append(f'    {name},')
        lines.append(')')
        lines.append('')

    lines.extend([
        f'OPENAPI_SPEC_VERSION: str = {version!r}',
        '',
        '',
        '@dataclass(frozen=True)',
        'class RouteContract:',
        '    method: str',
        '    path: str',
        '    operation_id: str',
        '    tags: Tuple[str, ...]',
        '    success_status: int',
        '    request_schema: str | None',
        '    response_schema: str | None',
        '',
        '',
        'EXPECTED_OPERATIONS: Tuple[RouteContract, ...] = (',
    ])
    for o in ops:
        lines.append(
            f"    RouteContract(method={o['method']!r}, path={o['path']!r}, "
            f"operation_id={o['operation_id']!r}, tags={o['tags']!r}, "
            f"success_status={o['success_status']!r}, "
            f"request_schema={o['request_schema']!r}, "
            f"response_schema={o['response_schema']!r}),"
        )
    lines.extend([
        ')',
        '',
        '',
        'class NapdaBackendProtocol(Protocol):',
        '    """Typed FastAPI route contract generated from contracts/openapi.json."""',
        '',
    ])
    for o in ops:
        args = ['self']
        for pname, ptype in o['path_params']:
            args.append(f'{pname}: {ptype}')
        if o['request_schema']:
            args.append(f"body: {o['request_schema']}")
        for qname, qtype, qreq in o['query_params']:
            args.append(f'{qname}: {qtype}' if qreq else f'{qname}: {qtype} | None = None')
        ret = o['response_schema'] if o['response_schema'] else ('None' if o['success_status'] == 204 else 'Dict[str, Any]')
        lines.append(f"    def {o['operation_id']}({', '.join(args)}) -> {ret}: ...")

    lines.append('')
    OUT_CONTRACT.write_text('\n'.join(lines), encoding='utf-8')
    return len(ops), imported


def main() -> None:
    _run_datamodel_codegen()
    op_count, imported = _generate_contract()
    print(f"Generated {OUT_SCHEMAS.relative_to(ROOT)} and {OUT_CONTRACT.relative_to(ROOT)} ({op_count} operations, {len(imported)} route schemas)")


if __name__ == "__main__":
    main()
