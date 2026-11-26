// 제품 3D 모델: PIEV 에어워셔 고체 탈취제 (b/product/piev 영상을 보고 만든 것).
// 장면 코드에서:  import Product from './BProduct';   <Product height={1.2} lidOpen={1} />
//   바닥(y=0)에 서고, 높이는 height. lidOpen 0 = 뚜껑 닫힘, 1 = 뚜껑을 들어 옆에 세워 둠(초록 젤이 보임).
// 생김새: 위가 살짝 넓은 무광 반투명 흰 유리컵(높이:지름 ≈ 1.2:1, 두꺼운 테두리), 안에 윤기 있는 짙은 초록 젤,
//         은색 금속 뚜껑, 앞면에 세이지색 타원 라벨("PIEV AIRWASHER" 둥근 글씨, 편백 가지 그림, 리본, "PHYTONCIDE").
import React, { useMemo } from 'react';
import * as THREE from 'three';

const H = 1; // 모델 기준 높이 (scale 로 height 에 맞춘다)
const R_TOP = 0.43;
const R_BOT = 0.4;
const WALL = 0.035;
const GEL_Y = 0.86; // 젤 윗면 높이 (컵 높이 비율)
const SAGE = '#5f8f80';

function makeLabelTexture(): THREE.CanvasTexture {
  const W = 512, Hh = 640;
  const cv = document.createElement('canvas');
  cv.width = W;
  cv.height = Hh;
  const g = cv.getContext('2d')!;
  g.clearRect(0, 0, W, Hh);
  // 타원 배지 (위는 둥근 아치, 아래는 리본)
  const cx = W / 2, cy = Hh * 0.46, rx = W * 0.42, ry = Hh * 0.4;
  g.fillStyle = '#fbfbf8';
  g.beginPath();
  g.ellipse(cx, cy, rx, ry, 0, 0, Math.PI * 2);
  g.fill();
  g.strokeStyle = SAGE;
  g.lineWidth = 9;
  g.beginPath();
  g.ellipse(cx, cy, rx - 6, ry - 6, 0, 0, Math.PI * 2);
  g.stroke();
  g.lineWidth = 2.5;
  g.setLineDash([3, 6]);
  g.beginPath();
  g.ellipse(cx, cy, rx - 20, ry - 20, 0, 0, Math.PI * 2);
  g.stroke();
  g.setLineDash([]);
  // 둥근 글씨 "PIEV AIRWASHER"
  const text = 'PIEV AIRWASHER';
  g.fillStyle = SAGE;
  g.font = 'bold 56px Georgia, "Times New Roman", serif';
  g.textAlign = 'center';
  g.textBaseline = 'middle';
  const arcR = rx - 58;
  const span = Math.PI * 0.7;
  [...text].forEach((ch, i) => {
    const a = -Math.PI / 2 - span / 2 + (span * (i + 0.5)) / text.length;
    g.save();
    g.translate(cx + Math.cos(a) * arcR, cy - 20 + Math.sin(a) * (arcR * 1.05));
    g.rotate(a + Math.PI / 2);
    g.fillText(ch, 0, 0);
    g.restore();
  });
  // 편백 가지 그림
  g.strokeStyle = SAGE;
  g.lineCap = 'round';
  const stem = (x0: number, y0: number, x1: number, y1: number, w: number) => {
    g.lineWidth = w;
    g.beginPath();
    g.moveTo(x0, y0);
    g.lineTo(x1, y1);
    g.stroke();
  };
  stem(cx, cy + 150, cx, cy - 70, 5);
  for (let k = 0; k < 7; k++) {
    const y = cy - 50 + k * 26;
    const len = 70 - Math.abs(k - 3) * 8;
    for (const s of [-1, 1]) {
      stem(cx, y, cx + s * len, y - 26, 3.5);
      for (let t = 1; t <= 4; t++) {
        const px = cx + (s * len * t) / 5, py = y - (26 * t) / 5;
        stem(px, py, px + s * 9, py - 13, 2.5);
        stem(px, py, px + s * 12, py + 5, 2.5);
      }
    }
  }
  // 리본 + "PHYTONCIDE"
  g.fillStyle = '#fbfbf8';
  g.strokeStyle = SAGE;
  g.lineWidth = 4;
  g.beginPath();
  g.moveTo(cx - 170, cy + 188);
  g.quadraticCurveTo(cx, cy + 238, cx + 170, cy + 188);
  g.lineTo(cx + 160, cy + 232);
  g.quadraticCurveTo(cx, cy + 282, cx - 160, cy + 232);
  g.closePath();
  g.fill();
  g.stroke();
  g.fillStyle = SAGE;
  g.font = 'bold 26px Georgia, serif';
  g.fillText('PHYTONCIDE', cx, cy + 236);
  const tex = new THREE.CanvasTexture(cv);
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.anisotropy = 8;
  return tex;
}

export default function Product({ height = 1.2, lidOpen = 1, glow = 0 }: { height?: number; lidOpen?: number; glow?: number }) {
  const label = useMemo(() => makeLabelTexture(), []);
  const s = height / H;
  // 컵 옆면: 바깥 + 안쪽 (위가 살짝 넓다)
  const outer = useMemo(() => new THREE.CylinderGeometry(R_TOP, R_BOT, H, 64, 1, true), []);
  const inner = useMemo(() => new THREE.CylinderGeometry(R_TOP - WALL, R_BOT - WALL, H - 0.06, 64, 1, true), []);
  const rim = useMemo(() => new THREE.RingGeometry(R_TOP - WALL, R_TOP, 64), []);
  // 라벨: 컵 옆면을 따라 휜 조각 (앞쪽 약 70°)
  const labelGeo = useMemo(() => {
    const yMid = H * 0.42, hLab = H * 0.62;
    // 컵처럼 위가 넓은 원뿔대로 (곧은 원통이면 윗부분이 유리 안으로 묻힌다)
    const rAt = (y: number) => R_BOT + ((R_TOP - R_BOT) * y) / H + 0.004;
    const arc = (98 * Math.PI) / 180;
    return new THREE.CylinderGeometry(rAt(yMid + hLab / 2), rAt(yMid - hLab / 2), hLab, 48, 1, true, -arc / 2, arc);
  }, []);
  const gelR = R_BOT - WALL + (R_TOP - R_BOT) * GEL_Y;

  // 뚜껑: 닫힘(컵 위) → 열림(오른쪽 옆에 비스듬히 세움)
  // 뚜껑: 먼저 위로 들린 뒤 옆으로 옮겨 컵 오른쪽 바닥에 눕힌다 (어느 순간에도 컵과 겹치지 않게)
  const lt = Math.min(1, Math.max(0, lidOpen));
  const sm = (x: number) => { const k = Math.min(1, Math.max(0, x)); return k * k * (3 - 2 * k); };
  const LID_R = R_TOP + 0.015;
  // 세 단계: 위로 들기(0~0.35) → 컵 밖으로 옆 이동(0.35~0.7, 높이 유지) → 바닥으로 내려놓기(0.7~1)
  const lift = sm(lt / 0.35), slide = sm((lt - 0.35) / 0.35), drop = sm((lt - 0.7) / 0.3);
  const TOP_Y = H + 0.036, HIGH = H + 0.45, OUT_X = R_TOP + LID_R + 0.1;
  const lidPos: [number, number, number] = [
    slide * OUT_X,
    TOP_Y + (HIGH - TOP_Y) * lift - (HIGH - 0.036) * drop,
    slide * 0.12,
  ];
  const lidRot: [number, number, number] = [0, 0, -Math.sin(Math.PI * slide) * 0.3];

  return (
    <group scale={s}>
      {/* 유리컵 */}
      <mesh geometry={outer} position={[0, H / 2, 0]} castShadow receiveShadow>
        <meshPhysicalMaterial color="#eef0f1" roughness={0.55} metalness={0} clearcoat={0.3} transparent opacity={0.95} side={THREE.FrontSide} />
      </mesh>
      <mesh geometry={inner} position={[0, H / 2 + 0.03, 0]}>
        <meshStandardMaterial color="#e2e6e6" roughness={0.6} side={THREE.BackSide} />
      </mesh>
      <mesh geometry={rim} position={[0, H, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <meshStandardMaterial color="#f7f8f8" roughness={0.4} />
      </mesh>
      {/* 바닥 */}
      <mesh position={[0, 0.03, 0]} receiveShadow castShadow>
        <cylinderGeometry args={[R_BOT, R_BOT, 0.06, 64]} />
        <meshStandardMaterial color="#e6e9ea" roughness={0.6} />
      </mesh>
      {/* 초록 젤 (윗면 윤기) */}
      <mesh position={[0, (H * GEL_Y) / 2, 0]}>
        <cylinderGeometry args={[gelR, R_BOT - WALL, H * GEL_Y - 0.02, 64]} />
        <meshStandardMaterial color="#1f6e48" roughness={0.35} />
      </mesh>
      <mesh position={[0, H * GEL_Y - 0.008, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <circleGeometry args={[gelR, 64]} />
        <meshPhysicalMaterial color="#0f4a2e" roughness={0.18} clearcoat={1} clearcoatRoughness={0.1} envMapIntensity={0.6} emissive="#0f4a2e" emissiveIntensity={0.04 + glow * 0.5} />
      </mesh>
      {/* 라벨 */}
      <mesh geometry={labelGeo} position={[0, H * 0.42, 0]}>
        <meshStandardMaterial map={label} transparent roughness={0.7} side={THREE.FrontSide} />
      </mesh>
      {/* 은색 금속 뚜껑 */}
      <group position={lidPos} rotation={lidRot}>
        <mesh castShadow>
          <cylinderGeometry args={[R_TOP + 0.015, R_TOP + 0.015, 0.07, 64]} />
          <meshStandardMaterial color="#c9ccd0" metalness={0.9} roughness={0.28} />
        </mesh>
        <mesh position={[0, 0.036, 0]} rotation={[-Math.PI / 2, 0, 0]}>
          <circleGeometry args={[R_TOP + 0.015, 64]} />
          <meshStandardMaterial color="#d6d9dc" metalness={0.95} roughness={0.22} />
        </mesh>
      </group>
    </group>
  );
}
