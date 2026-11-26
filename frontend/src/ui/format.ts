/** 좋아요 수 같은 숫자를 짧게: 1,234 → "1,234", 12,300 → "1.2만" */
export function formatCount(count: number): string {
  if (count < 10000) return count.toLocaleString('ko-KR');
  const man = count / 10000;
  return `${man >= 100 ? Math.round(man) : Math.round(man * 10) / 10}만`;
}
