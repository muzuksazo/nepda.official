import { useState } from 'react';
import { CreatorProfileScreen } from '../screens/CreatorProfileScreen';
import { sampleCreator } from '../screens/sampleProjects';

/**
 * 화면 하나짜리 스토리에서도 닉네임을 누르면 만든 사람 프로필이 열리게 한다.
 * 프로필에서 뒤로를 누르면 원래 화면으로 돌아간다. (여러 화면을 오가는 전체 흐름은 "전체 흐름 (클릭 프로토타입)" 스토리)
 */
export function useCreatorPeek() {
  const [creatorName, setCreatorName] = useState<string | null>(null);
  let profileScreen = null;
  if (creatorName) {
    const { profile, videos } = sampleCreator(creatorName);
    profileScreen = <CreatorProfileScreen creator={profile} videos={videos} onBack={() => setCreatorName(null)} />;
  }
  return { onOpenCreator: setCreatorName, profileScreen };
}
