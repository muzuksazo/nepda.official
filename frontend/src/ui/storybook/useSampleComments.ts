import { useState } from 'react';
import type { VideoComment } from '../components';

let nextId = 0;

/**
 * 스토리·프로토타입용 댓글 상태: 올리면 맨 아래에 "방금" 내 댓글로 붙고, 내 댓글은 지울 수 있다.
 * 실제로는 서버 API(미정)가 이 역할을 한다.
 */
export function useSampleComments(initial: Record<string, VideoComment[]>, myName: string | undefined) {
  const [comments, setComments] = useState(initial);
  const onAddComment = (videoId: string, text: string) => {
    nextId += 1;
    const comment: VideoComment = { id: `mine-${nextId}`, authorName: myName ?? '나', text, createdAt: new Date().toISOString(), isMine: true };
    setComments((prev) => ({ ...prev, [videoId]: [...(prev[videoId] ?? []), comment] }));
  };
  const onDeleteComment = (videoId: string, commentId: string) => {
    setComments((prev) => ({ ...prev, [videoId]: (prev[videoId] ?? []).filter((c) => c.id !== commentId) }));
  };
  return { comments, onAddComment, onDeleteComment };
}
