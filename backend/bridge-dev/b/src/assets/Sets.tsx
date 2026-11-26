// 장면 공용 세트 (pipeline/src/generated/BSets.tsx 로 복사되어 쓰인다).
// 장면 코드에서:  import { StudyRoom, STUDY, Beam, Prism, RAINBOW } from './BSets';
// 같은 이야기의 장면들이 같은 공간을 쓰게 해서, 장면이 바뀌어도 장소가 이어져 보이게 한다.
//
// StudyRoom: 옛 학자의 서재. 창문 벽, 책장, 러그, 책상 + 책상 위 소품(펼친 책, 책 묶음, 사과, 촛대).
//   물건: Kenney furniture-kit (CC0), Poly Pizza 펼친 책(Quaternius, CC0)·책 묶음(CreativeTrio, CC0),
//         사과(jeremy, CC-BY)·촛대(Jarlan Perez, CC-BY) → CC-BY 는 영상 설명에 작가 표기.
import React, { useMemo } from 'react';
import * as THREE from 'three';
import { FLOOR_Y, Prop, Stage } from './BCharacter';

/** 실제 무지개 일곱 색 (빨강 … 보라) */
export const RAINBOW = ['#e8322a', '#f08a24', '#f2c94c', '#4caf6a', '#3b82c4', '#4b4fa8', '#8a4fb0'];

const F = FLOOR_Y;
const K = 2.04; // Kenney 가구 → 실제 크기 배율 (책상 높이 약 0.78)
const WALL_Z = -2.6;
const WALL_H = 1.29 * K * 1.25; // Kenney 벽 한 칸 (폭 1 : 높이 1.29)
const WALL_W = WALL_H / 1.29;
const WIN_X = -1.3;
const DESK_TOP = F + 0.384 * K;
const KF = 'bassets/kenney/furniture-kit/';
const PP = 'bassets/polypizza/';
const WALL = { _defaultMat: '#6f6253', wood: '#5a3d2a', metalDark: '#2b2a29' };
const WOOD = { wood: '#6b4a33', woodDark: '#4a3122', metal: '#3a3836', metalDark: '#2b2a29' };

/** 서재 안의 자리들 (장면 코드가 물체·인물을 놓을 때 쓴다) */
export const STUDY = {
  floorY: F,
  deskTop: DESK_TOP,
  /** 책상 위 프리즘 자리 */
  prism: [0.42, DESK_TOP + 0.2, -0.45] as [number, number, number],
  /** 창문 안쪽 (햇빛이 들어오는 점) */
  windowLight: [WIN_X, F + 2.55, WALL_Z + 0.08] as [number, number, number],
  /** 인물이 서는 자리 (책상 왼쪽) */
  person: [-1.22, F, -0.15] as [number, number, number],
  personRotY: 0.55,
  /** 책상 위 빈 벽 앞 공중: 도형을 띄워 보여 주는 자리 (화면 위쪽 1/3, 자막과 안 겹침) */
  air: [0.35, 1.55, -0.6] as [number, number, number],
  camera: { position: [0, 1.45, 9.2] as [number, number, number], lookAt: [0, 0.6, -1] as [number, number, number], fov: 35 },
};

export function StudyRoom({
  windowGlow = 0.9,
  prism = true,
  prismGlow = 0,
  camera = STUDY.camera,
  deskProps = true,
}: {
  /** 창문 밝기 0~1 */
  windowGlow?: number;
  /** 책상 위 프리즘 */
  prism?: boolean;
  /** 프리즘 안쪽 빛 0~1 (빛이 닿았을 때) */
  prismGlow?: number;
  camera?: { position: [number, number, number]; lookAt: [number, number, number]; fov: number };
  /** 책상 위 소품 (책·사과·촛대) */
  deskProps?: boolean;
}) {
  return (
    <group>
      <Stage back={-4.8} hdri="bassets/polyhaven/hdri/brown_photostudio_02_1k.hdr" envIntensity={0.35} floorColor="#4a3f36" camera={camera} />

      {/* 뒷벽: 창문 벽 + 민 벽 */}
      <Prop file={KF + 'wallWindow.glb'} position={[WIN_X, F, WALL_Z]} height={WALL_H} colors={WALL}
        glow={{ glass: new THREE.Color('#f3cf96').multiplyScalar(windowGlow).getStyle() }} />
      {[[WIN_X + WALL_W, 0], [WIN_X - WALL_W, 0], [WIN_X, 1], [WIN_X + WALL_W, 1], [WIN_X - WALL_W, 1]].map(([x, row], i) => (
        <Prop key={i} file={KF + 'wall.glb'} position={[x, F + row * WALL_H, WALL_Z]} height={WALL_H} colors={WALL} />
      ))}

      {/* 책장 (오른쪽 뒤) + 꽂힌 책 */}
      <Prop file={KF + 'bookcaseOpen.glb'} position={[1.3, F, WALL_Z + 0.35]} height={0.88 * K * 1.1} colors={WOOD} />
      {[0.5, 0.98, 1.45].map((y, i) => (
        <Prop key={i} file={KF + 'books.glb'} position={[1.15 + (i % 2) * 0.25, F + y, WALL_Z + 0.35]} height={0.3} rotationY={i === 1 ? Math.PI : 0}
          colors={{ carpetDarker: '#7a2b24', carpetWhite: '#d9cdb6', plant: '#2f5a44', metal: '#3a3836' }} />
      ))}

      {/* 러그 + 책상 */}
      <Prop file={KF + 'rugRectangle.glb'} position={[-0.4, F + 0.002, -0.2]} width={3.0} colors={{ carpet: '#5e2a24', carpetDarker: '#43201c' }} shadow={false} />
      <Prop file={KF + 'desk.glb'} position={[-0.05, F, -0.55]} height={0.384 * K} colors={WOOD} />

      {deskProps && (
        <>
          <Prop file={PP + 'book__FsCIGEfTEs__FsCIGEfTEs.glb'} position={[-0.35, DESK_TOP, -0.4]} width={0.42} rotationY={0.25} />
          <Prop file={PP + 'book__dxt7dETAy9__dxt7dETAy9.glb'} position={[0.05, DESK_TOP, -0.78]} height={0.34} rotationY={-0.3} />
          <Prop file={PP + 'apple__4tOmpD9_xsV__4tOmpD9-xsV.glb'} position={[-0.55, DESK_TOP, -0.22]} height={0.17} />
          <Prop file={PP + 'candle__8apROCXjeN4__8apROCXjeN4.glb'} position={[-0.68, DESK_TOP, -0.75]} height={0.32} />
        </>
      )}
      {prism && <Prism position={STUDY.prism} glow={prismGlow} />}
    </group>
  );
}

const PRISM_EDGES = new THREE.EdgesGeometry(new THREE.CylinderGeometry(0.2, 0.2, 0.34, 3));
/** 유리 삼각 프리즘 (투명 몸통 + 흰 모서리). glow 0~1 이면 안쪽이 환해진다 */
export function Prism({ position, glow = 0, scale = 1 }: { position: [number, number, number]; glow?: number; scale?: number }) {
  return (
    <group position={position} scale={scale}>
      <group rotation={[Math.PI / 2, 0, Math.PI / 6]}>
        <mesh castShadow>
          <cylinderGeometry args={[0.2, 0.2, 0.34, 3]} />
          <meshPhysicalMaterial color="#dff0ff" roughness={0.05} metalness={0} clearcoat={1} transparent opacity={0.45} depthWrite={false} envMapIntensity={2} />
        </mesh>
        <lineSegments geometry={PRISM_EDGES}>
          <lineBasicMaterial color="#ffffff" transparent opacity={0.9} toneMapped={false} />
        </lineSegments>
      </group>
      {glow > 0 && (
        <mesh scale={0.11}>
          <sphereGeometry args={[1, 24, 16]} />
          <meshBasicMaterial color="#fff6e0" transparent opacity={0.35 * glow} blending={THREE.AdditiveBlending} depthWrite={false} toneMapped={false} />
        </mesh>
      )}
    </group>
  );
}

/** from → to 방향으로 k(0~1) 만큼 뻗는 빛줄기. glow 면 겹칠수록 밝아진다 */
export function Beam({ from, to, k, width, color, opacity = 1, glow }: { from: number[]; to: number[]; k: number; width: number; color: string; opacity?: number; glow?: boolean }) {
  const { q, len } = useMemo(() => {
    const d = new THREE.Vector3(to[0] - from[0], to[1] - from[1], to[2] - from[2]);
    const len = d.length();
    return { q: new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(1, 0, 0), d.normalize()), len };
  }, [from.join(), to.join()]);
  const l = Math.max(k * len, 1e-4);
  return (
    <group position={from as [number, number, number]} quaternion={q}>
      <mesh position={[l / 2, 0, 0]} scale={[l, 1, 1]}>
        <boxGeometry args={[1, width, width]} />
        <meshBasicMaterial color={color} transparent opacity={opacity} blending={glow ? THREE.AdditiveBlending : THREE.NormalBlending} depthWrite={false} toneMapped={false} />
      </mesh>
    </group>
  );
}

/** 장면 1 끝에서 바닥에 깔린 일곱 색 띠의 자리 (i = 0 빨강 … 6 보라): 다음 장면이 여기서 이어 받는다 */
export function floorStrip(i: number): { x: number; y: number; z: number; len: number } {
  const p = STUDY.prism;
  const sx = p[0] + 0.12;
  const drop = p[1] - F - 0.01;
  const ang = 0.8 + i * 0.06;
  return { x: sx + drop / Math.tan(ang) + 0.17, y: F + 0.006 + i * 0.0005, z: p[2] + 0.04 + i * 0.01 + 0.25, len: 0.34 };
}
