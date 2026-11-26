// 장면 키트 (pipeline/src/generated/BKit.tsx 로 복사되어 쓰인다).
// 3D 명세(설계표)만 주면 무대·카메라·소품 자리·인물 감정·반전 템플릿을 검증된 방식으로 그린다.
// 모델(Claude)이 쓰는 코드는 "사실을 보여 주는 시각화(Viz)" 하나뿐이고, 키트가 그것을 정해진 상자 안에 놓는다.
//   - 일반 장면: Viz 는 단위 상자(x·y -1..1, z -0.6..0.6) 안에 그린다 → 키트가 시각화 자리(인물 오른쪽 공중 또는 바닥)에 0.7배로 놓는다
//   - 반전 장면: 키트가 제품을 쾅 착지시키고 뒤쪽을 어둡게 한다. Viz 는 제품 둘레의 "기능 효과"를 미터 단위로 그린다
//     (원점 = 제품 바닥 가운데, 제품은 x -0.4..0.4, y 0..1.35, 뚜껑은 오른쪽 바닥 x≈0.9 에 놓인다)
import React, { useState } from 'react';
import { interpolate } from 'remotion';
import { useCurrentFrame } from 'remotion';
import { blendCamera, CAMERAS, Character, DustBurst, FLOOR_Y, Prop, Quake, SLAM_IMPACT, SlamIn, Stage, type CameraName } from './BCharacter';

export type Slot = 'back-left' | 'back-center' | 'back-right' | 'side-left' | 'side-right' | 'mid-left' | 'mid-right' | 'near-person' | 'front-right' | 'fg-left' | 'fg-right';
/** 같은 물건 여러 개 놓는 모양: row 한 줄, grid 두 줄, stack 위로 쌓기, cluster 촘촘한 무리, arc 부채꼴 */
export type Pattern = 'single' | 'row' | 'grid' | 'stack' | 'cluster' | 'arc';
export type Emote = 'look' | 'tilt' | 'nod' | 'surprise' | 'bounce' | 'droop' | 'victory' | 'defeat';

export interface KitPlan {
  stage: { floor: string; wall: string; hdri?: string };
  /** 카메라 키프레임: at = 장면 진행 비율(0~1), view = 보는 곳 */
  shots: { at: number; view: CameraName }[];
  /** on = 다른 소품(배열 번호) 위에 올림 (탁자·책상·선반 위), count·pattern = 같은 물건 여러 개 */
  props: { file: string; slot: Slot; height: number; rotationY?: number; tone?: string; on?: number; count?: number; pattern?: Pattern }[];
  character?: { file: string; emotions: { type: Emote; from: number; to: number }[] } | null;
  /** 시각화 자리: air = 인물 오른쪽 공중, floor = 인물 오른쪽 바닥 위 */
  viz: 'air' | 'floor';
  reveal?: boolean;
  /** 반전에서 제품 뚜껑을 여는 구간 (진행 비율) */
  lid?: { from: number; to: number };
}

// 자리 (x, z), 최대 높이, 최대 가로 (카메라 wide 기준으로 화면 안에 들어오게 맞춘 값)
const SLOTS: Record<Slot, { x: number; z: number; maxH: number; maxW: number }> = {
  'back-left': { x: -1.35, z: -2.2, maxH: 2.6, maxW: 1.6 },
  'back-center': { x: 0.15, z: -2.5, maxH: 2.6, maxW: 1.8 },
  'back-right': { x: 1.5, z: -2.2, maxH: 2.6, maxW: 1.6 },
  'side-left': { x: -1.6, z: -1.1, maxH: 2.0, maxW: 1.1 },
  'side-right': { x: 1.65, z: -1.2, maxH: 2.0, maxW: 1.1 },
  'mid-left': { x: -1.45, z: -0.6, maxH: 1.8, maxW: 0.8 },
  'mid-right': { x: 1.45, z: -0.7, maxH: 1.8, maxW: 0.8 },
  'near-person': { x: -1.45, z: 0.45, maxH: 0.9, maxW: 0.55 },
  'front-right': { x: 1.25, z: 0.45, maxH: 0.55, maxW: 0.6 },
  // 전경: 카메라 가까이 화면 양 끝에 걸치는 낮은 물체 (깊이감, 일부 잘려도 된다)
  'fg-left': { x: -1.05, z: 2.0, maxH: 0.8, maxW: 0.7 },
  'fg-right': { x: 1.05, z: 2.0, maxH: 0.9, maxW: 0.7 },
};
const PERSON: [number, number, number] = [-0.95, FLOOR_Y, -0.1];
const VIZ_AIR: [number, number, number] = [0.45, 1.4, -0.5];
const VIZ_SCALE = 0.85;
// 인물 없는 장면: 핵심 요소가 화면 가운데를 크게 차지한다 (상자 약 2.1m)
const VIZ_SOLO: [number, number, number] = [0, 1.35, -0.5];
const VIZ_SOLO_SCALE = 1.05; // 단위 상자 1 = 0.85m → 상자 약 1.7m (화면 폭의 절반 이상)
const PRODUCT_AT: [number, number, number] = [0, FLOOR_Y, 0.6];

/** 바닥·벽 색 밝기 제한: 바닥이 하얗게 날아가거나 벽이 너무 밝아 무대가 밋밋해지지 않게 */
function clampLight(hex: string, min: number, max: number): string {
  const m = /^#?([0-9a-f]{6})$/i.exec(hex.trim());
  if (!m) return hex;
  const n = parseInt(m[1], 16);
  let r = (n >> 16) / 255, g = ((n >> 8) & 255) / 255, b = (n & 255) / 255;
  const l = 0.2126 * r + 0.7152 * g + 0.0722 * b;
  const k = l > max ? max / l : l < min && l > 0 ? min / l : 1;
  [r, g, b] = [r, g, b].map((v) => Math.min(1, v * k));
  return '#' + [r, g, b].map((v) => Math.round(v * 255).toString(16).padStart(2, '0')).join('');
}

function cameraAt(shots: KitPlan['shots'], p: number) {
  const s = [...shots].sort((a, b) => a.at - b.at);
  if (!s.length) return CAMERAS.wide;
  if (p <= s[0].at) return CAMERAS[s[0].view];
  for (let i = 0; i < s.length - 1; i++) {
    if (p < s[i + 1].at) return blendCamera(s[i].view, s[i + 1].view, (p - s[i].at) / Math.max(1e-3, s[i + 1].at - s[i].at));
  }
  return CAMERAS[s[s.length - 1].view];
}

type Size = { x: number; y: number; z: number };
/** 후경 소품을 살짝 어둡게 (공기 원근법: 앞의 시각화가 또렷하게 떨어져 보이게) */
const BACK_TONE = '#a9a39c';
type Placed = { key: string; file: string; position: [number, number, number]; height: number; maxW: number; rotationY: number; tone?: string; base: number };

/** 패턴대로 n 개의 자리(가운데 기준 dx, dy, dz)와 각 물건의 최대 가로. area = 놓을 수 있는 가로·깊이 */
function patternOffsets(pattern: Pattern, n: number, itemH: number, area: { w: number; d: number }): { dx: number; dy: number; dz: number; rot: number }[] {
  const out: { dx: number; dy: number; dz: number; rot: number }[] = [];
  const jit = (i: number, k: number) => ((Math.sin(i * 12.9898 + k * 78.233) * 43758.5453) % 1) - 0.5; // 결정적 흔들림
  for (let i = 0; i < n; i++) {
    if (pattern === 'stack') out.push({ dx: jit(i, 1) * 0.04, dy: i * itemH * 0.98, dz: jit(i, 2) * 0.04, rot: jit(i, 3) * 0.5 });
    else if (pattern === 'grid') {
      const cols = Math.ceil(n / 2), col = i % cols, row = Math.floor(i / cols);
      out.push({ dx: cols > 1 ? (col / (cols - 1) - 0.5) * area.w : 0, dy: 0, dz: (row - 0.5) * area.d * 0.6, rot: jit(i, 3) * 0.3 });
    } else if (pattern === 'cluster') {
      const a = i * 2.39996, r = Math.sqrt((i + 0.5) / n) * 0.5;
      out.push({ dx: Math.cos(a) * r * area.w, dy: 0, dz: Math.sin(a) * r * area.d, rot: jit(i, 3) * 1.2 });
    } else if (pattern === 'arc') {
      const t = n > 1 ? i / (n - 1) - 0.5 : 0;
      out.push({ dx: t * area.w, dy: 0, dz: -Math.cos(t * Math.PI) * area.d * 0.4 + area.d * 0.2, rot: -t * 0.8 });
    } else out.push({ dx: n > 1 ? (i / (n - 1) - 0.5) * area.w : 0, dy: 0, dz: 0, rot: jit(i, 3) * 0.2 }); // row / single
  }
  return out;
}

type Layout = 'person' | 'solo' | 'reveal';

/**
 * 장면 구성에 따라 자리를 옮긴다: 시각화 상자 뒤(화면에서 같은 높이·같은 자리)에 받침·소품이 오면
 * 시각화와 겹쳐 "파고든" 것처럼 보이므로, 후경은 시각화 양옆 빈자리로 비킨다.
 *   person: 인물 왼쪽, 시각화 오른쪽 가운데 (x -0.4~1.3) → 후경은 인물 뒤와 오른쪽 끝
 *   solo: 시각화가 가운데 (x ±1.05) → 후경은 양 끝
 */
function slotFor(slot: Slot, layout: Layout, used: Map<string, number>, lowAlone = false): { x: number; z: number; maxH: number; maxW: number } {
  const base = SLOTS[slot] ?? SLOTS['back-center'];
  if (layout === 'reveal') return base;
  // 낮은 물건(0.5m 이하, 위에 올린 것 없음)은 화면에서 시각화 아래로 보이므로 후경 가운데에 그대로 둔다
  if (slot === 'back-center' && lowAlone) return { ...base, maxH: 0.5 };
  if (slot.startsWith('back')) {
    // 후경 가운데는 덜 쓴 쪽 끝으로
    let side: 'left' | 'right' = slot === 'back-left' ? 'left' : slot === 'back-right' ? 'right' : (used.get('back:left') ?? 0) <= (used.get('back:right') ?? 0) ? 'left' : 'right';
    if (layout === 'person' && slot === 'back-center') side = 'left'; // 인물 뒤는 시각화와 안 겹친다
    const k = used.get(`back:${side}`) ?? 0;
    used.set(`back:${side}`, k + 1);
    const x0 = layout === 'person' ? (side === 'left' ? [-1.05, -1.95][k % 2] : 2.0) : side === 'left' ? -1.9 : 1.95;
    return { x: x0, z: -2.2 - Math.floor(k / 2) * 0.5, maxH: base.maxH, maxW: layout === 'person' && side === 'left' && k % 2 === 0 ? 0.9 : 1.0 };
  }
  if (slot === 'mid-left' || slot === 'mid-right') {
    const right = slot === 'mid-right';
    if (layout === 'person') return right ? { x: 1.85, z: -0.9, maxH: 1.6, maxW: 0.6 } : { x: -1.75, z: -0.8, maxH: 1.8, maxW: 0.7 };
    return { x: right ? 1.6 : -1.6, z: -0.7, maxH: 1.6, maxW: 0.6 };
  }
  if (slot === 'side-left' || slot === 'side-right') {
    const right = slot === 'side-right';
    if (layout === 'person' && right) return { x: 2.0, z: -1.3, maxH: base.maxH, maxW: 0.9 };
    if (layout === 'solo') return { x: right ? 1.85 : -1.85, z: -1.2, maxH: base.maxH, maxW: 0.9 };
  }
  return base;
}

/** 소품 배치: 바닥 자리(slot)의 물건 → 그 위에 올리는 물건(on, 받침의 실제 크기를 알아야 해서 받침이 불러와진 뒤) */
function placeProps(props: KitPlan['props'], sizes: Record<number, Size>, layout: Layout): Placed[] {
  const out: Placed[] = [];
  const list = props.slice(0, 8);
  const used = new Map<string, number>();
  list.forEach((p, idx) => {
    const n = Math.max(1, Math.min(8, Math.round(p.count ?? 1)));
    const pattern: Pattern = p.pattern ?? (n > 1 ? 'row' : 'single');
    const onBase = p.on !== undefined && p.on !== idx && list[p.on] && list[p.on].on === undefined ? p.on : undefined;
    if (onBase === undefined) {
      const isBack = (p.slot ?? 'back-center').startsWith('back');
      const lowAlone = p.height <= 0.5 && !list.some((q, qi) => qi !== idx && q.on === idx);
      const slot = slotFor(p.slot, layout, used, lowAlone);
      const k = isBack ? 0 : used.get(p.slot) ?? 0; // 후경은 slotFor 가 자리를 나눠 준다
      if (!isBack) used.set(p.slot, k + 1);
      const dir = slot.x >= 0 ? 1 : -1; // 같은 자리 두 번째부터는 바깥쪽·뒤로 비킨다 (시각화 쪽으로 들어오지 않게)
      const h = Math.min(Math.max(0.1, p.height), slot.maxH);
      const each = n > 1 ? Math.min(slot.maxW, Math.max(0.25, (slot.maxW * 1.6) / n)) : slot.maxW;
      const offs = patternOffsets(pattern, n, h, { w: Math.min(2.2, each * (n - 1) * 1.05), d: 0.8 });
      offs.forEach((o, j) =>
        out.push({ key: `p${idx}-${j}`, file: p.file, position: [slot.x + dir * k * 0.35 + o.dx, FLOOR_Y + o.dy, slot.z - k * 0.45 + o.dz], height: h, maxW: each, rotationY: (p.rotationY ?? 0) + o.rot, tone: p.tone ?? (isBack && layout !== 'reveal' ? BACK_TONE : undefined), base: j === 0 ? idx : -1 })
      );
    } else {
      const baseSize = sizes[onBase];
      const basePlaced = out.find((x) => x.key === `p${onBase}-0`);
      if (!baseSize || !basePlaced) return; // 받침이 아직 안 불러와졌으면 다음 그림에서
      const top = basePlaced.position[1] + baseSize.y;
      const area = { w: baseSize.x * 0.72, d: baseSize.z * 0.55 };
      const h = Math.min(Math.max(0.05, p.height), 0.9);
      const each = Math.max(0.08, Math.min(area.w / Math.max(1, pattern === 'stack' ? 1 : n) * 0.9, 0.6));
      patternOffsets(pattern, n, h, area).forEach((o, j) =>
        out.push({ key: `p${idx}-${j}`, file: p.file, position: [basePlaced.position[0] + o.dx, top + o.dy, basePlaced.position[2] + o.dz], height: h, maxW: each, rotationY: (p.rotationY ?? 0) + o.rot, tone: p.tone ?? basePlaced.tone, base: -1 })
      );
    }
  });
  return out;
}

export function KitScene({ plan, durationInFrames: d, children, Product }: { plan: KitPlan; durationInFrames: number; color: string; children?: React.ReactNode; Product?: React.ComponentType<{ height?: number; lidOpen?: number }> }) {
  const f = useCurrentFrame();
  const p = f / Math.max(1, d);
  const [sizes, setSizes] = useState<Record<number, Size>>({});
  // 인물이 없으면 인물·시각화 자리 대신 가운데 카메라로 (person → center, wide → center, visual → centerClose)
  const solo = !plan.character && !plan.reveal;
  const shots = solo
    ? plan.shots.map((s) => ({ ...s, view: (s.view === 'visual' ? 'centerClose' : 'center') as CameraName }))
    : plan.shots;
  const camera = plan.reveal ? CAMERAS.product : cameraAt(shots, p);
  const fr = (x: number) => Math.round(x * d);

  // 인물 감정 → 동작 클립(victory/defeat) + 덧입힘(나머지)
  const ch = plan.character;
  const clips: { clip: 'Idle' | 'Victory' | 'Defeat'; from: number; to: number }[] = [];
  if (ch) {
    const big = ch.emotions.filter((e) => e.type === 'victory' || e.type === 'defeat').sort((a, b) => a.from - b.from);
    let cur = 0;
    for (const e of big) {
      if (fr(e.from) > cur) clips.push({ clip: 'Idle', from: cur, to: fr(e.from) });
      clips.push({ clip: e.type === 'victory' ? 'Victory' : 'Defeat', from: fr(e.from), to: fr(e.to) });
      cur = fr(e.to);
    }
    clips.push({ clip: 'Idle', from: cur, to: d + 1 });
  }
  const emotes = (ch?.emotions ?? [])
    .filter((e) => e.type !== 'victory' && e.type !== 'defeat')
    .map((e) => ({ type: e.type as 'look' | 'tilt' | 'nod' | 'surprise' | 'bounce' | 'droop', from: fr(e.from), to: fr(e.to), amount: e.type === 'look' ? 0.45 : undefined }));
  if (plan.reveal && ch) emotes.push({ type: 'surprise', from: SLAM_IMPACT, to: SLAM_IMPACT + 26, amount: undefined });

  // 반전: 착지 순간부터 0.5초에 걸쳐 무대 조명을 낮춘다 (판을 씌우지 않음 → 화면 전체가 고르게 어두워지고 잘림이 없다)
  const dim = plan.reveal ? interpolate(f, [SLAM_IMPACT, SLAM_IMPACT + 15], [0, 0.9], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' }) : 0;
  const world = (
    <>
      <Stage dim={dim} camera={camera} floorColor={clampLight(plan.stage.floor, 0.12, 0.3)} wallColor={clampLight(plan.stage.wall, 0.04, 0.12)} back={-4.8} hdri={plan.stage.hdri} envIntensity={0.35} />
      {placeProps(plan.props, sizes, plan.reveal ? 'reveal' : solo ? 'solo' : 'person').filter((pr) => !plan.reveal || pr.position[2] < 0.1).map((pr) => ( // 반전: 앞쪽 소품은 빼서 제품·뚜껑 자리를 비운다
        <Prop
          key={pr.key}
          file={pr.file}
          position={pr.position}
          height={pr.height}
          maxWidth={pr.maxW}
          rotationY={pr.rotationY}
          tone={pr.tone}
          onSize={pr.base >= 0 ? (sz) => setSizes((m) => (m[pr.base] ? m : { ...m, [pr.base]: sz })) : undefined}
        />
      ))}
      {ch && (
        <Character file={ch.file} colors={{ Skin: '#f0c9a6' }} timeline={clips} emotes={emotes} position={PERSON} rotationY={0.5} height={1.7} />
      )}
    </>
  );

  if (!plan.reveal) {
    // 바닥 자리는 세로 화면에서 자막에 걸려서 쓰지 않는다: 땅이 필요하면 시각화가 상자 아래(y=-1)에 받침판을 그린다
    const at = solo ? VIZ_SOLO : VIZ_AIR;
    return (
      <group>
        {world}
        <group position={at} scale={solo ? VIZ_SOLO_SCALE : VIZ_SCALE}>{children}</group>
      </group>
    );
  }

  const lidOpen = plan.lid ? interpolate(p, [plan.lid.from, plan.lid.to], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' }) : 0;
  return (
    <Quake impact={SLAM_IMPACT}>
      {world}
      {/* 제품만 비추는 스포트라이트: 무대가 어두워지는 만큼 켜진다 */}
      <spotLight
        userData={{ keepLit: true }}
        position={[0.15, PRODUCT_AT[1] + 5.2, PRODUCT_AT[2] + 1.1]}
        target-position={[0, PRODUCT_AT[1] + 0.5, PRODUCT_AT[2]]}
        angle={0.17}
        penumbra={0.45}
        decay={0}
        intensity={4.6 * (dim / 0.9)}
        color="#fff6ea"
      />
      <SlamIn impact={SLAM_IMPACT} position={PRODUCT_AT}>
        {Product ? <Product height={1.35} lidOpen={lidOpen} /> : null}
      </SlamIn>
      <DustBurst impact={SLAM_IMPACT} position={PRODUCT_AT} radius={1.0} />
      <group position={PRODUCT_AT}>{f >= SLAM_IMPACT ? children : null}</group>
    </Quake>
  );
}
