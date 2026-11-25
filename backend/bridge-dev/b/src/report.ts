// 프로젝트 하나의 모든 회차를 한 HTML로 만든다. 회차·시나리오·3D 명세는 접었다 펼 수 있다.
import { krw, PRICES, totals } from "./cost.js";
import type { RunRecord } from "./generate.js";
import type { Scene3D } from "./schema.js";

const esc = (s: unknown) =>
  String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]!);
const nl = (s: string) => esc(s).replace(/\n/g, "<br>");
const usd = (n: number | null) => (n === null ? "단가 미상" : `$${n.toFixed(n < 0.01 ? 4 : 3)}`);
const won = (n: number) => {
  const k = krw(n);
  return k === null ? "" : ` <span class="muted">(약 ${k.toLocaleString("ko-KR")}원)</span>`;
};
const num = (n: number) => n.toLocaleString("ko-KR");
export const dur = (ms: number) => {
  const s = Math.round(ms / 1000);
  return s < 60 ? `${s}초` : `${Math.floor(s / 60)}분 ${s % 60}초`;
};

function simBar(sim: number) {
  const inRange = sim >= 0.4 && sim <= 0.6;
  return `<span class="bar"><span class="fill${inRange ? " ok" : ""}" style="width:${Math.round(sim * 100)}%"></span></span><span class="mono">${sim.toFixed(2)}</span>`;
}

function pathChips(nodes: { word: string; sim_to_anchor: number }[], anchor: string) {
  const chips = nodes
    .map((n, i) => `<span class="chip${i === 0 ? " start" : ""}"><b>${i === 0 ? "시작" : `브리지 ${i}`}</b> ${esc(n.word)} <span class="mono">${n.sim_to_anchor.toFixed(2)}</span></span>`)
    .join('<span class="arrow">→</span>');
  return `<div class="path">${chips}<span class="arrow">→</span><span class="chip anchor"><b>앵커</b> ${esc(anchor)}</span></div>`;
}

function scene3dBlock(sc: Scene3D | undefined) {
  if (!sc) return `<p class="muted">3D 명세 없음</p>`;
  const motion = [...sc.motion]
    .sort((a, b) => a.from - b.from)
    .map(
      (m) => `<div class="tl-row"><div class="tl"><span style="left:${m.from * 100}%;width:${Math.max(2, (m.to - m.from) * 100)}%"></span></div><div>${esc(m.action)}</div></div>`
    )
    .join("");
  const objs = sc.objects
    .map((o) => `<li><span class="swatch" style="background:${esc(o.color)}"></span><b>${esc(o.name)}</b> — ${esc(o.build)}<br><span class="muted">${esc(o.material)} · ${esc(o.position)}</span></li>`)
    .join("");
  return `<details class="s3d"><summary>3D 장면 명세</summary>
    <p><b>보여 줄 사실</b> ${esc(sc.fact_shown)}</p>
    <ul class="objs">${objs}</ul>
    <div class="tl-wrap"><div class="tl-head"><span>0%</span><span>움직임</span><span>100%</span></div>${motion}</div>
    <p><b>카메라</b> ${esc(sc.camera)} · <b>조명</b> ${esc(sc.lighting)} · <b>배경</b> <span class="swatch" style="background:${esc(sc.background)}"></span>${esc(sc.background)}${
      sc.counter ? ` · <b>카운터</b> ${sc.counter.from} → ${sc.counter.to} ${esc(sc.counter.unit)}` : ""
    }</p></details>`;
}

type LegacyIdeation = { anchor: string; anchorFact: string; words?: { word: string; sim: number; info: number; usage?: number }[] };

function ideationBlock(run: RunRecord): string {
  const id = run.ideation as (RunRecord["ideation"] & LegacyIdeation) | null;
  if (!id) return `<p class="muted">유사도 검색 없이 생성한 회차입니다.</p>`;
  const head = `<p><b>앵커</b> ${esc(id.anchor)}<br><span class="muted">근거: ${esc(id.anchorFact)}${id.usageDomains ? ` · 용도 영역: ${esc(id.usageDomains.join(", "))}` : ""}</span></p>`;
  if (Array.isArray(id.seeds)) {
    const picked = new Set(run.response.scenarios.map((s) => s.ad_spec.story_seed).filter(Boolean));
    const rows = [...id.seeds]
      .sort((a, b) => b.score - a.score)
      .slice(0, 12)
      .map(
        (s) => `<tr${picked.has(s.word) ? ' class="picked"' : ""}><td class="num">${s.score.toFixed(3)}</td><td>${esc(s.word)}<br><span class="muted">${esc(s.arc)}</span></td>
          <td class="muted">${esc(s.lens)}</td><td>${simBar(s.sim)}</td><td class="num">${s.usage.toFixed(2)}</td><td class="num">${s.link.toFixed(2)}</td><td class="num">${s.info.toFixed(2)}</td></tr>`
      )
      .join("");
    const src = { new: "새 검색", reused: "저장된 검색 재사용 · 앵커 고정", expanded: "재사용 + 추가 검색 · 앵커 고정" }[run.ideationSource ?? "new"];
    return `<details class="sub"><summary>유사도 검색 (${src}) — 이야기 씨앗 ${id.seeds.length}개 · 후보 ${(run.seedCandidates ?? []).length}개 전달</summary>${head}
      <p class="muted">조건: 발단-앵커 0.40~0.60 · 용도 영역 0.35 이하 · 결말-앵커 연결 0.6 이상. 초록 줄이 고른 씨앗.</p>
      <div class="scroll"><table><thead><tr><th>점수</th><th>씨앗 · 흐름</th><th>관점</th><th>발단 유사도</th><th>용도</th><th>연결</th><th>흥미</th></tr></thead><tbody>${rows}</tbody></table></div></details>`;
  }
  // 예전 기록(단어 경로 방식)
  const words = (id.words ?? []).filter((w) => w.sim >= 0.4 && w.sim <= 0.6).sort((a, b) => b.info - a.info).slice(0, 10);
  return `<details class="sub"><summary>유사도 검색 (예전 방식: 단어 경로)</summary>${head}
    <table><thead><tr><th>시작 후보</th><th>info</th><th>앵커 유사도</th></tr></thead><tbody>${words
      .map((w) => `<tr><td>${esc(w.word)}</td><td class="num">${w.info.toFixed(2)}</td><td>${simBar(w.sim)}</td></tr>`)
      .join("")}</tbody></table></details>`;
}

function roundBlock(run: RunRecord, open: boolean) {
  const r = run.response;
  const allOk = run.checks.every((c) => c.errors.length === 0);
  const t = totals(run.steps); // 저장된 합계 대신 단계에서 다시 계산(병렬 단계 시간 규칙 반영)

  const costRows = run.steps
    .map((s) => `<tr><td>${esc(s.step)}</td><td class="mono">${esc(s.model)}</td><td class="num">${num(s.inputTokens)}</td><td class="num">${num(s.outputTokens)}</td><td class="num">${usd(s.costUsd)}</td><td class="num">${s.ms ? dur(s.ms) : "—"}</td></tr>`)
    .join("");

  const ideation = ideationBlock(run);

  const cards = r.scenarios
    .map((s, i) => {
      const c = run.checks[i] ?? { errors: [], warnings: [] };
      const sc = run.cuts?.find((x) => x.scenario_id === s.scenario_id);
      const cutOf = (order: number) => sc?.beats.find((b) => b.order === order);
      const thumbs = (order: number) => {
        const cb = cutOf(order);
        if (!cb) return "";
        const imgs = cb.images.map((p) => `<a href="${esc(p)}" target="_blank"><img src="${esc(p)}" alt="장면 ${order} 컷" loading="lazy"></a>`).join("");
        const tag = cb.ok ? "" : `<div class="cutfail">생성 실패 → 기본 도형${cb.error ? `: ${esc(cb.error.split("\n")[0].slice(0, 120))}` : ""}</div>`;
        return `<div class="cuts">${imgs}</div>${tag}${cb.code ? `<a class="muted codelink" href="${esc(cb.code)}" target="_blank">장면 코드</a>` : ""}`;
      };
      const strip = sc
        ? `<div class="strip">${[...s.beats]
            .sort((a, b) => a.order - b.order)
            .map((b) => {
              const cb = cutOf(b.order);
              const mid = cb?.images[1] ?? cb?.images[0];
              return mid ? `<figure><img src="${esc(mid)}" alt="장면 ${b.order}" loading="lazy"><figcaption>${b.order}. ${esc(b.role)} · ${b.duration_sec}초${cb && !cb.ok ? " ⚠" : ""}</figcaption></figure>` : "";
            })
            .join("")}</div>`
        : "";
      const beats = [...s.beats]
        .sort((a, b) => a.order - b.order)
        .map(
          (b) => `<tr><td class="num">${b.order}</td><td><b>${esc(b.role)}</b><br><span class="muted">${b.duration_sec}초</span></td>
            <td>${nl(b.narration)}</td><td class="cap">${nl(b.caption)}</td><td>${esc(b.visual)}${thumbs(b.order)}${scene3dBlock(b.scene3d)}</td></tr>`
        )
        .join("");
      const checks =
        (c.errors.length || c.warnings.length
          ? `<ul class="checks">${c.errors.map((e) => `<li class="err">✗ ${esc(e)}</li>`).join("")}${c.warnings.map((w) => `<li class="warn">△ ${esc(w)}</li>`).join("")}</ul>`
          : `<p class="okline">✓ 규칙 검사 통과</p>`);
      const facts = s.ad_spec.fact_sources
        .map((f) => `<li><span class="tag${f.status.includes("확인 필요") ? " warn" : ""}">${esc(f.status)}</span> ${esc(f.claim)}</li>`)
        .join("");
      return `<details class="card" open><summary><span class="title">${esc(s.hook_title)}</span>
          <span class="meta">${s.hook_duration_sec}초 · 장면 ${s.beats.length}개 · <span class="mono">${esc(s.scenario_id)}</span></span>
          <span class="badge ${c.errors.length ? "bad" : "good"}">${c.errors.length ? `위반 ${c.errors.length}` : "통과"}</span></summary>
        ${(() => {
          const v = run.videos?.find((x) => x.scenario_id === s.scenario_id);
          if (!v) return "";
          const rows = v.scenes
            .map((x) => `<tr><td class="num">${x.order}</td><td class="num">${x.planned}초</td><td class="num">${x.final}초</td><td class="num">${x.voiceSec ?? "—"}초</td><td>${x.usedGen ? "생성 코드" : "기본 도형"}</td></tr>`)
            .join("");
          return `<div class="video"><video controls preload="metadata" src="${esc(v.file)}"></video>
            <div><b>훅 영상</b> ${v.seconds}초 · <a href="${esc(v.file)}" target="_blank">mp4 열기</a>
            <table><thead><tr><th>장면</th><th>계획</th><th>최종</th><th>음성</th><th>3D</th></tr></thead><tbody>${rows}</tbody></table>
            <p class="muted">음성이 장면보다 길면 장면이 늘어납니다(+0.25초 여유).</p></div></div>`;
        })()}
        ${strip}
        ${pathChips(s.ad_spec.bridge_path, s.ad_spec.anchor)}
        <p class="muted">시작 유사도 ${s.ad_spec.hook_similarity_score.toFixed(2)} · 인접 최소 ${s.ad_spec.adjacent_min_sim.toFixed(2)} · 숫자 실 ${esc(s.ad_spec.number_thread)} · ${esc(s.replacement_test_note)}</p>
        <div class="scroll"><table class="beats"><thead><tr><th>#</th><th>장면</th><th>나레이션</th><th>자막</th><th>화면 · 3D</th></tr></thead><tbody>${beats}</tbody></table></div>
        ${checks}
        <details class="sub"><summary>사실 출처 ${s.ad_spec.fact_sources.length}개</summary><ul class="facts">${facts}</ul></details>
      </details>`;
    })
    .join("");

  return `<details class="round"${open ? " open" : ""}>
    <summary><span class="rnum">${r.round}회차</span>
      <span class="meta">시나리오 ${r.scenarios.length}개 · ${usd(t.costUsd)}${t.unknownPrice ? "+" : ""} · ⏱ ${t.ms ? dur(t.ms) : "기록 없음"} · ${new Date(run.createdAt).toLocaleString("ko-KR")}</span>
      <span class="badge ${allOk ? "good" : "bad"}">${allOk ? "검사 통과" : "위반 있음"}</span></summary>
    <div class="round-body">
      ${cards}
      <details class="sub"><summary>비용 — 토큰 ${num(t.inputTokens)} 입력 / ${num(t.outputTokens)} 출력 · ${usd(t.costUsd)}${won(t.costUsd)} · ⏱ ${dur(t.ms)}</summary>
        <div class="scroll"><table><thead><tr><th>단계</th><th>모델</th><th>입력 토큰</th><th>출력 토큰</th><th>비용</th><th>시간</th></tr></thead>
        <tbody>${costRows}<tr class="total"><td>합계</td><td></td><td class="num">${num(t.inputTokens)}</td><td class="num">${num(t.outputTokens)}</td><td class="num">${usd(t.costUsd)}</td><td class="num">${dur(t.ms)}</td></tr></tbody></table></div>
        <p class="muted">시나리오 생성 ${run.attempts}회 시도 · 생성 모델 ${esc(run.modelId)} · 아이디어 모델 ${esc(run.ideaModelId)}</p>
      </details>
      ${ideation}
    </div></details>`;
}

export function renderReport(runs: RunRecord[], productName: string): string {
  const sorted = [...runs].sort((a, b) => b.response.round - a.response.round);
  const all = totals(sorted.flatMap((r) => r.steps));
  const scenarioCount = sorted.reduce((a, r) => a + r.response.scenarios.length, 0);
  const priceNote = Object.entries(PRICES)
    .map(([m, p]) => `${m} $${p.input}/$${p.output}`)
    .join(" · ");
  const project = sorted[0]?.response.project_id ?? "";

  return `<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>B 훅 시나리오 — ${esc(project)}</title>
<style>
:root{--bg:#f6f5f2;--card:#fff;--ink:#1d1c1a;--muted:#6f6b65;--line:#e3e0da;--accent:#e8322a;--good:#1f7a4d;--goodbg:#e4f3ea;--badbg:#fde8e6;--warnbg:#fff4d6;--warn:#8a6100;--chip:#f0eee9}
@media (prefers-color-scheme:dark){:root{--bg:#141413;--card:#1e1d1b;--ink:#ecebe8;--muted:#a19d96;--line:#33312d;--good:#5fc391;--goodbg:#173326;--badbg:#3a1a17;--warnbg:#33290f;--warn:#e7c05a;--chip:#2a2825}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.6 "Pretendard","Apple SD Gothic Neo","Malgun Gothic",system-ui,sans-serif}
main{max-width:1180px;margin:0 auto;padding:28px 16px 60px}
header h1{font-size:22px;margin:0 0 4px}header p{margin:0;color:var(--muted)}
.stats{display:flex;flex-wrap:wrap;gap:10px;margin:18px 0 8px}.stat{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px 14px;min-width:140px}
.stat b{display:block;font-size:20px}.stat span{color:var(--muted);font-size:13px}
.toolbar{display:flex;gap:8px;margin:14px 0}.toolbar button{border:1px solid var(--line);background:var(--card);color:var(--ink);border-radius:8px;padding:6px 12px;cursor:pointer;font:inherit;font-size:13px}
details>summary{cursor:pointer;list-style:none}details>summary::-webkit-details-marker{display:none}
details>summary::before{content:"▸";display:inline-block;width:1em;color:var(--muted);transition:transform .15s}details[open]>summary::before{transform:rotate(90deg)}
.round{background:var(--card);border:1px solid var(--line);border-radius:14px;margin:14px 0;overflow:hidden}
.round>summary{display:flex;align-items:center;gap:12px;flex-wrap:wrap;padding:14px 18px;font-size:16px}.rnum{font-weight:700}
.round-body{padding:0 18px 18px}.meta{color:var(--muted);font-size:13px}
.badge{margin-left:auto;font-size:12px;border-radius:999px;padding:2px 10px;font-weight:600}.badge.good{background:var(--goodbg);color:var(--good)}.badge.bad{background:var(--badbg);color:var(--accent)}
.card{border:1px solid var(--line);border-radius:12px;margin:12px 0;padding:0 14px 12px}.card>summary{display:flex;align-items:center;gap:10px;flex-wrap:wrap;padding:12px 0}
.card .title{font-weight:700;font-size:16px}
.path{display:flex;flex-wrap:wrap;align-items:center;gap:6px;margin:4px 0 8px}.chip{background:var(--chip);border-radius:8px;padding:4px 10px;font-size:13px}
.chip b{font-weight:600;color:var(--muted);margin-right:4px}.chip.start{outline:1px solid var(--line)}.chip.anchor{background:var(--accent);color:#fff}.chip.anchor b{color:#ffd9d6}.arrow{color:var(--muted)}
.scroll{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:14px;margin:6px 0}th,td{border-bottom:1px solid var(--line);padding:8px;text-align:left;vertical-align:top}
th{color:var(--muted);font-weight:600;font-size:12px;white-space:nowrap}td.num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
table.beats td:nth-child(2){min-width:104px}table.beats td:nth-child(3){min-width:220px}table.beats td:nth-child(5){min-width:260px}.cap{white-space:nowrap;font-weight:600}
tr.total td{font-weight:700}tr.picked td{background:var(--goodbg)}
.mono{font-family:ui-monospace,Consolas,monospace;font-size:12px}.muted{color:var(--muted)}
.bar{display:inline-block;width:70px;height:6px;background:var(--chip);border-radius:3px;margin-right:6px;vertical-align:middle;overflow:hidden}.fill{display:block;height:100%;background:var(--muted)}.fill.ok{background:var(--good)}
.s3d{margin-top:8px;border-top:1px dashed var(--line);padding-top:6px}.s3d summary{font-size:13px;color:var(--muted)}.s3d p{margin:6px 0;font-size:13px}
.objs{margin:6px 0;padding-left:18px;font-size:13px}.swatch{display:inline-block;width:10px;height:10px;border-radius:2px;border:1px solid var(--line);margin-right:5px;vertical-align:middle}
.tl-wrap{font-size:13px}.tl-head{display:flex;justify-content:space-between;color:var(--muted);font-size:11px;width:120px}.tl-row{display:grid;grid-template-columns:120px 1fr;gap:10px;align-items:center;margin:3px 0}
.tl{position:relative;height:8px;background:var(--chip);border-radius:4px}.tl span{position:absolute;top:0;height:100%;background:var(--accent);border-radius:4px}
.checks{padding-left:0;list-style:none;margin:8px 0}.checks li{padding:4px 10px;border-radius:6px;margin:3px 0;font-size:13px}.err{background:var(--badbg)}.warn{background:var(--warnbg);color:var(--warn)}
.okline{color:var(--good);font-weight:600;margin:8px 0}
.sub{margin:10px 0}.sub>summary{font-weight:600;font-size:14px;padding:6px 0}.sub h4{margin:12px 0 4px;font-size:13px;color:var(--muted)}
.facts{padding-left:0;list-style:none}.facts li{margin:4px 0;font-size:13px}.tag{font-size:11px;border-radius:4px;padding:1px 6px;background:var(--chip)}.tag.warn{background:var(--warnbg);color:var(--warn)}
footer{color:var(--muted);font-size:12px;margin-top:24px}
.video{display:flex;gap:16px;flex-wrap:wrap;align-items:flex-start;margin:4px 0 12px}.video video{width:220px;aspect-ratio:9/16;border-radius:12px;background:#000}
.video>div{flex:1;min-width:220px;font-size:14px}.video table{max-width:360px}
.strip{display:flex;gap:10px;overflow-x:auto;padding:4px 0 10px}.strip figure{margin:0;flex:none;width:150px}
.strip img{width:150px;aspect-ratio:9/16;object-fit:cover;border-radius:10px;border:1px solid var(--line);display:block;background:#000}
.strip figcaption{font-size:12px;color:var(--muted);margin-top:4px}
.cuts{display:flex;gap:6px;margin:8px 0 2px}.cuts img{width:64px;aspect-ratio:9/16;object-fit:cover;border-radius:6px;border:1px solid var(--line);display:block;background:#000}
.cutfail{font-size:12px;color:var(--warn);background:var(--warnbg);border-radius:6px;padding:2px 8px;margin:4px 0}.codelink{font-size:12px}
</style></head><body><main>
<header><h1>B 훅 시나리오 — ${esc(productName)}</h1><p class="mono">${esc(project)}</p></header>
<div class="stats">
  <div class="stat"><b>${sorted.length}</b><span>회차</span></div>
  <div class="stat"><b>${scenarioCount}</b><span>시나리오</span></div>
  <div class="stat"><b>${usd(all.costUsd)}${all.unknownPrice ? "+" : ""}</b><span>누적 비용${won(all.costUsd)}</span></div>
  <div class="stat"><b>${dur(all.ms)}</b><span>누적 소요 시간 (API 응답 대기 합계)</span></div>
  <div class="stat"><b>${num(all.inputTokens + all.outputTokens)}</b><span>누적 토큰 (입력 ${num(all.inputTokens)} · 출력 ${num(all.outputTokens)})</span></div>
</div>
<div class="toolbar"><button onclick="document.querySelectorAll('details.round').forEach(d=>d.open=true)">회차 모두 펼치기</button><button onclick="document.querySelectorAll('details.round').forEach(d=>d.open=false)">회차 모두 접기</button></div>
${sorted.map((r, i) => roundBlock(r, i === 0)).join("")}
<footer>비용은 표준 단가(USD/100만 토큰: ${esc(priceNote)})로 계산한 추정치이며 캐시 할인은 반영하지 않았습니다. 실제 청구액은 Claude Console의 Usage에서 확인하세요. 유사도는 임베딩이 아니라 Claude가 같은 기준표로 매긴 추정치입니다.</footer>
</main></body></html>`;
}
