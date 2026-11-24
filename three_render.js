// 훅컷 · Three.js 렌더러
// 블렌더 없이 브라우저 GPU(WebGL)로 같은 영상을 3D로 그리고, 소리까지 담아 녹화한다.
// 페이지(hookcut.html)의 window.HookCut 에서 지금 고른 기획·사진·본편 영상을 읽어 온다.
(() => {
"use strict";
const $ = (id) => document.getElementById(id);
if (!window.THREE || !window.HookCut) {
  const st = $("threeStatus");
  if (st) st.textContent = "Three.js 를 불러오지 못했어요. 인터넷 연결을 확인하고 새로고침해 주세요.";
  return;
}
const THREE = window.THREE;

// ---------- 좌표: 페이지의 540×960 캔버스 좌표 → 월드 (1px = 0.01) ----------
const FW = 5.4, FH = 9.6, FOV = 30;
const DIST = (FH / 2) / Math.tan((FOV / 2) * Math.PI / 180);   // z=0 평면이 화면을 꽉 채우는 거리
const wx = (px) => (px / 540 - 0.5) * FW;
const wy = (py) => (0.5 - py / 960) * FH;
const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
const easeOut = (x) => 1 - Math.pow(1 - clamp(x), 3);
const easeOutBack = (x) => { x = clamp(x); const c1 = 1.70158, c3 = c1 + 1; return 1 + c3 * Math.pow(x - 1, 3) + c1 * Math.pow(x - 1, 2); };
const lerp = (a, b, k) => a + (b - a) * k;

// ---------- 글자 텍스처: 한글 폰트로 캔버스에 그려 평면에 붙인다 ----------
// depth: 아래로 겹겹이 그려 입체 글자처럼 보이게 하는 층 수
function textCanvas(text, o) {
  const k = o.k;                       // 해상도 배율
  const size = o.size * k, pad = Math.round(size * 0.5);
  const font = `${o.weight || "900"} ${size}px ${o.font}`;
  const meas = document.createElement("canvas").getContext("2d");
  meas.font = font;
  // 줄바꿈 (maxW 는 540 좌표 기준)
  const maxW = (o.maxW || 470) * k, lines = [];
  String(text).split("\n").forEach((para) => {
    let cur = "";
    for (const word of para.split(" ")) {
      const tryLine = cur ? cur + " " + word : word;
      if (meas.measureText(tryLine).width > maxW && cur) { lines.push(cur); cur = word; } else cur = tryLine;
    }
    if (cur) lines.push(cur);
  });
  // 한 단어가 너무 길면 글자 단위로 자른다
  const fixed = [];
  lines.forEach((l) => {
    if (meas.measureText(l).width <= maxW) { fixed.push(l); return; }
    let cur = "";
    for (const ch of l) { if (meas.measureText(cur + ch).width > maxW && cur) { fixed.push(cur); cur = ch; } else cur += ch; }
    if (cur) fixed.push(cur);
  });
  const lh = size * 1.18;
  const tw = Math.max(1, ...fixed.map((l) => meas.measureText(l).width));
  const depth = (o.depth || 0) * k;
  const bw = o.box ? (o.boxW ? o.boxW * k : tw + size * 1.2) : tw;
  const w = Math.ceil(bw + pad * 2 + depth), h = Math.ceil(lh * fixed.length + pad * 2 + depth + (o.box ? size * 0.5 : 0));
  const c = document.createElement("canvas"); c.width = w; c.height = h;
  const g = c.getContext("2d");
  g.font = font; g.textAlign = "center"; g.textBaseline = "middle"; g.lineJoin = "round";
  if (o.box) {
    g.fillStyle = o.box;
    const r = (o.radius || 10) * k, x = pad, y = pad, bh = h - pad * 2 - depth;
    g.beginPath(); g.roundRect ? g.roundRect(x, y, bw, bh, r) : g.rect(x, y, bw, bh); g.fill();
  }
  const cx = pad + bw / 2, top = pad + (o.box ? size * 0.25 : 0) + lh / 2;
  const draw = (dx, dy, fill, stroke) => fixed.forEach((l, i) => {
    const y = top + i * lh + dy;
    if (stroke && o.strokeW) { g.strokeStyle = stroke; g.lineWidth = o.strokeW * k; g.strokeText(l, cx + dx, y); }
    if (fill) { g.fillStyle = fill; g.fillText(l, cx + dx, y); }
  });
  for (let d = depth; d > 0; d -= Math.max(1, k)) draw(d, d, o.depthColor || "#000", o.depthColor || "#000");   // 입체 옆면
  if (o.shadow) { g.save(); g.shadowColor = "rgba(0,0,0,.55)"; g.shadowBlur = 18 * k; g.shadowOffsetY = 6 * k; draw(0, 0, o.color, o.stroke); g.restore(); }
  draw(0, 0, o.color, o.stroke);
  return { canvas: c, w: w / k, h: h / k };   // w,h 는 540 좌표 기준 크기
}

function textMesh(text, o) {
  const tc = textCanvas(text, o);
  const tex = new THREE.CanvasTexture(tc.canvas);
  tex.minFilter = THREE.LinearFilter; tex.anisotropy = 4;
  if (THREE.sRGBEncoding) tex.encoding = THREE.sRGBEncoding;
  const m = new THREE.Mesh(new THREE.PlaneGeometry(tc.w / 100, tc.h / 100),
    new THREE.MeshBasicMaterial({ map: tex, transparent: true, depthWrite: false }));
  m.userData.dispose = () => { tex.dispose(); m.geometry.dispose(); m.material.dispose(); };
  return m;
}

// 사진을 정해진 크기에 꽉 채우기 (가운데 기준으로 잘라 냄)
function coverTexture(src, boxW, boxH) {
  const tex = new THREE.Texture(src);
  tex.needsUpdate = true; tex.minFilter = THREE.LinearFilter;
  if (THREE.sRGBEncoding) tex.encoding = THREE.sRGBEncoding;
  const iw = src.naturalWidth || src.videoWidth || src.width, ih = src.naturalHeight || src.videoHeight || src.height;
  fitUV(tex, iw, ih, boxW / boxH, "cover");
  return tex;
}
function fitUV(tex, iw, ih, boxAspect, mode) {
  const ia = iw / Math.max(1, ih);
  tex.repeat.set(1, 1); tex.offset.set(0, 0);
  if (mode !== "cover") return;
  if (ia > boxAspect) { const r = boxAspect / ia; tex.repeat.set(r, 1); tex.offset.set((1 - r) / 2, 0); }
  else { const r = ia / boxAspect; tex.repeat.set(1, r); tex.offset.set(0, (1 - r) / 2); }
}

function radialTexture(inner, outer, size = 256) {
  const c = document.createElement("canvas"); c.width = c.height = size;
  const g = c.getContext("2d"), gr = g.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2);
  gr.addColorStop(0, inner); gr.addColorStop(1, outer);
  g.fillStyle = gr; g.fillRect(0, 0, size, size);
  const t = new THREE.CanvasTexture(c); return t;
}
function vignetteTexture() {
  const c = document.createElement("canvas"); c.width = 108; c.height = 192;
  const g = c.getContext("2d"), gr = g.createRadialGradient(54, 96, 40, 54, 96, 130);
  gr.addColorStop(0, "rgba(0,0,0,0)"); gr.addColorStop(1, "rgba(0,0,0,0.55)");
  g.fillStyle = gr; g.fillRect(0, 0, 108, 192);
  return new THREE.CanvasTexture(c);
}
function plane(w, h, mat) { return new THREE.Mesh(new THREE.PlaneGeometry(w, h), mat); }
// 단색: 출력이 sRGB 라서 색 값을 선형으로 바꿔 넣어야 원래 색(예: #2B54FF)이 그대로 나온다
const col = (hex) => new THREE.Color(hex).convertSRGBToLinear();
function basic(color, extra) { return new THREE.MeshBasicMaterial(Object.assign({ color: col(color) }, extra || {})); }

// 흐린 영상 배경 (가우시안 비슷하게 25점 샘플)
function blurMaterial(tex, darkness) {
  return new THREE.ShaderMaterial({
    uniforms: { map: { value: tex }, rep: { value: tex.repeat }, off: { value: tex.offset }, step: { value: new THREE.Vector2(1 / 160, 1 / 160) }, dark: { value: darkness } },
    vertexShader: "varying vec2 vUv; void main(){ vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position,1.0); }",
    fragmentShader: `
      uniform sampler2D map; uniform vec2 rep; uniform vec2 off; uniform vec2 step; uniform float dark; varying vec2 vUv;
      void main(){
        vec2 uv = vUv * rep + off; vec4 acc = vec4(0.0); float wsum = 0.0;
        for (int x = -2; x <= 2; x++) for (int y = -2; y <= 2; y++) {
          float w = exp(-float(x*x + y*y) / 4.0);
          acc += texture2D(map, uv + vec2(float(x), float(y)) * step * 3.0) * w; wsum += w;
        }
        gl_FragColor = vec4((acc / wsum).rgb * dark, 1.0);
      }`
  });
}

// ---------- 효과음 (블렌더 쪽 sfx.py 와 같은 소리를 Web Audio 로 합성) ----------
function playSfx(ac, out, name, when, vol) {
  const g = ac.createGain(); g.connect(out);
  const env = (peak, dur, curve = "exp") => {
    g.gain.setValueAtTime(0.0001, when);
    g.gain.linearRampToValueAtTime(peak * vol, when + 0.008);
    if (curve === "exp") g.gain.exponentialRampToValueAtTime(0.0001, when + dur);
    else g.gain.linearRampToValueAtTime(0.0001, when + dur);
  };
  if (name === "pop") {
    const o = ac.createOscillator(); o.type = "sine";
    o.frequency.setValueAtTime(500, when); o.frequency.exponentialRampToValueAtTime(1900, when + 0.09);
    o.connect(g); env(0.7, 0.1); o.start(when); o.stop(when + 0.12);
  } else if (name === "boing") {
    const o = ac.createOscillator(), lfo = ac.createOscillator(), lg = ac.createGain();
    o.type = "sine"; o.frequency.setValueAtTime(420, when); o.frequency.exponentialRampToValueAtTime(190, when + 0.55);
    lfo.frequency.value = 14; lg.gain.value = 55; lfo.connect(lg); lg.connect(o.frequency);
    o.connect(g); env(0.6, 0.58); o.start(when); lfo.start(when); o.stop(when + 0.6); lfo.stop(when + 0.6);
  } else if (name === "ding") {
    [1320, 2640, 3960].forEach((f, i) => {
      const o = ac.createOscillator(), og = ac.createGain(); o.frequency.value = f; og.gain.value = [1, 0.5, 0.25][i];
      o.connect(og); og.connect(g); o.start(when); o.stop(when + 1.0);
    });
    env(0.35, 0.95);
  } else if (name === "whoosh") {
    const n = Math.floor(ac.sampleRate * 0.5), buf = ac.createBuffer(1, n, ac.sampleRate), d = buf.getChannelData(0);
    for (let i = 0; i < n; i++) d[i] = Math.random() * 2 - 1;
    const s = ac.createBufferSource(), f = ac.createBiquadFilter(); s.buffer = buf; f.type = "bandpass"; f.Q.value = 0.8;
    f.frequency.setValueAtTime(300, when); f.frequency.exponentialRampToValueAtTime(2800, when + 0.25); f.frequency.exponentialRampToValueAtTime(500, when + 0.45);
    s.connect(f); f.connect(g);
    g.gain.setValueAtTime(0.0001, when); g.gain.linearRampToValueAtTime(0.6 * vol, when + 0.22); g.gain.linearRampToValueAtTime(0.0001, when + 0.45);
    s.start(when); s.stop(when + 0.5);
  } else if (name === "scratch") {
    // 찌익: 레코드를 긁듯 음이 급하게 떨어지는 소리 (매치컷 직전)
    const o = ac.createOscillator(); o.type = "sawtooth";
    o.frequency.setValueAtTime(1500, when); o.frequency.exponentialRampToValueAtTime(90, when + 0.2);
    const n = Math.floor(ac.sampleRate * 0.22), buf = ac.createBuffer(1, n, ac.sampleRate), d = buf.getChannelData(0);
    for (let i = 0; i < n; i++) d[i] = (Math.random() * 2 - 1) * 0.7;
    const s = ac.createBufferSource(); s.buffer = buf;
    o.connect(g); s.connect(g); env(0.5, 0.22, "lin"); o.start(when); s.start(when); o.stop(when + 0.23); s.stop(when + 0.23);
  } else if (name === "stop") {
    const o = ac.createOscillator(), o3 = ac.createOscillator(), g3 = ac.createGain();
    o.frequency.setValueAtTime(180, when); o.frequency.exponentialRampToValueAtTime(72, when + 0.25);
    o3.frequency.setValueAtTime(540, when); o3.frequency.exponentialRampToValueAtTime(216, when + 0.25); g3.gain.value = 0.3;
    o.connect(g); o3.connect(g3); g3.connect(g); env(0.9, 0.26); o.start(when); o3.start(when); o.stop(when + 0.3); o3.stop(when + 0.3);
  }
}

// ---------- 장면 만들기 ----------
function buildScene(snap, opts) {
  const c = snap.concept, info = snap.info, T = snap.T, F = snap.fonts, k = opts.k;
  const problem = c.template === "problem", bTone = problem && c.tone === "b";
  const tHook = T.hook, tBridge = tHook + T.bridge, tEnd = tBridge + snap.adLen, total = tEnd + T.end;
  const scene = new THREE.Scene();
  scene.background = col("#0c0d10");
  const cam = new THREE.PerspectiveCamera(FOV, 9 / 16, 0.1, 200);
  cam.position.set(0, 0, DIST);
  const disposers = [];
  const track = (m) => { if (m.userData && m.userData.dispose) disposers.push(m.userData.dispose); return m; };
  const sections = [];   // {from, to, group, update(t, lt)}
  const sfx = [];        // [time, name, vol]

  // 은은한 빛망울 (전환·엔딩)
  const bokehTex = radialTexture("rgba(255,236,200,1)", "rgba(255,236,200,0)");
  function bokeh(group, n, seed) {
    const list = [];
    let s = seed;
    const rnd = () => (s = (s * 9301 + 49297) % 233280) / 233280;
    for (let i = 0; i < n; i++) {
      const sz = 0.25 + rnd() * 0.6;
      const m = new THREE.Sprite(new THREE.SpriteMaterial({ map: bokehTex, transparent: true, opacity: 0.35 + rnd() * 0.4, depthWrite: false, blending: THREE.AdditiveBlending,
        color: new THREE.Color().setHSL(0.08 + rnd() * 0.08, 0.8, 0.7).convertSRGBToLinear() }));
      m.scale.set(sz, sz, 1);
      const p = { x: (rnd() - 0.5) * 7, y: (rnd() - 0.5) * 11, z: -1 - rnd() * 3, ph: rnd() * 6, sp: 0.2 + rnd() * 0.4 };
      m.position.set(p.x, p.y, p.z); group.add(m); list.push([m, p]);
    }
    return (t) => list.forEach(([m, p]) => { m.position.y = p.y + Math.sin(t * p.sp + p.ph) * 0.25; m.position.x = p.x + Math.cos(t * p.sp * 0.7 + p.ph) * 0.15; });
  }

  // ===== 1. 훅 =====
  if (problem) {
    const per = tHook / 3;
    const vig = vignetteTexture();
    for (let kx = 0; kx < 3; kx++) {
      const g = new THREE.Group(); scene.add(g);
      const fi = kx * per, fe = kx === 2 ? tHook : fi + per;
      const img = snap.hookPhotos[kx % 3];
      // 사진: 화면보다 조금 크게, 뒤쪽에 두어 카메라가 움직일 때 깊이감(시차)이 생기게
      const pw = FW * 1.18, ph = FH * 1.18;
      const photo = img ? plane(pw, ph, new THREE.MeshBasicMaterial({ map: coverTexture(img, pw, ph) })) : plane(pw, ph, basic("#333"));
      photo.position.z = -0.6; g.add(photo);
      if (kx === 2) photo.material.color = new THREE.Color(0.86, 0.86, 0.86);   // 마지막 컷은 살짝 어둡게 (정지 화면)
      const vg = plane(FW * 1.1, FH * 1.1, new THREE.MeshBasicMaterial({ map: vig, transparent: true, depthWrite: false })); vg.position.z = 0.02; g.add(vg);
      const tag = track(textMesh(`CUT ${kx + 1}`, { k, size: 22, font: F.body, weight: "700", color: "#E6E8EE", box: "rgba(14,15,18,.85)", radius: 8 }));
      tag.position.set(wx(452), wy(118), 0.3); g.add(tag);
      const two = c.hook.length >= 6, l1 = two ? c.hook[2 * kx] : c.hook[kx], l2 = two ? c.hook[2 * kx + 1] : "";
      const t1 = fi + 0.2, t2 = fi + per / 2, tSt = fi + per * 0.32;
      let cap, cap2, stk = null, tilt = [-0.05, 0.04, -0.03][kx];
      if (bTone) {
        cap = track(textMesh(l1 || "", { k, size: 46, font: F.display, color: "#FFE14D", stroke: "#111", strokeW: 9, depth: 5, depthColor: "#111", maxW: 400 }));
        cap.position.set(0, wy(640), 0.5); cap.rotation.z = tilt; g.add(cap);
        if (l2) { cap2 = track(textMesh(l2, { k, size: 33, font: F.display, color: "#fff", stroke: "#111", strokeW: 8, depth: 4, depthColor: "#111", maxW: 400 }));
          cap2.position.set(0, wy(775), 0.5); cap2.rotation.z = -tilt * 0.7; g.add(cap2); }
        const st = (c.stickers || [])[kx];
        if (st) { stk = track(textMesh(st, { k, size: 50, font: F.display, color: "#FF4D6D", stroke: "#fff", strokeW: 8, depth: 4, depthColor: "#b3243f", maxW: 300 }));
          stk.position.set(wx(kx % 2 ? 150 : 390), wy(300), 0.6); g.add(stk); }
        sfx.push([t1, "pop", 0.8]); if (l2) sfx.push([t2, "boing", 0.7]); if (stk) sfx.push([tSt, "pop", 0.6]); if (kx === 2) sfx.push([fi + 0.03, "stop", 0.9]);
      } else {
        cap = track(textMesh(l1 || "", { k, size: 42, font: F.body, weight: "900", color: "#fff", box: "rgba(14,15,18,.9)", boxW: 500, radius: 10, maxW: 460 }));
        cap.position.set(0, wy(740), 0.4); g.add(cap);
        if (l2) { cap2 = track(textMesh(l2, { k, size: 32, font: F.body, weight: "700", color: "#E6E8EE", box: "rgba(14,15,18,.85)", boxW: 440, radius: 10, maxW: 410 }));
          cap2.position.set(0, wy(850), 0.4); g.add(cap2); }
      }
      sections.push({ from: fi, to: fe, group: g, update(t) {
        const lt = t - fi;
        // 카메라: 천천히 다가가고(마지막 컷은 멈춤), B급이면 둘째 줄과 함께 확 당겨짐 + 정지 컷 흔들림
        let z = DIST - (kx < 2 ? 0.9 * (lt / per) : 0);
        if (bTone && l2) z -= 2.6 * easeOut((t - t2) / 0.1) * (t >= t2 ? 1 : 0);
        let sx = Math.sin(lt * 0.6) * 0.06, sy = 0;
        if (bTone && kx === 2 && lt < 0.25) { sx += Math.sin(lt * 90) * 0.06 * (1 - lt / 0.25); sy = Math.cos(lt * 70) * 0.05 * (1 - lt / 0.25); }
        cam.position.set(sx, sy, z);
        if (bTone) {
          const s1 = t >= t1 ? easeOutBack((t - t1) / 0.28) : 0; cap.scale.setScalar(Math.max(0.001, s1)); cap.visible = t >= t1;
          if (cap2) { const s2 = t >= t2 ? easeOutBack((t - t2) / 0.25) : 0; cap2.scale.setScalar(Math.max(0.001, s2)); cap2.visible = t >= t2; }
          if (stk) { const s3 = t >= tSt ? easeOutBack((t - tSt) / 0.25) : 0; stk.scale.setScalar(Math.max(0.001, s3)); stk.visible = t >= tSt;
            stk.rotation.z = (kx % 2 ? 0.16 : -0.16) + Math.sin(t * 6) * 0.05; }
        } else {
          cap.visible = t >= t1; if (cap2) cap2.visible = t >= t2;
          cap.material.opacity = clamp((t - t1) / 0.15); if (cap2) cap2.material.opacity = clamp((t - t2) / 0.15);
        }
      } });
    }
  } else {
    // 다른 템플릿의 훅: 페이지의 2D 미리보기를 그대로 텍스처로 (살짝 기울여 3D 무대처럼)
    const g = new THREE.Group(); scene.add(g);
    const tex = new THREE.CanvasTexture(window.HookCut.drawFrame2D(0)); tex.minFilter = THREE.LinearFilter;
    const p = plane(FW, FH, new THREE.MeshBasicMaterial({ map: tex })); g.add(p);
    sections.push({ from: 0, to: tHook, group: g, update(t) {
      window.HookCut.drawFrame2D(t); tex.needsUpdate = true;
      cam.position.set(Math.sin(t * 0.5) * 0.08, 0, DIST - 0.6 * (t / tHook));
    } });
  }

  // ===== 2. 브릿지 =====
  {
    const g = new THREE.Group(); scene.add(g);
    const bg = plane(FW * 3, FH * 2, basic("#2B54FF")); bg.position.z = -3; g.add(bg);
    const stripes = [];
    for (let i = 0; i < 12; i++) {
      const s = plane(0.55, 16, basic(i % 2 ? "#3D63FF" : "#1E40E0")); s.rotation.z = 0.35; s.position.set(-7 + i * 1.2, 0, -2.5 - (i % 3) * 0.2); g.add(s); stripes.push(s);
    }
    const upd = bokeh(g, 14, 11);
    const tx = track(textMesh(c.bridge || "", { k, size: 58, font: F.display, color: "#fff", stroke: "#111", strokeW: 10, depth: 6, depthColor: "#0b1a66", maxW: 470 }));
    tx.position.set(0, 0, 0.4); g.add(tx);
    if (bTone) sfx.push([tHook, "whoosh", 0.7], [tHook + 0.13, "ding", 0.6]);
    if (c.template === "twist") sfx.push([tHook * 0.8 - 0.1, "scratch", 0.9]);
    sections.push({ from: tHook, to: tBridge, group: g, update(t) {
      const lt = t - tHook;
      stripes.forEach((s, i) => { s.position.x = -7 + i * 1.2 + (lt * 3.2) % 1.2; });
      upd(t);
      const sc = easeOutBack((lt - 0.06) / 0.3); tx.scale.setScalar(Math.max(0.001, sc));
      cam.position.set(0, 0, DIST - 1.2 * (lt / T.bridge));
    } });
  }

  // ===== 3. 광고 파트 (본편 영상 또는 사진 3장) =====
  let video = null;
  if (snap.base) {
    const g = new THREE.Group(); scene.add(g);
    video = document.createElement("video");
    video.src = snap.base.url; video.playsInline = true; video.preload = "auto"; video.crossOrigin = "anonymous";
    const vt = new THREE.VideoTexture(video); vt.minFilter = THREE.LinearFilter; if (THREE.sRGBEncoding) vt.encoding = THREE.sRGBEncoding;
    const vtBg = new THREE.VideoTexture(video); vtBg.minFilter = THREE.LinearFilter;
    const bgW = FW * 1.15, bgH = FH * 1.15;
    const bgMesh = plane(bgW, bgH, blurMaterial(vtBg, 0.5)); bgMesh.position.z = -0.8; g.add(bgMesh);
    const fg = plane(FW, FW, new THREE.MeshBasicMaterial({ map: vt })); g.add(fg);
    const segs = (snap.base.segments && snap.base.segments.length) ? snap.base.segments : [{ start: 0, end: snap.base.dur, caption: "" }];
    // 구간 자막 (위쪽)
    let acc = tBridge;
    const segInfo = segs.map((s) => {
      const from = acc; acc += s.end - s.start;
      let cap = null;
      if (s.caption) { cap = track(textMesh(s.caption, { k, size: 34, font: F.body, weight: "800", color: "#fff", box: "rgba(13,13,18,.86)", radius: 8, maxW: 470 }));
        cap.position.set(0, wy(134), 0.3); cap.visible = false; g.add(cap); }
      return { from, to: acc, start: s.start, cap };
    });
    const sizeFromVideo = () => {
      const iw = video.videoWidth || 1, ih = video.videoHeight || 1, a = iw / ih;
      // 앞: 비율 그대로 화면 폭에 맞춤 / 뒤: 꽉 채워 흐리게
      if (a >= FW / FH) { fg.scale.set(1, (FW / a) / FW, 1); } else { fg.scale.set((FH * a) / FW, FH / FW, 1); }
      fitUV(vtBg, iw, ih, bgW / bgH, "cover");
    };
    video.addEventListener("loadedmetadata", sizeFromVideo);
    sections.push({ from: tBridge, to: tEnd, group: g, segInfo, update(t) {
      cam.position.set(0, 0, DIST);
      const cur = segInfo.find((s) => t >= s.from && t < s.to) || segInfo[segInfo.length - 1];
      segInfo.forEach((s) => { if (s.cap) { s.cap.visible = s === cur; s.cap.material.opacity = clamp((t - s.from) / 0.2); } });
      cur.want = cur.start + (t - cur.from);
    } });
  } else {
    const per = snap.adLen / 3;
    for (let i = 0; i < 3; i++) {
      const g = new THREE.Group(); scene.add(g);
      const from = tBridge + i * per, img = snap.photos[i];
      const pw = FW * 1.15, ph = FH * 1.15;
      const p = img ? plane(pw, ph, new THREE.MeshBasicMaterial({ map: coverTexture(img, pw, ph) })) : plane(pw, ph, basic("#222")); p.position.z = -0.5; g.add(p);
      const shade = plane(FW * 1.2, FH * 0.5, new THREE.MeshBasicMaterial({ map: radialTexture("rgba(0,0,0,.7)", "rgba(0,0,0,0)"), transparent: true, depthWrite: false }));
      shade.position.set(0, wy(820), 0.05); g.add(shade);
      const cap = track(textMesh((c.ad || [])[i] || "", { k, size: 44, font: F.display, color: "#fff", stroke: "#000", strokeW: 8, depth: 4, maxW: 470 }));
      cap.position.set(0, wy(790), 0.4); g.add(cap);
      sections.push({ from, to: from + per, group: g, update(t) {
        const lt = t - from;
        cam.position.set((i % 2 ? -1 : 1) * 0.25 * (lt / per), 0, DIST - 0.8 * (lt / per));
        cap.material.opacity = clamp(lt / 0.3); cap.position.x = -(1 - easeOut(lt / 0.3)) * 0.6;
      } });
    }
  }

  // ===== 4. 엔딩 =====
  {
    const g = new THREE.Group(); scene.add(g);
    const bg = plane(FW * 3, FH * 2, basic("#2B54FF")); bg.position.z = -3; g.add(bg);
    const upd = bokeh(g, 16, 29);
    const name = track(textMesh(info.name || "우리 가게", { k, size: 76, font: F.display, color: "#fff", stroke: "#111", strokeW: 12, depth: 8, depthColor: "#0b1a66", maxW: 470 }));
    name.position.set(0, wy(330), 0.5); g.add(name);
    const parts = [];
    if (info.offer) { const m = track(textMesh(info.offer, { k, size: 36, font: F.display, color: "#FFD43B", stroke: "#111", strokeW: 7, maxW: 470 })); m.position.set(0, wy(500), 0.4); g.add(m); parts.push(m); }
    if (info.place) { const m = track(textMesh(info.place, { k, size: 28, font: F.body, weight: "700", color: "#fff", maxW: 470 })); m.position.set(0, wy(570), 0.4); g.add(m); parts.push(m); }
    const btn = track(textMesh(c.cta || "프로필 링크 확인", { k, size: 32, font: F.body, weight: "900", color: "#2B54FF", box: "#fff", radius: 40, maxW: 440 }));
    btn.position.set(0, wy(700), 0.45); g.add(btn);
    if (bTone) sfx.push([tEnd + 0.03, "ding", 0.5]);
    sections.push({ from: tEnd, to: total + 1, group: g, update(t) {
      const lt = t - tEnd; upd(t);
      name.scale.setScalar(Math.max(0.001, easeOutBack(lt / 0.4)));
      parts.forEach((m, i) => { m.material.opacity = clamp((lt - 0.3 - i * 0.15) / 0.3); });
      btn.visible = lt > 0.6; btn.scale.setScalar(1 + Math.sin(lt * 6) * 0.04);
      cam.position.set(0, 0, DIST - 0.5 * clamp(lt / T.end));
    } });
  }

  // ===== HUD: 광고 표시 + 진행 바 (카메라와 상관없이 화면에 고정) =====
  const hud = new THREE.Scene();
  const hcam = new THREE.OrthographicCamera(0, 540, 0, -960, -10, 10);
  const badge = track(textMesh(info.disclose || "광고", { k, size: 24, font: F.body, weight: "900", color: "#1A1600", box: "#FFD43B", radius: 8, maxW: 300 }));
  // 텍스처 메쉬는 월드 단위(1=100px)라 HUD에서는 100배
  badge.scale.setScalar(100);
  const bw = badge.geometry.parameters.width * 100, bh = badge.geometry.parameters.height * 100;
  badge.position.set(24 + bw / 2 - 12, -(34 + bh / 2 - 12), 0); hud.add(badge);
  const barBg = plane(540, 6, basic("#ffffff", { transparent: true, opacity: 0.25 })); barBg.position.set(270, -957, 0); hud.add(barBg);
  const bar = plane(540, 6, basic("#ffffff")); bar.position.set(270, -957, 0.1); hud.add(bar);

  function renderAt(renderer, t) {
    sections.forEach((s) => { const on = t >= s.from && t < s.to; s.group.visible = on; if (on) s.update(t); });
    renderer.autoClear = true; renderer.render(scene, cam);
    const p = clamp(t / total); bar.scale.x = Math.max(0.0001, p); bar.position.x = 270 * p;
    renderer.autoClear = false; renderer.clearDepth(); renderer.render(hud, hcam);
  }
  function dispose() { disposers.forEach((d) => d()); if (video) { video.pause(); video.removeAttribute("src"); video.load(); } }
  const adSection = sections.find((s) => s.segInfo);
  return { renderAt, dispose, total, sfx, video, adSection, tBridge, tEnd };
}

// ---------- 실행 (미리 재생 / 녹화) ----------
let running = null;
function status(msg, err) { const p = $("threeStatus"); p.className = "bstatus" + (err ? " err" : ""); p.textContent = msg; }
function setBusy(on) { $("threeBtn").disabled = on; $("threePreview").disabled = on; $("threeStop").hidden = !on; $("tprog").hidden = !on; }
let tq = 1080;
document.querySelectorAll("#threeQual [data-tq]").forEach((b) => b.addEventListener("click", () => {
  tq = Number(b.dataset.tq);
  document.querySelectorAll("#threeQual [data-tq]").forEach((x) => { const on = x === b; x.setAttribute("aria-selected", String(on)); x.setAttribute("aria-checked", String(on)); });
}));

function pickMime() {
  if (typeof MediaRecorder === "undefined") return null;
  return ["video/mp4;codecs=avc1.640028,mp4a.40.2", "video/mp4;codecs=avc1,mp4a.40.2", "video/mp4", "video/webm;codecs=vp9,opus", "video/webm;codecs=vp8,opus", "video/webm"]
    .find((m) => MediaRecorder.isTypeSupported(m)) || null;
}

async function start(record) {
  if (running) return;
  const snap = window.HookCut.snapshot();
  if (!snap.concept) { status("먼저 훅을 하나 골라 주세요.", true); return; }
  if (record && !pickMime()) { status("이 브라우저는 영상 녹화를 지원하지 않아요. 크롬이나 엣지에서 열어 주세요.", true); return; }
  window.HookCut.stopPreview();
  setBusy(true); status("3D 장면을 만드는 중…");
  try { await Promise.all([document.fonts.load(`900 40px ${snap.fonts.display}`), document.fonts.load(`900 40px ${snap.fonts.body}`), document.fonts.load(`700 40px ${snap.fonts.body}`)]); } catch (e) {}

  const outW = tq, outH = Math.round(tq * 16 / 9);
  const canvas = document.createElement("canvas"); canvas.id = "threeCanvas"; canvas.width = outW; canvas.height = outH;
  let renderer;
  try { renderer = new THREE.WebGLRenderer({ canvas, antialias: true, preserveDrawingBuffer: false }); }
  catch (e) { setBusy(false); status("WebGL 을 켤 수 없어요. 그래픽 가속이 꺼져 있는지 확인해 주세요.", true); return; }
  renderer.setPixelRatio(1); renderer.setSize(outW, outH, false);
  if (THREE.sRGBEncoding) renderer.outputEncoding = THREE.sRGBEncoding;
  const built = buildScene(snap, { k: outW / 540 * 1.25 });
  const screen = document.querySelector(".screen"); screen.append(canvas);

  // 소리: 효과음 + 본편 영상 소리 → (녹화용) MediaStreamDestination, (미리 듣기) 스피커
  const ac = new (window.AudioContext || window.webkitAudioContext)();
  const mix = ac.createGain(); mix.gain.value = 0.9;
  const dest = ac.createMediaStreamDestination();
  mix.connect(dest); mix.connect(ac.destination);
  if (built.video) {
    try { const vs = ac.createMediaElementSource(built.video); vs.connect(mix); } catch (e) { console.warn(e); }
    await new Promise((ok) => { if (built.video.readyState >= 1) ok(); else { built.video.onloadedmetadata = ok; built.video.onerror = ok; } });
  }
  await ac.resume();

  let rec = null, chunks = [], mime = null;
  if (record) {
    mime = pickMime();
    const stream = canvas.captureStream(30);
    dest.stream.getAudioTracks().forEach((tr) => stream.addTrack(tr));
    rec = new MediaRecorder(stream, { mimeType: mime, videoBitsPerSecond: outW >= 1080 ? 16_000_000 : 9_000_000, audioBitsPerSecond: 192_000 });
    rec.ondataavailable = (e) => { if (e.data && e.data.size) chunks.push(e.data); };
  }
  const lead = 0.35, t0 = ac.currentTime + lead;
  built.sfx.forEach(([t, name, vol]) => playSfx(ac, mix, name, t0 + t, vol));
  built.renderAt(renderer, 0);
  if (rec) rec.start(500);

  const total = built.total;
  let stopped = false, lastSeg = null;
  const finish = async (cancelled) => {
    if (stopped) return; stopped = true;
    if (built.video) built.video.pause();
    const done = () => { renderer.dispose(); built.dispose(); canvas.remove(); ac.close(); running = null; setBusy(false); };
    if (rec && rec.state !== "inactive") {
      await new Promise((ok) => { rec.onstop = ok; rec.stop(); });
      if (!cancelled) {
        const type = mime.split(";")[0], ext = type.includes("mp4") ? "mp4" : "webm";
        const blob = new Blob(chunks, { type }), url = URL.createObjectURL(blob);
        window.HookCut.showResult(url, `Three.js · ${outW}×${outH} · 30fps`);
        const fname = window.HookCut.saveName(ext).replace("hookcut-", "hookcut-three-");
        if (window.HookCut.isLocal) { const a = document.createElement("a"); a.href = url; a.download = fname; document.body.append(a); a.click(); a.remove(); }
        status(`렌더 완료 · ${ext.toUpperCase()} ${(blob.size / 1e6).toFixed(1)}MB · ${fname} 으로 내려받았어요. 미리보기의 녹화본 탭에서도 볼 수 있어요.`);
      } else status("멈췄어요.");
    } else status(cancelled ? "멈췄어요." : "미리 재생을 마쳤어요.");
    done();
  };
  running = { stop: () => finish(true) };

  const tick = () => {
    if (stopped) return;
    const t = ac.currentTime - t0;
    if (t >= total) { built.renderAt(renderer, total - 0.001); setTimeout(() => finish(false), 250); return; }
    const tt = Math.max(0, t);
    // 본편 영상: 지금 구간의 원본 시각에 맞춰 재생 (어긋나면 다시 맞춤)
    if (built.video && built.adSection) {
      const inAd = tt >= built.tBridge && tt < built.tEnd;
      if (inAd) {
        built.renderAt(renderer, tt);
        const seg = built.adSection.segInfo.find((s) => tt >= s.from && tt < s.to);
        const want = seg ? seg.start + (tt - seg.from) : 0;
        if (seg !== lastSeg || Math.abs(built.video.currentTime - want) > 0.25) { try { built.video.currentTime = want; } catch (e) {} lastSeg = seg; }
        if (built.video.paused) built.video.play().catch(() => {});
      } else { if (!built.video.paused) built.video.pause(); built.renderAt(renderer, tt); }
    } else built.renderAt(renderer, tt);
    $("tprogFill").style.width = `${clamp(tt / total) * 100}%`;
    status(`${record ? "녹화 중" : "미리 재생 중"}… ${tt.toFixed(1)} / ${total.toFixed(1)}초 · 이 탭을 앞에 띄워 두세요`);
    requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
}

$("threeBtn").onclick = () => start(true);
$("threePreview").onclick = () => start(false);
$("threeStop").onclick = () => running && running.stop();
})();
