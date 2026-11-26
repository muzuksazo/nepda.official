// 재사용 인물 (Quaternius, CC0).
//   기본: Universal Animation Library 마네킹 (bassets/base_character.glb, 동작 CHARACTER_CLIPS)
//   캐릭터: Ultimate Animated Character Pack (bassets/uacp/<이름>.gltf, 동작 UACP_CLIPS, 재질 이름별 색 바꾸기 가능)
// 렌더할 때 pipeline/src/generated/BCharacter.tsx 로 복사되고, assets/quaternius/ 는 pipeline/public/bassets/ 로 복사된다.
// 장면 코드에서:  import { Character } from './BCharacter';
//
// <Character
//   timeline={[{ clip: 'Walk_Formal_Loop', from: 0, to: 40 }, { clip: 'Interact', from: 40, to: 90 }]}
//   path={[{ frame: 0, x: -2, z: 0 }, { frame: 40, x: -0.6, z: 0 }]}   // 선택: 프레임별 위치
//   rotationY={Math.PI / 2} height={2.2} />
//
// 동작은 프레임으로만 정해진다(Remotion 결정적 렌더). 구간이 바뀔 때 blend 프레임만큼 섞는다.
import React, { useEffect, useLayoutEffect, useMemo, useState } from 'react';
import { continueRender, delayRender, interpolate, staticFile, useCurrentFrame, useVideoConfig } from 'remotion';
import * as THREE from 'three';
import { useThree } from '@react-three/fiber';
import { GLTFLoader, type GLTF } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { clone as cloneSkinned } from 'three/examples/jsm/utils/SkeletonUtils.js';
import { mergeVertices } from 'three/examples/jsm/utils/BufferGeometryUtils.js';
import { RoomEnvironment } from 'three/examples/jsm/environments/RoomEnvironment.js';
import { HDRLoader } from 'three/examples/jsm/loaders/HDRLoader.js';

export const CHARACTER_CLIPS = [
  'Idle_Loop', 'Idle_Talking_Loop', 'Walk_Loop', 'Walk_Formal_Loop', 'Jog_Fwd_Loop', 'Sprint_Loop',
  'Interact', 'PickUp_Table', 'Fixing_Kneeling', 'Push_Loop', 'Sitting_Enter', 'Sitting_Idle_Loop',
  'Sitting_Talking_Loop', 'Sitting_Exit', 'Crouch_Idle_Loop', 'Jump_Start', 'Jump_Loop', 'Jump_Land',
  'Dance_Loop', 'Hit_Head', 'Spell_Simple_Enter', 'Spell_Simple_Idle_Loop', 'Spell_Simple_Shoot', 'Spell_Simple_Exit',
] as const;
export const UACP_CLIPS = [
  'Idle', 'Walk', 'Run', 'Walk_Carry', 'Run_Carry', 'PickUp', 'Victory', 'Defeat', 'SitDown', 'StandUp',
  'Jump', 'Roll', 'Punch', 'RecieveHit', 'Shoot_OneHanded', 'SwordSlash', 'Death',
] as const;
export type ClipName = (typeof CHARACTER_CLIPS)[number] | (typeof UACP_CLIPS)[number];
// 고개 숙이는 방향 부호: 이 리그는 뼈의 X축 회전 = 앞뒤 숙이기, Z축 = 옆으로 갸웃, Y축 = 좌우 돌리기
const PITCH = 1;
const LOOPING = /_Loop$|^(Idle|Walk|Run|Walk_Carry|Run_Carry)$/;

const cache = new Map<string, Promise<GLTF>>();
function load(url: string): Promise<GLTF> {
  if (!cache.has(url)) cache.set(url, new GLTFLoader().loadAsync(url));
  return cache.get(url)!;
}

export function Character({
  timeline,
  path,
  position = [0, 0, 0],
  rotationY = 0,
  height = 2.2,
  bodyColor = '#e9e9ec',
  jointColor = '#2a2a2e',
  blend = 8,
  file = 'bassets/base_character.glb',
  mirror = false,
  colors,
  smooth = true,
  emotes,
}: {
  timeline: { clip: ClipName; from: number; to: number; speed?: number; loop?: boolean }[];
  path?: { frame: number; x: number; z: number; y?: number }[];
  position?: [number, number, number];
  rotationY?: number;
  height?: number;
  bodyColor?: string;
  jointColor?: string;
  blend?: number;
  file?: string;
  /** 좌우 반전: 동작이 오른손으로 뻗는 방향을 화면 반대쪽으로 바꿀 때 */
  mirror?: boolean;
  /** 재질 이름 → 색 (예: { Shirt: '#e8322a', Skin: '#f1c9a5' }). 캐릭터 파일에만 쓴다 */
  colors?: Record<string, string>;
  /** 로우폴리 면 경계를 부드럽게 (법선 다시 계산) */
  smooth?: boolean;
  /**
   * 감정 표현 (동작 클립 위에 덧입힌다, 프레임 단위). 큰 행동 대신 이걸로 반응을 보여 준다.
   *   look: 고개를 돌려 바라봄 (amount = 좌우 각도, +면 캐릭터의 왼쪽)   tilt: 고개 갸웃(궁금함)
   *   nod: 끄덕임(이해)   surprise: 움찔 놀라며 몸을 젖힘   bounce: 신나서 통통 튐   droop: 고개를 떨굼(실망)
   * 기쁨은 timeline 의 'Victory', 실망은 'Defeat' 클립을 같이 쓰면 좋다.
   */
  emotes?: { type: 'look' | 'tilt' | 'nod' | 'surprise' | 'bounce' | 'droop'; from: number; to: number; amount?: number }[];
}) {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const [gltf, setGltf] = useState<GLTF | null>(null);
  const [handle] = useState(() => delayRender('character glb'));
  const advance = useThree((st) => st.advance);

  useEffect(() => {
    load(staticFile(file))
      .then((g) => setGltf(g))
      .catch((e) => { console.warn('[BCharacter] load failed', e); continueRender(handle); });
  }, [file, handle]);

  const rig = useMemo(() => {
    if (!gltf) return null;
    const root = cloneSkinned(gltf.scene) as THREE.Object3D;
    root.traverse((o) => {
      const m = o as THREE.SkinnedMesh;
      if (!m.isMesh) return;
      m.castShadow = true;
      m.receiveShadow = true;
      m.frustumCulled = false;
      if (smooth && m.geometry) {
        // 면마다 따로 있던 법선을 지우고 같은 자리 꼭짓점을 합친 뒤 다시 계산 → 매끈한 음영
        const g = m.geometry.clone();
        g.deleteAttribute('normal');
        const merged = mergeVertices(g, 1e-4);
        merged.computeVertexNormals();
        m.geometry = merged;
      }
      const mannequin = /base_character/.test(file);
      const mats = (Array.isArray(m.material) ? m.material : [m.material]).map((src) => {
        if (mannequin) {
          const isJoint = /joint/i.test(src.name);
          return new THREE.MeshStandardMaterial({ color: isJoint ? jointColor : bodyColor, roughness: 0.75, metalness: 0 });
        }
        const orig = (src as THREE.MeshStandardMaterial).color ?? new THREE.Color('#888');
        // 직업 캐릭터 팩(glTF)은 색이 뒤바뀌어 있다: 'Skin'(몸·머리·손)이 거의 검정, 'Face'(눈·눈썹 모양)가 흰색.
        // 피부를 살색으로 칠하면 눈·눈썹은 진한 색으로 (원래 모습: 살색 피부, 검은 눈)
        const eyes = src.name === 'Face' && colors?.Skin && !colors.Face ? new THREE.Color(colors.Eyes ?? '#2a1c15') : null;
        const mat = new THREE.MeshStandardMaterial({ color: eyes ?? colors?.[src.name] ?? orig.clone(), roughness: 0.65, metalness: 0 });
        mat.name = src.name;
        return mat;
      });
      m.material = Array.isArray(m.material) ? mats : mats[0];
    });
    // 키를 height 로 맞추고 발을 y=0 에
    root.updateMatrixWorld(true);
    const box = new THREE.Box3().setFromObject(root, true);
    const s = height / Math.max(1e-3, box.max.y - box.min.y);
    root.scale.setScalar(s);
    root.position.y = -box.min.y * s;
    const holder = new THREE.Group();
    holder.add(root);
    const mixer = new THREE.AnimationMixer(root);
    const actions = new Map<string, THREE.AnimationAction>();
    for (const c of gltf.animations) {
      const a = mixer.clipAction(c);
      a.play();
      a.setEffectiveWeight(0);
      actions.set(c.name.replace(/^Rig\|/, ''), a);
    }
    const bone = (n: string) => root.getObjectByName(n) as THREE.Bone | undefined;
    const bones = { head: bone('Head'), neck: bone('Neck'), torso: bone('Torso'), abdomen: bone('Abdomen') };
    const rest = new Map<THREE.Object3D, THREE.Quaternion>();
    for (const b of Object.values(bones)) if (b) rest.set(b, b.quaternion.clone());
    return { holder, root, baseY: root.position.y, mixer, actions, bones, rest };
  }, [gltf, height, bodyColor, jointColor, file, smooth, JSON.stringify(colors ?? {})]);

  // 모델이 장면에 붙은 다음 프레임을 찍게 한다
  useEffect(() => {
    if (!rig) return;
    // ThreeCanvas 는 프레임이 바뀔 때만 그리므로, 모델이 늦게 붙은 프레임은 직접 한 번 그린다
    advance(performance.now());
    requestAnimationFrame(() => continueRender(handle));
  }, [rig, handle, advance]);

  if (rig) {
    const segs = [...timeline].sort((a, b) => a.from - b.from);
    const weights = new Map<string, { w: number; t: number }>();
    const setW = (seg: (typeof segs)[number], w: number) => {
      const a = rig.actions.get(seg.clip);
      if (!a || w <= 0) return;
      const dur = a.getClip().duration;
      const raw = ((frame - seg.from) / fps) * (seg.speed ?? 1);
      const loop = seg.loop ?? LOOPING.test(seg.clip);
      const t = loop ? ((raw % dur) + dur) % dur : Math.min(Math.max(raw, 0), dur - 1e-3);
      const prev = weights.get(seg.clip);
      if (!prev || prev.w < w) weights.set(seg.clip, { w, t });
    };
    let idx = segs.findIndex((s) => frame >= s.from && frame < s.to);
    if (idx < 0) idx = frame < (segs[0]?.from ?? 0) ? 0 : segs.length - 1;
    const cur = segs[idx];
    const prev = segs[idx - 1];
    if (cur) {
      const k = prev ? interpolate(frame, [cur.from, cur.from + blend], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' }) : 1;
      setW(cur, k);
      if (prev && k < 1) setW(prev, 1 - k);
    }
    for (const [name, a] of rig.actions) {
      const e = weights.get(name);
      a.setEffectiveWeight(e ? e.w : 0);
      if (e) a.time = e.t;
    }
    for (const [b, q] of rig.rest) b.quaternion.copy(q); // 클립이 안 건드리는 뼈도 매 프레임 같은 출발점에서
    rig.mixer.update(0);

    // 감정 표현 덧입히기
    let hop = 0;
    const { head, neck, torso } = rig.bones;
    for (const e of emotes ?? []) {
      const ramp = Math.min(8, (e.to - e.from) / 3);
      const w = interpolate(frame, [e.from, e.from + ramp, e.to - ramp, e.to], [0, 1, 1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: (x) => x * x * (3 - 2 * x) });
      if (w <= 0) continue;
      const t = (frame - e.from) / fps;
      const a = e.amount;
      if (e.type === 'look') { head?.rotateY((a ?? 0.6) * w); neck?.rotateY((a ?? 0.6) * 0.4 * w); }
      if (e.type === 'tilt') head?.rotateZ((a ?? 0.32) * w);
      if (e.type === 'nod') head?.rotateX(PITCH * Math.max(0, Math.sin(t * Math.PI * 2 * 1.6)) * (a ?? 0.3) * w);
      if (e.type === 'droop') { head?.rotateX(PITCH * (a ?? 0.45) * w); torso?.rotateX(PITCH * 0.12 * w); }
      if (e.type === 'surprise') {
        const jolt = interpolate(frame - e.from, [0, 4, 12], [0, 1, 0.75], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
        torso?.rotateX(-PITCH * (a ?? 0.28) * jolt * w);
        head?.rotateX(-PITCH * 0.22 * jolt * w);
        hop += interpolate(frame - e.from, [0, 4, 9], [0, 0.07, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
      }
      if (e.type === 'bounce') hop += Math.abs(Math.sin(t * Math.PI * 2.4)) * (a ?? 0.08) * w;
    }
    rig.root.position.y = rig.baseY + hop / Math.max(1e-3, rig.root.scale.y);
  }

  let [x, y, z] = position;
  if (path && path.length) {
    const fr = path.map((p) => p.frame);
    const opt = { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' } as const;
    x = path.length > 1 ? interpolate(frame, fr, path.map((p) => p.x), opt) : path[0].x;
    z = path.length > 1 ? interpolate(frame, fr, path.map((p) => p.z), opt) : path[0].z;
    if (path.some((p) => p.y !== undefined)) y = interpolate(frame, fr, path.map((p) => p.y ?? position[1]), opt);
  }

  return rig ? <primitive object={rig.holder} position={[x, y, z]} rotation={[0, rotationY, 0]} scale={[mirror ? -1 : 1, 1, 1]} /> : null;
}

/**
 * 받아 둔 물건 모델(GLB) 하나를 놓는다. 크기는 height(또는 width) 에 맞추고, 바닥 중심이 position 에 오게 한다.
 *   file: 'bassets/kenney/furniture-kit/desk.glb', 'bassets/polypizza/<파일>.glb' 등 (b/assets 아래 경로 그대로)
 *   colors: 재질 이름 → 색,  tone: 모든 색에 곱할 색 (예 '#b08a70' → 장난감 같은 원색을 차분한 나무색으로)
 */
export function Prop({
  file,
  position = [0, 0, 0],
  rotationY = 0,
  height,
  width,
  colors,
  tone,
  glow,
  roughness = 0.7,
  shadow = true,
  maxWidth,
  onSize,
}: {
  /** 가로(x·z 중 큰 쪽) 최대 크기(m). 납작한 물건(키보드·러그)을 높이로 맞추면 거대해지는 것을 막는다 */
  maxWidth?: number;
  /** 불러와 크기를 맞춘 뒤 실제 크기(m: x 가로, y 높이, z 깊이)를 알려 준다 */
  onSize?: (size: { x: number; y: number; z: number }) => void;
  file: string;
  position?: [number, number, number];
  rotationY?: number;
  height?: number;
  width?: number;
  colors?: Record<string, string>;
  tone?: string;
  /** 재질 이름 → 스스로 빛나는 색 (예: 창문 유리 { glass: '#fff2d0' }) */
  glow?: Record<string, string>;
  roughness?: number;
  shadow?: boolean;
}) {
  const [gltf, setGltf] = useState<GLTF | null>(null);
  const [handle] = useState(() => delayRender('prop ' + file));
  const advance = useThree((st) => st.advance);
  useEffect(() => {
    load(staticFile(file))
      .then((g) => setGltf(g))
      .catch((e) => { console.warn('[BProp] load failed', file, e); continueRender(handle); });
  }, [file, handle]);
  const obj = useMemo(() => {
    if (!gltf) return null;
    const root = gltf.scene.clone(true);
    const mul = tone ? new THREE.Color(tone) : null;
    root.traverse((o) => {
      const m = o as THREE.Mesh;
      if (!m.isMesh) return;
      m.castShadow = shadow;
      m.receiveShadow = true;
      const mats = (Array.isArray(m.material) ? m.material : [m.material]).map((src) => {
        const s = src as THREE.MeshStandardMaterial;
        const col = colors?.[s.name] ? new THREE.Color(colors[s.name]) : (s.color ?? new THREE.Color('#999')).clone();
        if (mul && !colors?.[s.name]) col.multiply(mul);
        const g = glow?.[s.name];
        const mat = new THREE.MeshStandardMaterial({ color: col, map: s.map ?? null, roughness, metalness: 0, transparent: !g && s.transparent, opacity: g ? 1 : s.opacity });
        if (g) { mat.emissive = new THREE.Color(g); mat.emissiveIntensity = 1.1; mat.toneMapped = false; }
        return mat;
      });
      m.material = Array.isArray(m.material) ? mats : mats[0];
    });
    root.updateMatrixWorld(true);
    const box = new THREE.Box3().setFromObject(root, true);
    const size = box.getSize(new THREE.Vector3());
    let s = height ? height / Math.max(1e-3, size.y) : width ? width / Math.max(1e-3, Math.max(size.x, size.z)) : 1;
    if (maxWidth) s = Math.min(s, maxWidth / Math.max(1e-3, Math.max(size.x, size.z)));
    const c = box.getCenter(new THREE.Vector3());
    root.scale.setScalar(s);
    root.position.set(-c.x * s, -box.min.y * s, -c.z * s);
    const holder = new THREE.Group();
    holder.add(root);
    holder.userData.size = { x: size.x * s, y: size.y * s, z: size.z * s };
    return holder;
  }, [gltf, height, width, maxWidth, tone, roughness, shadow, JSON.stringify(colors ?? {}), JSON.stringify(glow ?? {})]);
  useEffect(() => {
    if (!obj) return;
    onSize?.(obj.userData.size);
    advance(performance.now());
    requestAnimationFrame(() => continueRender(handle));
  }, [obj, handle, advance]);
  return obj ? <primitive object={obj} position={position} rotation={[0, rotationY, 0]} /> : null;
}

/**
 * 무대: 바닥 + 뒤로 휘어 올라가는 배경(사진 스튜디오 같은 끝없는 벽) + 자연광(창가 햇빛 느낌의 키 라이트, 부드러운 그림자,
 * 실내 반사광) + 카메라. 바닥 높이 floorY 는 자막 윗부분 근처(화면 약 62%)에 오도록 기본값을 잡았다.
 * 장면 코드에서:  <Stage /> 를 맨 앞에 두고, 물체는 y = floorY 위에 세운다. 물체에 castShadow / receiveShadow 를 주면 그림자가 생긴다.
 */
export const FLOOR_Y = -0.35;
export function Stage({
  floorY = FLOOR_Y,
  floorColor = '#3f3a36',
  wallColor = '#141319',
  sun = [-4, 7, 5] as [number, number, number],
  warmth = '#fff1dc',
  camera = { position: [0, 1.55, 9.2] as [number, number, number], lookAt: [0, 0.55, -1] as [number, number, number], fov: 40 },
  hdri,
  envIntensity = 0.25,
  back = -3.2,
  dim = 0,
}: {
  /** 실내 반사·간접광용 HDRI (예 'bassets/polyhaven/hdri/brown_photostudio_02_1k.hdr'). 배경에는 안 보인다 */
  hdri?: string;
  envIntensity?: number;
  /** 바닥이 뒤쪽 벽으로 휘기 시작하는 깊이 (벽·가구를 뒤에 세울 땐 더 뒤로, 예 -4.8) */
  back?: number;
  /** 0~1: 무대 전체(조명·반사광)를 이만큼 어둡게 (반전에서 제품만 남길 때). 판을 씌우지 않아 경계·잘림이 없다 */
  dim?: number;
  floorY?: number;
  floorColor?: string;
  wallColor?: string;
  sun?: [number, number, number];
  warmth?: string;
  camera?: { position: [number, number, number]; lookAt: [number, number, number]; fov: number };
}) {
  const gl = useThree((st) => st.gl);
  const scene = useThree((st) => st.scene);
  const cam = useThree((st) => st.camera) as THREE.PerspectiveCamera;
  useMemo(() => {
    gl.shadowMap.enabled = true;
    gl.shadowMap.type = THREE.PCFShadowMap;
    gl.toneMapping = THREE.ACESFilmicToneMapping;
    gl.toneMappingExposure = 1.05;
    const pm = new THREE.PMREMGenerator(gl);
    scene.environment = pm.fromScene(new RoomEnvironment(), 0.04).texture;
    scene.fog = new THREE.Fog('#100f14', 11, 20);
  }, [gl, scene]);
  const advance = useThree((st) => st.advance);
  const [hdrHandle] = useState(() => (hdri ? delayRender('hdri ' + hdri) : null));
  useEffect(() => {
    if (!hdri || hdrHandle === null) return;
    new HDRLoader()
      .loadAsync(staticFile(hdri))
      .then((tex) => {
        const pm = new THREE.PMREMGenerator(gl);
        scene.environment = pm.fromEquirectangular(tex).texture;
        tex.dispose();
        advance(performance.now());
      })
      .catch((e) => console.warn('[BStage] hdri load failed', e))
      .finally(() => requestAnimationFrame(() => continueRender(hdrHandle)));
  }, [hdri, hdrHandle, gl, scene, advance]);
  const lit = 1 - Math.min(1, Math.max(0, dim));
  (scene as THREE.Scene & { environmentIntensity?: number }).environmentIntensity = envIntensity * lit;
  // 파이프라인 ThreeCanvas 가 깔아 둔 기본 조명 등 무대 밖 조명도 같이 낮춘다 (무대 조명·keepLit 조명은 빼고).
  // 처음 그릴 때는 조명이 아직 장면에 붙기 전이라, 붙은 뒤(layout effect)에 바꾸고 한 번 더 그린다. 처음 밝기는 userData 에 기억
  const advanceStage = useThree((st) => st.advance);
  useLayoutEffect(() => {
    let changed = false;
    scene.traverse((o) => {
      const l = o as THREE.Light;
      if (!l.isLight || l.userData.stage || l.userData.keepLit) return;
      if (l.userData.baseIntensity === undefined) l.userData.baseIntensity = l.intensity;
      const want = (l.userData.baseIntensity as number) * lit;
      if (l.intensity !== want) { l.intensity = want; changed = true; }
    });
    if (changed) advanceStage(performance.now());
  });
  // 매 프레임 적용: 바깥 ThreeCanvas 가 camera prop(기본 [0, 0.8, 7])을 다시 넣어도 무대 카메라가 이기게
  cam.position.set(...camera.position);
  cam.fov = camera.fov;
  cam.lookAt(...camera.lookAt);
  cam.updateProjectionMatrix();
  cam.updateMatrixWorld();

  // 바닥에서 뒤쪽 벽으로 부드럽게 휘는 면 (곡률 반경 R)
  const cyc = useMemo(() => {
    const R = 2.2, depth = 14, height = 12, width = 30;
    const pts: THREE.Vector2[] = [];
    pts.push(new THREE.Vector2(depth, 0));
    for (let i = 0; i <= 24; i++) {
      const a = (i / 24) * (Math.PI / 2);
      pts.push(new THREE.Vector2(back + R - Math.sin(a) * R, R - Math.cos(a) * R));
    }
    pts.push(new THREE.Vector2(back, height));
    const shapeZ = pts.map((p) => p.x), shapeY = pts.map((p) => p.y);
    const g = new THREE.BufferGeometry();
    const pos: number[] = [], idx: number[] = [], col: number[] = [];
    const cf = new THREE.Color(floorColor), cw = new THREE.Color(wallColor), tmp = new THREE.Color();
    for (let i = 0; i < pts.length; i++) {
      pos.push(-width / 2, shapeY[i], shapeZ[i], width / 2, shapeY[i], shapeZ[i]);
      tmp.copy(cf).lerp(cw, Math.min(1, Math.max(0, shapeY[i] / 2.6)));
      // 카메라 쪽 바닥은 어둡게 → 자막이 잘 읽히고 무대에 빛이 고인 느낌
      tmp.lerp(cw, Math.min(0.85, Math.max(0, (shapeZ[i] - 1.5) / 5)));
      col.push(tmp.r, tmp.g, tmp.b, tmp.r, tmp.g, tmp.b);
      if (i > 0) { const a = (i - 1) * 2; idx.push(a, a + 1, a + 2, a + 1, a + 3, a + 2); }
    }
    g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
    g.setAttribute('color', new THREE.Float32BufferAttribute(col, 3));
    g.setIndex(idx);
    g.computeVertexNormals();
    return g;
  }, [floorColor, wallColor, back]);

  return (
    <group>
      <hemisphereLight userData={{ stage: true }} args={['#c9d3ff', '#2a2018', 0.3 * lit]} />
      {/* 창가 햇빛: 바닥에 빛이 고이고 가장자리는 어둡게 */}
      <spotLight
        userData={{ stage: true }}
        position={[sun[0] * 0.8, sun[1] * 1.1, sun[2]]}
        angle={0.55}
        penumbra={0.9}
        decay={0}
        intensity={2.2 * lit}
        color={warmth}
        target-position={[0.2, 0, -0.8]}
      />
      <directionalLight
        userData={{ stage: true }}
        castShadow
        position={sun}
        intensity={1.4 * lit}
        color={warmth}
        shadow-mapSize-width={2048}
        shadow-mapSize-height={2048}
        shadow-camera-left={-6}
        shadow-camera-right={6}
        shadow-camera-top={7}
        shadow-camera-bottom={-4}
        shadow-camera-near={0.5}
        shadow-camera-far={30}
        shadow-bias={-0.0004}
        shadow-normalBias={0.02}
        shadow-radius={5}
      />
      {/* 뒤에서 살짝 비추는 테두리 빛 */}
      <directionalLight userData={{ stage: true }} position={[3, 3, -4]} intensity={0.9 * lit} color="#cfd8ff" />
      <mesh geometry={cyc} position={[0, floorY, 0]} receiveShadow>
        <meshStandardMaterial vertexColors roughness={0.92} metalness={0} side={THREE.DoubleSide} />
      </mesh>
    </group>
  );
}

/**
 * 반전 등장 템플릿 "쾅": 제품이 위에서 떨어져 바닥에 내려앉고(눌렸다 튀어 오름), 그 순간 바닥이 울린다.
 *   <Quake impact={IMPACT}>  ← 장면 전체(무대 제외 아무거나)를 감싸면 착지 순간 화면이 흔들린다
 *     <SlamIn impact={IMPACT} position={[x, floorY, z]}> 제품 </SlamIn>
 *     <DustBurst impact={IMPACT} position={[x, floorY, z]} radius={1.2} />
 *   </Quake>
 * impact = 착지 프레임. 나레이션 "그런데!!"가 끝나는 때(장면 시작 약 0.5초 = 15프레임)에 맞춘다.
 */
export const SLAM_IMPACT = 15;

/** 위에서 떨어져 position 에 착지. children 의 바닥(y=0)이 position 높이에 오게 만들어 둔다 */
export function SlamIn({
  impact = SLAM_IMPACT,
  fall = 10,
  dropHeight = 4,
  position = [0, 0, 0],
  children,
}: {
  impact?: number;
  /** 떨어지는 데 걸리는 프레임 */
  fall?: number;
  dropHeight?: number;
  position?: [number, number, number];
  children: React.ReactNode;
}) {
  const f = useCurrentFrame();
  const t = (f - (impact - fall)) / fall; // 0 → 1 에 착지
  let y = 0, sy = 1, sxz = 1, visible = true;
  if (t < 0) visible = false;
  else if (t < 1) {
    y = dropHeight * (1 - t * t); // 중력처럼 점점 빨라짐
    sy = 1 + 0.08 * t; // 떨어지며 살짝 길쭉
    sxz = 1 - 0.04 * t;
  } else {
    const a = f - impact; // 착지 뒤 프레임
    const squash = Math.exp(-a / 3.5) * Math.cos(a * 0.9);
    sy = 1 - 0.22 * squash;
    sxz = 1 + 0.12 * squash;
    y = Math.max(0, 0.18 * Math.sin(Math.min(Math.PI, Math.max(0, (a - 2) / 7) * Math.PI)) * (a > 2 && a < 9 ? 1 : 0));
  }
  return (
    <group position={[position[0], position[1] + y, position[2]]} scale={[sxz, sy, sxz]} visible={visible}>
      {children}
    </group>
  );
}

/** 착지 순간 감싼 것 전체를 짧게 흔든다 (바닥이 울리는 느낌). strength = 첫 흔들림 크기 */
export function Quake({ impact = SLAM_IMPACT, strength = 0.09, frames = 12, children }: { impact?: number; strength?: number; frames?: number; children: React.ReactNode }) {
  const f = useCurrentFrame();
  const a = f - impact;
  let x = 0, y = 0;
  if (a >= 0 && a < frames) {
    const k = strength * (1 - a / frames) ** 2;
    x = k * Math.sin(a * 2.7) * 0.6;
    y = -k * Math.abs(Math.cos(a * 3.3));
  }
  return <group position={[x, y, 0]}>{children}</group>;
}

/** 착지 지점에서 바닥을 따라 퍼지는 먼지 고리 + 작은 먼지 알갱이 */
export function DustBurst({ impact = SLAM_IMPACT, position = [0, 0, 0], radius = 1.2, color = '#efe4d2' }: { impact?: number; position?: [number, number, number]; radius?: number; color?: string }) {
  const f = useCurrentFrame();
  const a = f - impact;
  const bits = useMemo(() => Array.from({ length: 18 }, (_, i) => ({ ang: (i / 18) * Math.PI * 2 + (i % 3) * 0.3, sp: 0.7 + ((i * 37) % 10) / 20, up: 0.25 + ((i * 53) % 10) / 25 })), []);
  if (a < 0 || a > 22) return null;
  const k = a / 22;
  const ease = 1 - (1 - k) ** 3;
  return (
    <group position={position}>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.02, 0]}>
        <ringGeometry args={[radius * (0.35 + 0.9 * ease), radius * (0.55 + 1.05 * ease), 48]} />
        <meshBasicMaterial color={color} transparent opacity={0.75 * (1 - k)} depthWrite={false} />
      </mesh>
      {bits.map((b, i) => {
        const r = radius * (0.5 + b.sp * ease);
        const h = b.up * Math.sin(Math.min(1, k * 1.6) * Math.PI) * 0.6;
        return (
          <mesh key={i} position={[Math.cos(b.ang) * r, 0.03 + h, Math.sin(b.ang) * r * 0.6]} scale={0.06 * (1 - k * 0.6)}>
            <sphereGeometry args={[1, 8, 6]} />
            <meshStandardMaterial color={color} transparent opacity={0.85 * (1 - k)} roughness={1} />
          </mesh>
        );
      })}
    </group>
  );
}

/**
 * 반전 템플릿 "뒤쪽 어두워짐": impact 부터 약 0.5초에 걸쳐 z 보다 뒤에 있는 것(배경·물건·인물)을 어둡게 덮는다.
 * 제품을 z 보다 앞(카메라 쪽)에 두면 제품만 밝게 남는다. 예: 제품 z=0.6 → <BackDim z={0.25} />
 */
export function BackDim({ impact = SLAM_IMPACT, z = 0.25, amount = 0.72, frames = 15 }: { impact?: number; z?: number; amount?: number; frames?: number }) {
  const f = useCurrentFrame();
  const k = interpolate(f, [impact, impact + frames], [0, amount], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  if (k <= 0) return null;
  return (
    <mesh position={[0, 2, z]} renderOrder={10}>
      <planeGeometry args={[40, 30]} />
      <meshBasicMaterial color="#000000" transparent opacity={k} depthWrite={false} toneMapped={false} />
    </mesh>
  );
}

/** 카메라 포커스 프리셋 (장면 키트 배치 기준: 인물 x≈-0.95, 시각화 자리 [0.55, 1.35, -0.5], 반전 제품 [0, FLOOR_Y, 0.6]) */
export const CAMERAS = {
  // 모두 살짝 내려다본다: 무대가 화면 위로 올라와 위쪽 빈 공간이 줄고, 시각화가 자막(약 62%) 위에 선다
  wide: { position: [0.1, 1.9, 7.3] as [number, number, number], lookAt: [0.1, 0.35, -0.6] as [number, number, number], fov: 40 },
  // person: 인물 쪽으로 다가가되 시각화도 화면 안에 남는 중간 거리 (세로 화면에서 얼굴만 잡으면 사실이 안 보인다)
  person: { position: [-0.3, 1.75, 6.0] as [number, number, number], lookAt: [-0.3, 0.6, -0.4] as [number, number, number], fov: 40 },
  // visual: 시각화 쪽으로 다가가되 인물(x≈-0.85)도 화면 안에 남는 거리
  visual: { position: [0.2, 2.0, 6.3] as [number, number, number], lookAt: [0.25, 0.85, -0.5] as [number, number, number], fov: 40 },
  product: { position: [0, 3.0, 6.9] as [number, number, number], lookAt: [0.2, -0.2, 0.5] as [number, number, number], fov: 40 },
  // 인물 없는 장면: 핵심 요소(가운데 [0, 1.35, -0.5])를 크게. center = 주변 소품까지, centerClose = 핵심 요소만
  center: { position: [0, 2.0, 6.8] as [number, number, number], lookAt: [0, 0.75, -0.5] as [number, number, number], fov: 40 },
  centerClose: { position: [0, 2.0, 5.7] as [number, number, number], lookAt: [0, 0.8, -0.5] as [number, number, number], fov: 40 },
};
export type CameraName = keyof typeof CAMERAS;
type Cam = { position: [number, number, number]; lookAt: [number, number, number]; fov: number };

/** 두 카메라 사이를 t(0~1) 만큼 옮긴 카메라. Stage 의 camera 로 넘긴다: <Stage camera={blendCamera('wide', 'visual', t)} /> */
export function blendCamera(a: CameraName | Cam, b: CameraName | Cam, t: number): Cam {
  const A = typeof a === 'string' ? CAMERAS[a] : a;
  const B = typeof b === 'string' ? CAMERAS[b] : b;
  const k = Math.min(1, Math.max(0, t));
  const e = k * k * (3 - 2 * k);
  const mix = (x: number[], y: number[]) => x.map((v, i) => v + (y[i] - v) * e) as [number, number, number];
  return { position: mix(A.position, B.position), lookAt: mix(A.lookAt, B.lookAt), fov: A.fov + (B.fov - A.fov) * e };
}
