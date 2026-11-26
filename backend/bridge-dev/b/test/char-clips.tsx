// 동작 견본: 정면(rotationY=0)으로 선 인물 6명이 각각 다른 동작을 한다. 팔이 화면 어느 쪽으로 가는지 확인용.
import React from 'react';
import { Character, type ClipName } from './BCharacter';

const CLIPS: ClipName[] = ['Interact', 'PickUp_Table', 'Spell_Simple_Shoot', 'Spell_Simple_Enter', 'Push_Loop', 'Idle_Talking_Loop'];

export default function Scene({ durationInFrames: d }: { durationInFrames: number; color: string }) {
  return (
    <group>
      <ambientLight intensity={0.5} />
      <directionalLight position={[-3, 5, 5]} intensity={1.4} />
      {CLIPS.map((clip, i) => (
        <Character
          key={clip}
          timeline={[{ clip, from: 0, to: d + 1 }]}
          position={[-1.2 + (i % 3) * 1.2, i < 3 ? 2.0 : 0.0, -1.5]}
          height={1.5}
        />
      ))}
    </group>
  );
}
