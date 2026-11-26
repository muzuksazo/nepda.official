// 감정 표현 견본: 왼쪽부터 기본 / look / tilt / nod / surprise / droop (프레임 중간에 최대)
import React from 'react';
import { Character, Stage, FLOOR_Y } from './BCharacter';

const TYPES = ['none', 'look', 'tilt', 'nod', 'surprise', 'droop'] as const;
export default function Scene({ durationInFrames: d }: { durationInFrames: number; color: string }) {
  return (
    <group>
      <Stage />
      {TYPES.map((t, i) => (
        <Character
          key={t}
          file="bassets/uacp/OldClassy_Male.gltf"
          colors={{ Skin: '#f0c9a6' }}
          timeline={[{ clip: 'Idle', from: 0, to: d + 1 }]}
          emotes={t === 'none' ? [] : [{ type: t, from: 0, to: d }]}
          position={[-1.9 + i * 0.76, FLOOR_Y, -1]}
          rotationY={0}
          height={1.15}
        />
      ))}
    </group>
  );
}
