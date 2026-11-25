"""Offline regression coverage organized by PRD area."""
from tests.support.media_tools import (
    FlowAutomatorHardeningCase,
    FlowAutomatorSpeedAndFocusCase,
    flow_automator,
    json,
    patch,
    tempfile,
)
from tests.support.tempdirs import temporary_directory


class TestFlowAutomatorHardening(FlowAutomatorHardeningCase):
    def test_open_lightbox_download_menu_compact_fallback_and_filter(self) -> None:
        dom_compact = {
            "elements": [
                {"role": "button", "name": "옵션 더보기", "ref": "r_more"},
            ]
        }
        dom_more_menu = {
            "elements": [
                {"role": "menuitem", "name": "즐겨찾기", "ref": "m_fav"},
                {"role": "menuitem", "name": "download 미디어 다운로드", "ref": "m_dl"},
                {"role": "menuitem", "name": "휴지통", "ref": "m_trash"},
            ]
        }
        dom_quality_menu = {
            "elements": [
                {"role": "menuitem", "name": "즐겨찾기", "ref": "q_fav"},
                {"role": "menuitem", "name": "720p 원본 크기", "ref": "q_720"},
                {"role": "menuitem", "name": "1080p 업스케일링됨", "ref": "q_1080"},
                {"role": "menuitem", "name": "휴지통", "ref": "q_trash"},
            ]
        }
        clicked: list[str] = []

        def fake_click_ref(_tab: int, ref: str) -> None:
            clicked.append(ref)

        with patch.object(flow_automator, "read_dom", side_effect=[dom_compact, dom_more_menu, dom_quality_menu]), patch.object(
            flow_automator, "click_ref", side_effect=fake_click_ref
        ), patch.object(flow_automator.time, "sleep"):
            _, filtered = flow_automator._open_lightbox_download_menu(123, media="video")

        self.assertEqual(clicked, ["r_more", "m_dl"])
        self.assertEqual([el["ref"] for el in filtered], ["q_720", "q_1080"])


    def test_open_tile_to_lightbox_stale_ref_fallback(self) -> None:
        urls = iter([
            "https://labs.google/fx/project/abc",
            "https://labs.google/fx/project/abc",
            "https://labs.google/fx/project/abc",
            "https://labs.google/fx/project/abc",
            "https://labs.google/fx/project/abc",
            "https://labs.google/fx/project/abc",
            "https://labs.google/fx/project/abc",
            "https://labs.google/fx/project/abc",
            "https://labs.google/fx/project/abc",
            "https://labs.google/fx/project/abc/edit/item-1",
        ])
        with patch.object(flow_automator, "click_xy", side_effect=RuntimeError("ugot click rc=1: stale_ref")), patch.object(
            flow_automator, "get_page_url", side_effect=lambda _t: next(urls)
        ), patch.object(flow_automator, "evaluate_js") as m_eval, patch.object(flow_automator.time, "sleep"):
            flow_automator._open_tile_to_lightbox(
                123,
                {"x": 200, "y": 300, "top": 220, "h": 180},
                "media_key_xyz",
                "wave tile",
            )
            self.assertTrue(m_eval.called)


    def test_generate_ref_ignores_signed_url_rotation_until_new_key(self) -> None:
        with temporary_directory() as td:
            media_states = iter([
                {"items": [{"src_key": "old_key_1"}], "firstKey": "old_key_1", "firstSrc": "https://cdn/1?sig=A"},
                {"items": [{"src_key": "old_key_1"}], "firstKey": "old_key_1", "firstSrc": "https://cdn/1?sig=B"},
                {"items": [{"src_key": "new_key_2"}], "firstKey": "new_key_2", "firstSrc": "https://cdn/2?sig=A"},
            ])
            texts = iter([
                "Minimalist desk frame, Zero camera cuts, zero readable text",
                "Minimalist desk frame, Zero camera cuts, zero readable text",
                "생성 중 40%",
                "완료됨",
            ])
            with patch.object(flow_automator, "ensure_grid_view"), patch.object(
                flow_automator, "scroll_grid_top"
            ), patch.object(flow_automator, "clear_attachments"), patch.object(
                flow_automator, "ensure_image_settings"
            ), patch.object(
                flow_automator, "read_dom", return_value={"elements": [{"role": "textbox", "name": "무엇을 만들고 싶으신가요?", "ref": "tb1"}, {"role": "button", "name": "생성 시작", "ref": "btn1"}]}
            ), patch.object(
                flow_automator, "ugot", return_value={}
            ), patch.object(
                flow_automator, "click_ref"
            ), patch.object(
                flow_automator, "evaluate_js", return_value=0
            ), patch.object(
                flow_automator, "read_text", side_effect=lambda _t: next(texts)
            ), patch.object(
                flow_automator, "get_media_state", side_effect=lambda _t: next(media_states)
            ), patch.object(
                flow_automator,
                "download_top_lightbox",
                return_value={
                    "file": "refs/R_T.png",
                    "src_key": "new_key_2",
                    "width": 768,
                    "height": 1376,
                    "bytes": 12345,
                    "title": "R_T",
                },
            ) as m_dl, patch.object(
                flow_automator.time, "sleep"
            ):
                res = flow_automator.generate_ref(
                    123,
                    td,
                    {
                        "id": "R_T",
                        "file": "refs/R_T.png",
                        "prompt": "Minimalist desk frame, Zero camera cuts, zero readable text",
                        "settings": {"aspect_ratio": "9:16"},
                    },
                )
            self.assertEqual(res["src_key"], "new_key_2")
            self.assertEqual(m_dl.call_count, 1)


    def test_ugot_retries_document_changed_error(self) -> None:
        resp_err = type("P", (), {"returncode": 1, "stdout": "", "stderr": "document_changed: page navigated"})()
        resp_ok = type("P", (), {"returncode": 0, "stdout": json.dumps({"structuredContent": {"ok": True}}), "stderr": ""})()
        with patch.object(flow_automator.subprocess, "run", side_effect=[resp_err, resp_ok]) as m_run, patch.object(
            flow_automator.time, "sleep"
        ) as m_sleep:
            out = flow_automator.ugot("read_page", {"tabId": 1})
        self.assertTrue(out["ok"])
        self.assertEqual(m_run.call_count, 2)
        m_sleep.assert_called_once_with(1.0)




class TestFlowAutomatorSpeedAndFocus(FlowAutomatorSpeedAndFocusCase):
    def test_poll_wave_snapshot_uses_single_eval_and_parses_keys(self) -> None:
        fake_eval = {
            "text": "생성 중 45%\nnormal line",
            "policy_count": 1,
            "still_running": True,
            "srcs": [
                "https://flow.google.com/asb/KEY_ONE=s512-rw",
                "https://flow.google.com/asb/KEY_TWO=s512-rw",
                "https://flow.google.com/asb/KEY_ONE=s512-rw",
            ],
        }
        with patch.object(flow_automator, "evaluate_js", return_value=fake_eval) as m_eval:
            snap = flow_automator.poll_wave_snapshot(999, max_items=16)
        self.assertEqual(m_eval.call_count, 1)
        self.assertTrue(snap["still_running"])
        self.assertEqual(snap["policy_count"], 1)
        self.assertEqual(snap["keys"], ["KEY_ONE", "KEY_TWO"])


    def test_submit_reuses_settings_cache_and_calls_tab_focus(self) -> None:
        with temporary_directory() as td:
            cfg = {
                "mode": "ingredients",
                "ar": "9:16",
                "res": "720p",
                "duration": 5,
                "model": "Omni 1.2 Flash",
                "est_credits": 15,
                "prompt": "One crisp 9:16 shot with zero readable text.",
                "rel_out": "clips/A1.mp4",
            }
            unit = {"id": "A1", "reference_ids": []}
            cache = {
                "sig": ("ingredients", "9:16", "720p", 5, "Omni 1.2 Flash"),
                "cost": 15,
            }
            dom = {
                "elements": [
                    {"role": "textbox", "name": "무엇을 만들고 싶으신가요?", "ref": "tb1"},
                    {"role": "button", "name": "생성 시작", "ref": "btn1"},
                ]
            }
            eval_returns = [
                "동영상 · 720p · 5초 crop_9_16 x1",
                "동영상 · 720p · 5초 crop_9_16 x1",
                {"hasOptions": False, "promptText": cfg["prompt"]},
                0,
            ]
            with patch.object(flow_automator, "ensure_tab_active") as m_focus, patch.object(
                flow_automator, "ensure_grid_view"
            ), patch.object(flow_automator, "clear_attachments"), patch.object(
                flow_automator, "attach_assets"
            ), patch.object(
                flow_automator, "ensure_video_settings_and_read_cost"
            ) as m_settings, patch.object(
                flow_automator, "evaluate_js", side_effect=eval_returns
            ), patch.object(
                flow_automator, "read_dom", return_value=dom
            ), patch.object(
                flow_automator, "ugot", return_value={}
            ), patch.object(
                flow_automator, "click_ref"
            ), patch.object(
                flow_automator.time, "sleep"
            ):
                cost, _ = flow_automator._submit_video_unit_to_flow(
                    123, td, unit, cfg, {}, 50, settings_cache=cache
                )
            self.assertEqual(cost, 15)
            self.assertEqual(m_settings.call_count, 0)
            m_focus.assert_called_once_with(123)
