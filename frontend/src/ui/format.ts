/** 좋아요 수 같은 숫자를 짧게: 1,234 → "1,234", 12,300 → "1.2만" */
export function formatCount(count: number): string {
  if (count < 10000) return count.toLocaleString('ko-KR');
  const man = count / 10000;
  return `${man >= 100 ? Math.round(man) : Math.round(man * 10) / 10}만`;
}

/** 가격: 12900 → "12,900원" */
export function formatWon(price: number): string {
  return `${price.toLocaleString('ko-KR')}원`;
}

/**
 * 알림 시각: 방금 · 5분 전 · 3시간 전 · 어제 · 3일 전 · 11월 2일.
 * now를 넘기면 그 시각 기준으로 센다(스토리·테스트에서 결과를 고정할 때).
 */
export function formatRelativeTime(iso: string, now: Date = new Date()): string {
  const then = new Date(iso);
  const minutes = Math.floor((now.getTime() - then.getTime()) / 60000);
  if (minutes < 1) return '방금';
  if (minutes < 60) return `${minutes}분 전`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24 && then.getDate() === now.getDate()) return `${hours}시간 전`;
  const days = Math.round((startOfDay(now) - startOfDay(then)) / 86400000);
  if (days <= 1) return '어제';
  if (days < 7) return `${days}일 전`;
  return `${then.getMonth() + 1}월 ${then.getDate()}일`;
}

function startOfDay(date: Date): number {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime();
}
