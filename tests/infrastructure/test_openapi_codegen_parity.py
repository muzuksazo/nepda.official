"""OpenAPI 3.1 SSOT parity & v0.2 codegen tests across frontend (Orval) and backend (FastAPI)."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

from tests.support.projects_api import build_test_client, login_client
from tests.support.tempdirs import temporary_directory

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app import generated_contract, generated_schemas  # noqa: E402
from app.server import create_app  # noqa: E402
from app.config import Settings  # noqa: E402


class TestOpenApiCodegenParity(unittest.TestCase):
    def test_backend_routes_and_generated_schemas_match_openapi_spec(self) -> None:
        spec = json.loads((ROOT / "contracts" / "openapi.json").read_text(encoding="utf-8"))
        spec_schemas = set((spec.get("components") or {}).get("schemas", {}).keys())
        for name in spec_schemas:
            self.assertTrue(
                hasattr(generated_schemas, name),
                f"generated_schemas missing OpenAPI schema: {name}",
            )

        with temporary_directory() as td:
            app = create_app(
                Settings(
                    _env_file=None,
                    gemini_api_key="dummy-key",
                    work_root=str(Path(td) / "work"),
                    output_dir=str(Path(td) / "outputs"),
                    db_path=str(Path(td) / "napda.db"),
                )
            )
            live_openapi = app.openapi()
            live_paths = live_openapi.get("paths") or {}

            self.assertEqual(len(generated_contract.EXPECTED_OPERATIONS), 25)
            for op in generated_contract.EXPECTED_OPERATIONS:
                self.assertIn(op.path, live_paths, f"Missing live route path: {op.path}")
                self.assertIn(
                    op.method.lower(),
                    live_paths[op.path],
                    f"Missing live method {op.method} on {op.path}",
                )

    def test_frontend_orval_artifacts_exist_with_v02_operations(self) -> None:
        gen_root = ROOT / "frontend" / "src" / "api" / "generated"
        self.assertTrue((ROOT / "frontend" / "orval.config.ts").is_file())
        self.assertTrue((ROOT / "frontend" / "src" / "api" / "mutator.ts").is_file())
        self.assertTrue((ROOT / "frontend" / "src" / "api" / "index.ts").is_file())
        self.assertTrue((gen_root / "model" / "productInfoRequest.ts").is_file())
        self.assertTrue((gen_root / "model" / "createHookResponse.ts").is_file())

        projects_ts = (gen_root / "projects" / "projects.ts").read_text(encoding="utf-8")
        planning_ts = (gen_root / "planning" / "planning.ts").read_text(encoding="utf-8")
        hooks_ts = (gen_root / "hooks" / "hooks.ts").read_text(encoding="utf-8")
        self.assertIn("createProductInfoV1ProductInfoPost", projects_ts)
        self.assertIn("selectScenarioV1ProjectsProjectIdScenariosScenarioIdSelectPost", planning_ts)
        self.assertIn("createHookV1ProjectsProjectIdHooksPost", hooks_ts)
        self.assertIn("getHookV1ProjectsProjectIdHooksHookIdGet", hooks_ts)
        self.assertIn("listOutputsV1ProjectsProjectIdOutputsGet", hooks_ts)

    def test_v02_worker_flow_e2e(self) -> None:
        with temporary_directory() as td:
            root = Path(td)
            client = build_test_client(root)
            login_client(client)

            # 1. POST /v1/product-info (cache miss -> cache hit)
            pi_payload = {
                "product": {
                    "name": "마그네틱 주방 타이머",
                    "category": "kitchen",
                    "verified_facts": ["LED 대형 숫자", "자석 부착식"],
                },
                "source_url": "https://example.com/timer",
            }
            r1 = client.post("/v1/product-info", json=pi_payload)
            self.assertEqual(r1.status_code, 200, r1.text)
            b1 = r1.json()
            self.assertFalse(b1["cached"])
            pi_id = b1["product_info_id"]

            r2 = client.post("/v1/product-info", json=pi_payload)
            self.assertEqual(r2.status_code, 200, r2.text)
            self.assertTrue(r2.json()["cached"])
            self.assertEqual(r2.json()["product_info_id"], pi_id)

            # 2. POST /v1/projects with unknown product_info_id -> 404 PRODUCT_INFO_NOT_FOUND
            bad_proj = client.post(
                "/v1/projects",
                json={"product_info_id": "pi_missing", "selected_types": ["A"]},
            )
            self.assertEqual(bad_proj.status_code, 404)
            self.assertEqual(bad_proj.json()["detail"]["error"]["code"], "PRODUCT_INFO_NOT_FOUND")

            # Create project via cached product_info_id
            proj_resp = client.post(
                "/v1/projects",
                json={"product_info_id": pi_id, "selected_types": ["A"]},
            )
            self.assertEqual(proj_resp.status_code, 201, proj_resp.text)
            pid = proj_resp.json()["project_id"]

            # 3. POST /scenarios round=1 then append round=2
            s1 = client.post(f"/v1/projects/{pid}/scenarios", json={"provider": "anthropic", "count": 1})
            self.assertEqual(s1.status_code, 200, s1.text)
            d1 = s1.json()
            self.assertEqual(d1["round"], 1)
            self.assertEqual(len(d1["scenarios"]), 1)

            s2 = client.post(f"/v1/projects/{pid}/scenarios", json={"provider": "anthropic", "count": 1})
            self.assertEqual(s2.status_code, 200, s2.text)
            d2 = s2.json()
            self.assertEqual(d2["round"], 2)
            self.assertEqual(len(d2["scenarios"]), 2)
            chosen_sid = d2["scenarios"][1]["scenario_id"]

            # 4. POST /hooks before selecting -> 409 INVALID_STATE
            unselected = client.post(f"/v1/projects/{pid}/hooks", json={"scenario_id": chosen_sid})
            self.assertEqual(unselected.status_code, 409, unselected.text)
            self.assertEqual(unselected.json()["detail"]["error"]["code"], "INVALID_STATE")

            # 5. POST /scenarios/{sid}/select -> POST /hooks -> GET /hooks/{id} -> GET /outputs
            sel = client.post(f"/v1/projects/{pid}/scenarios/{chosen_sid}/select")
            self.assertEqual(sel.status_code, 200, sel.text)
            self.assertEqual(sel.json()["selected_scenario_id"], chosen_sid)

            hk = client.post(
                f"/v1/projects/{pid}/hooks",
                json={"scenario_id": chosen_sid, "tts": {"enabled": True, "voice": "Kore"}},
            )
            self.assertEqual(hk.status_code, 202, hk.text)
            hid = hk.json()["hook_id"]

            hk_get = client.get(f"/v1/projects/{pid}/hooks/{hid}")
            self.assertEqual(hk_get.status_code, 200, hk_get.text)
            hk_body = hk_get.json()
            self.assertEqual(hk_body["status"], "done")
            self.assertEqual(hk_body["files"]["scenario_json"], "scenario.json")
            self.assertTrue((Path(hk_body["output_dir"]) / "scenario.json").is_file())

            outs = client.get(f"/v1/projects/{pid}/outputs")
            self.assertEqual(outs.status_code, 200, outs.text)
            self.assertEqual(len(outs.json()["outputs"]), 1)
            self.assertEqual(outs.json()["outputs"][0]["hook_id"], hid)
