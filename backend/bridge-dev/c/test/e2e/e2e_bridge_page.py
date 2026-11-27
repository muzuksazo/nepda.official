# Browser e2e for the C worker: drives bridge-dev/index.html served by the local C server.
# usage: python e2e_bridge_page.py <base_url> <preset> <shot_dir> [cycles]
import json, sys, time, urllib.request
from playwright.sync_api import sync_playwright

base, preset, shots = sys.argv[1], sys.argv[2], sys.argv[3]
cycles = int(sys.argv[4]) if len(sys.argv) > 4 else 1
results, fails = [], []


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    if not ok:
        fails.append(name)
    print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail else ""), flush=True)


with sync_playwright() as pw:
    browser = pw.chromium.launch(channel="msedge")
    page = browser.new_page(viewport={"width": 1280, "height": 1700})
    calls, console_errors = [], []
    page.on("response", lambda r: calls.append((r.request.method, r.url.replace(base, ""), r.status)) if "/v1/" in r.url else None)
    page.on("console", lambda m: console_errors.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: console_errors.append(str(e)))

    page.goto(f"{base}/?preset={preset}")
    check("page loads with preset", page.locator("#pname").input_value() != "", page.locator("#pname").input_value())
    check("mock mode is off (real calls)", not page.locator("#mock").is_checked())
    check("C type selected", page.locator('input[name="htype"][value="C"]').is_checked())
    check("base url points at this server", page.locator("#base").input_value() == base)
    facts = [f for f in page.locator("#pfacts").input_value().splitlines() if f.strip()]
    check("verified facts filled", len(facts) >= 2, f"{len(facts)} facts")

    for n in range(1, cycles + 1):
        t0 = time.time()
        page.click("#bAll")
        page.wait_for_function(
            "() => /1회 완료|오류/.test(document.getElementById('status').textContent) && !document.getElementById('bAll').disabled",
            timeout=600000)
        status = page.locator("#status").inner_text()
        check(f"cycle {n}: flow finishes", "1회 완료" in status, f"{status} / {time.time() - t0:.0f}s")
        page.wait_for_function(f"() => document.querySelectorAll('#cPlayer video').length >= {n}", timeout=15000)

    state = page.evaluate("() => ({project: S.project, rounds: S.rounds})")
    rounds = state["rounds"]
    check("rounds recorded", len(rounds) == cycles, f"{len(rounds)}")
    check("round numbers increase", [r["round"] for r in rounds] == list(range(1, cycles + 1)), str([r["round"] for r in rounds]))
    hook_dirs = [r["hook"]["output_dir"] for r in rounds]
    check("each round has its own hook folder", len(set(hook_dirs)) == cycles, str(hook_dirs))

    for r in rounds:
        n, sc, hook = r["round"], r["scenario"], r["hook"]
        beats = sc["beats"]
        check(f"round {n}: 3-5 beats, <=15s", 3 <= len(beats) <= 5 and sc["hook_duration_sec"] <= 15, f"{len(beats)} beats, {sc['hook_duration_sec']}s")
        check(f"round {n}: roles problem -> proof -> CTA", beats[0]["role"] == "문제" and beats[1]["role"] == "가장 강한 증명" and beats[-1]["role"] == "CTA")
        bad = [c for c in (sc.get("checks") or []) if not c.get("ok", c.get("passed", True))] if isinstance(sc.get("checks"), list) else sc.get("checks")
        check(f"round {n}: rule checks", not bad if isinstance(bad, list) else True, json.dumps(bad, ensure_ascii=False)[:200])
        frames = (r["storyboard"] or {}).get("frames") or []
        check(f"round {n}: storyboard frame per beat", len(frames) == len(beats), f"{len(frames)} frames")
        check(f"round {n}: selected", r["selected_scenario_id"] == sc["scenario_id"])
        check(f"round {n}: hook done", hook["status"] == "done" and not hook.get("error"), hook.get("note") or "")
        files = hook["files"]
        need = ["hook_video", "tts_audio", "subtitles_srt", "scenario_json", "storyboard_images"]      # note = narration skipped (no key)
        check(f"round {n}: output files listed", all(k in files for k in need), ",".join(files.keys()))
        for k, v in files.items():
            for url in (v if isinstance(v, list) else [v]):
                req = urllib.request.Request(url, headers={"Range": "bytes=0-1023"})
                with urllib.request.urlopen(req) as resp:
                    total = int(resp.headers.get("Content-Range", "/0").split("/")[1] or 0)
                    ok = resp.status == 206 and total > 200
                check(f"round {n}: download {k} ({url.rsplit('/', 1)[1]})", ok, f"{total} bytes")

    imgs = page.evaluate("() => Array.from(document.querySelectorAll('#results img')).map(i => [i.src.split('/').pop(), i.complete && i.naturalWidth])")
    check("storyboard images render in page", imgs and all(w for _, w in imgs), f"{len(imgs)} images")

    vids = page.evaluate("""async () => {
      const out = [];
      for (const v of document.querySelectorAll('#cPlayer video')) {
        if (v.readyState < 1) await new Promise((res, rej) => { v.onloadedmetadata = res; v.onerror = () => rej(new Error('video error')); setTimeout(res, 15000); });
        v.muted = true; try { await v.play(); } catch (e) {}
        await new Promise(r => setTimeout(r, 2500)); v.pause();
        out.push({w: v.videoWidth, h: v.videoHeight, dur: v.duration, t: v.currentTime, err: v.error && v.error.code});
      }
      return out; }""")
    for i, v in enumerate(vids, 1):
        check(f"video {i}: plays in browser", not v["err"] and v["t"] > 1, f"{v['w']}x{v['h']}, {v['dur']:.1f}s, played {v['t']:.1f}s")
        check(f"video {i}: vertical 1080x1920, <=15s", v["w"] == 1080 and v["h"] == 1920 and v["dur"] <= 15.3)

    pid = state["project"]["project_id"]
    flow_n = len(calls)
    neg = page.evaluate("""async (pid) => {
      const j = async (m, p, b) => { const r = await fetch(p, {method: m, headers: {'Content-Type': 'application/json'}, body: b ? JSON.stringify(b) : undefined});
        let d = null; try { d = await r.json(); } catch (e) {} return [r.status, d && d.detail && d.detail.error && d.detail.error.code]; };
      return {
        unknownProject: await j('POST', '/v1/projects/proj_nope/scenarios', {count: 1}),
        notC: await j('POST', '/v1/projects/' + pid + '/scenarios', {types: ['A'], count: 1}),
        noFacts: await j('POST', '/v1/projects', {product: {name: 'x', category: 'living', verified_facts: []}, selected_types: ['C']}),
        hookUnselected: await j('POST', '/v1/projects/' + pid + '/hooks', {scenario_id: 'sc_other'}),
        hookMissing: await j('GET', '/v1/projects/' + pid + '/hooks/hook_nope'),
        badJson: await (async () => { const r = await fetch('/v1/product-info', {method: 'POST', body: '{oops'}); return [r.status]; })(),
        outputs: await (async () => { const r = await fetch('/v1/projects/' + pid + '/outputs'); return [r.status, (await r.json()).outputs.length]; })(),
        traversal: await (async () => { const r = await fetch('/files/..%2F..%2Fsrc%2Fserver.py'); return [r.status]; })(),
      }; }""", pid)
    check("error: unknown project -> 404", neg["unknownProject"] == [404, "PROJECT_NOT_FOUND"], str(neg["unknownProject"]))
    check("error: non-C scenario request -> 422", neg["notC"][0] == 422, str(neg["notC"]))
    check("error: no verified facts -> 422", neg["noFacts"][0] == 422, str(neg["noFacts"]))
    check("error: hook before select -> 409", neg["hookUnselected"] == [409, "INVALID_STATE"], str(neg["hookUnselected"]))
    check("error: unknown hook -> 404", neg["hookMissing"] == [404, "HOOK_NOT_FOUND"], str(neg["hookMissing"]))
    check("error: broken JSON -> 422", neg["badJson"] == [422], str(neg["badJson"]))
    check("outputs lists every round", neg["outputs"] == [200, cycles], str(neg["outputs"]))
    check("file path escape blocked", neg["traversal"] == [404], str(neg["traversal"]))

    bad_calls = [c for c in calls[:flow_n] if c[2] >= 400]
    check("no failed API call during the flow", not bad_calls, f"{flow_n} calls, failed: {bad_calls}")
    check("no console errors during the flow", not [e for e in console_errors if "Failed to load resource" not in e], f"{len(console_errors)} expected 4xx notices from the error-case calls")

    page.screenshot(path=f"{shots}/e2e_{preset}.png", full_page=True)
    json.dump({"preset": preset, "project": pid, "hook_dirs": hook_dirs, "calls": calls, "results": results},
              open(f"{shots}/e2e_{preset}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    browser.close()

print(f"\n{preset}: {len(results) - len(fails)}/{len(results)} passed" + (f"  FAILED: {fails}" if fails else ""))
sys.exit(1 if fails else 0)
