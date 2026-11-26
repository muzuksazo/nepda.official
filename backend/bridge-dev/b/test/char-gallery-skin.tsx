// 캐릭터 팩 미리보기 (skin)
import React from 'react';
import { Character, type ClipName } from './BCharacter';

const CAST: [string, ClipName][] = [
  ['OldClassy_Male', 'Idle'], ['Doctor_Female_Young', 'Victory'], ['Suit_Male', 'Walk'], ['Casual_Female', 'Idle'], ['Worker_Male', 'PickUp'],
  ['Chef_Female', 'Victory'], ['Wizard', 'Idle'], ['Kimono_Female', 'Walk'], ['Doctor_Male_Old', 'Idle'], ['Casual2_Male', 'Victory'],
];

export default function Scene({ durationInFrames: d }: { durationInFrames: number; color: string }) {
  return (
    <group>
      <ambientLight intensity={0.55} />
      <directionalLight position={[-3, 5, 5]} intensity={1.5} />
      <directionalLight position={[3, 2, -3]} intensity={0.8} />
      {CAST.map(([name, clip], i) => (
        <Character
          key={name}
          file={`bassets/uacp/${name}.gltf`}
          timeline={[{ clip, from: 0, to: d + 1 }]}
          position={[-1.8 + (i % 5) * 0.9, i < 5 ? 2.3 : 0.2, -3]}
          rotationY={0.35}
          height={1.3}
          colors={{ Skin: '#f0c9a6' }}
        />
      ))}
    </group>
  );
}
