// 장면 키트 (pipeline/src/generated/BKit.tsx 로 복사되어 쓰인다).
// 3D 명세(설계표)만 주면 무대·카메라·소품 자리·인물 감정·반전 템플릿을 검증된 방식으로 그린다.
// 모델(Claude)이 쓰는 코드는 "사실을 보여 주는 시각화(Viz)" 하나뿐이고, 키트가 그것을 정해진 상자 안에 놓는다.
//   - 일반 장면: Viz 는 단위 상자(x·y -1..1, z -0.6..0.6) 안에 그린다 → 키트가 시각화 자리(인물 오른쪽 공중 또는 바닥)에 0.7배로 놓는다
//   - 반전 장면: 키트가 제품을 쾅 착지시키고 뒤쪽을 어둡게 한다. Viz 는 제품 둘레의 "기능 효과"를 미터 단위로 그린다
//     (원점 = 제품 바닥 가운데, 제품은 x -0.4..0.4, y 0..1.35, 뚜껑은 오른쪽 바닥 x≈0.9 에 놓인다)
import React from 'react';
import { interpolate } from 'remotion';
import { useCurrentFrame } from 'remotion';
import { blendCamera, CAMERAS, Character, DustBurst, FLOOR_Y, Prop, Quake, SLAM_IMPACT, SlamIn, Stage, type CameraName } from './BCharacter';

export type Slot = 'back-left' | 'back-center' | 'back-right' | 'side-left' | 'side-right' | 'near-person' | 'front-right';
export type Emote = 'look' | 'tilt' | 'nod' | 'surprise' | 'bounce' | 'droop' | 'victory' | 'defeat';

export interface KitPlan {
  stage: { floor: string; wall: string; hdri?: string };
  /** 카메라 키프레임: at = 장면 진행 비율(0~1), view = 보는 곳 */
  shots: { at: number; view: CameraName }[];
  props: { file: string; slot: Slot; height: number; rotationY?: number; tone?: string }[];
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
  'near-person': { x: -1.45, z: 0.45, maxH: 0.9, maxW: 0.55 },
  'front-right': { x: 1.25, z: 0.45, maxH: 0.55, maxW: 0.6 },
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

/** 같은 자리에 여러 개면 옆으로 비켜 놓는다 */
function placeProps(props: KitPlan['props']) {
  const used = new Map<Slot, number>();
  return props.slice(0, 7).map((p) => {
    const slot = SLOTS[p.slot] ?? SLOTS['back-center'];
    const n = used.get(p.slot) ?? 0;
    used.set(p.slot, n + 1);
    const dir = slot.x >= 0 ? -1 : 1; // 화면 안쪽으로 비킨다
    return { ...p, maxW: slot.maxW, position: [slot.x + dir * n * 0.7, FLOOR_Y, slot.z + n * 0.15] as [number, number, number], height: Math.min(Math.max(0.1, p.height), slot.maxH) };
  });
}

export function KitScene({ plan, durationInFrames: d, children, Product }: { plan: KitPlan; durationInFrames: number; color: string; children?: React.ReactNode; Product?: React.ComponentType<{ height?: number; lidOpen?: number }> }) {
  const f = useCurrentFrame();
  const p = f / Math.max(1, d);
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
      {placeProps(plan.props).filter((pr) => !plan.reveal || pr.position[2] < 0.1).map((pr, i) => ( // 반전: 앞쪽 소품은 빼서 제품·뚜껑 자리를 비운다
        <Prop key={i} file={pr.file} position={pr.position} height={pr.height} maxWidth={pr.maxW} rotationY={pr.rotationY ?? 0} tone={pr.tone} />
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
