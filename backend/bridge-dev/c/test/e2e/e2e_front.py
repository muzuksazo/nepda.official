# e2e through the real frontend (frontend/, Vite dev server) with the C worker server behind it. Records the screen.
# usage: python e2e_front.py <front_url> <footage> <out_dir> <product_name> <intro>
import json, os, shutil, sys, time
from playwright.sync_api import sync_playwright

front, footage, out, name, intro = sys.argv[1:6]
os.makedirs(out, exist_ok=True)
SIZE = {"width": 432, "height": 932}
results, fails = [], []


def check(label, ok, detail=""):
    results.append((label, bool(ok), str(detail)))
    if not ok:
        fails.append(label)
    print(("PASS " if ok else "FAIL ") + label + (f"  [{detail}]" if detail else ""), flush=True)


with sync_playwright() as pw:
    browser = pw.chromium.launch(channel="msedge")
    ctx = browser.new_context(viewport=SIZE, record_video_dir=out, record_video_size=SIZE)
    page = ctx.new_page()
    calls, errors = [], []
    page.on("response", lambda r: calls.append((r.request.method, r.url.replace(front, "").split("?")[0], r.status))
            if any(k in r.url for k in ("/v1/", "/dev-uploads/", "/dev-files/")) else None)
    page.on("pageerror", lambda e: errors.append(str(e)))
    btn = lambda label: page.get_by_role("button", name=label, exact=True)
    shot = lambda name: (os.makedirs(os.path.join(out, "shots"), exist_ok=True), page.screenshot(path=os.path.join(out, "shots", name + ".png")))
    pause = lambda ms=1500: page.wait_for_timeout(ms)
    try:
        page.goto(front)
        pause()
        if btn("냅다 시작하기").count():
            btn("냅다 시작하기").click()
        btn("영상 만들기").first.wait_for(timeout=15000)
        check("home screen opens (signed in as dev user)", True)
        pause()
        btn("영상 만들기").first.click()

        page.get_by_placeholder("예: 접이식 실리콘 도마").fill(name)
        page.get_by_placeholder("한 줄로 자랑해 주세요").fill(intro)
        page.locator("label.n-chip").filter(has_text="문구").click()
        shot("01_product")
        pause()
        btn("다음").click()

        page.get_by_text("첫 3초, 어떻게 낚을까요?").wait_for(timeout=15000)
        check("1 product info saved -> hook type screen", True)
        if page.get_by_role("checkbox", name="A 유형").is_checked():
            page.get_by_role("checkbox", name="A 유형").uncheck(force=True)
        page.get_by_role("checkbox", name="C 유형").check(force=True)
        pause()
        check("2 C type selected", "C 유형 1개" in page.locator("body").inner_text(), "")
        shot("02_hook")
        btn("시나리오 글 보기").click()

        btn("그림으로 보기").wait_for(timeout=20000)
        page.wait_for_function("() => !document.body.innerText.includes('머리 굴리는 중')", timeout=120000)
        text = page.locator("body").inner_text()
        check("3 scenario text shown", "훅 시나리오" in text and len(text) > 120, text.replace("\n", " ")[:90])
        shot("03_scenario")
        pause(2500)
        btn("그림으로 보기").click()

        page.wait_for_function("() => { const i = [...document.querySelectorAll('img')].filter(x => x.src.includes('/dev-files/')); return i.length >= 3 && i.every(x => x.complete && x.naturalWidth > 0); }", timeout=180000)
        n_img = page.evaluate("() => [...document.querySelectorAll('img')].filter(x => x.src.includes('/dev-files/')).length")
        check("4 storyboard images shown", n_img >= 3, f"{n_img} images")
        shot("04_storyboard")
        pause(2500)
        btn("촬영 가이드 받기").click()

        page.locator('ol[aria-label="촬영 순서"] li').first.wait_for(timeout=30000)
        n_shots = page.locator('ol[aria-label="촬영 순서"] li').count()
        check("5 filming guide shown", n_shots >= 2, f"{n_shots} shots")
        shot("05_guide")
        pause(2500)
        btn("찍은 영상 올리기").click()

        btn("훅 붙여서 만들기").wait_for(timeout=15000)
        page.locator('input[type="file"]').first.set_input_files(footage)
        pause(2000)
        check("6 footage picked, create enabled", btn("훅 붙여서 만들기").is_enabled())
        shot("06_upload")
        t0 = time.time()
        btn("훅 붙여서 만들기").click()

        pause(6000)
        shot("07_generating")
        btn("영상 보러 가기").wait_for(timeout=420000)          # generating screen: waits for the Veo call + render
        check("   generating screen reached done", True, f"{time.time() - t0:.0f}s")
        shot("08_done")
        pause(1500)
        btn("영상 보러 가기").click()
        page.get_by_text("짜잔, 영상 나왔어요").wait_for(timeout=180000)
        check("7 upload + render request accepted -> review screen", True, f"{time.time() - t0:.0f}s")
        page.wait_for_selector("video.n-video", timeout=300000)
        check("8 finished video appears", True, f"{time.time() - t0:.0f}s after create")
        v = page.evaluate("""async () => { const v = document.querySelector('video.n-video');
            if (v.readyState < 1) await new Promise(r => { v.onloadedmetadata = r; setTimeout(r, 15000); });
            v.muted = true; try { await v.play(); } catch (e) {}
            await new Promise(r => setTimeout(r, 11000));
            return {src: v.getAttribute('src'), w: v.videoWidth, h: v.videoHeight, dur: v.duration, t: v.currentTime, err: v.error && v.error.code}; }""")
        check("9 video plays in the frontend", not v["err"] and v["t"] > 2, f"{v['w']}x{v['h']}, {v['dur']:.1f}s, played {v['t']:.1f}s, {v['src']}")
        check("   vertical 1080x1920, 22s (hook 10 + body 12)", v["w"] == 1080 and v["h"] == 1920 and abs(v["dur"] - 22) < 0.4, v["dur"])
        shot("09_review")
        btn("썸네일 만들기").click()
        pause(3000)
        shot("10_thumbnail")
        check("10 thumbnail screen opens", page.get_by_role("button", name="영상").count() > 0 or "썸네일" in page.locator("body").inner_text())
    except Exception as e:
        check("flow ran to the end", False, str(e).splitlines()[0][:200])
        try:
            print("SCREEN TEXT:", page.locator("body").inner_text().replace("\n", " | ")[:600])
        except Exception:
            pass

    bad = [c for c in calls if c[2] >= 400]
    check("no failed API call", not bad, f"{len(calls)} calls, failed: {bad}")
    check("no page errors", not errors, "; ".join(errors)[:200])
    used = sorted({f"{m} {u}" for m, u, _ in calls if u.startswith("/v1/")})
    print("API used:", json.dumps(used, ensure_ascii=False))
    page.screenshot(path=os.path.join(out, "e2e_front_last.png"))
    video = page.video
    ctx.close()
    browser.close()
    dst = os.path.join(out, "e2e_front.webm")
    shutil.move(video.path(), dst)
    json.dump({"calls": calls, "results": results}, open(os.path.join(out, "e2e_front.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)

print(f"\nfrontend e2e: {len(results) - len(fails)}/{len(results)} passed" + (f"  FAILED: {fails}" if fails else ""))
sys.exit(1 if fails else 0)
