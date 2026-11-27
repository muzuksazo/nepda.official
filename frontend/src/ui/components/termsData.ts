/** 가입할 때 받는 동의 항목 */
export type AgreementKey = 'age' | 'terms' | 'privacy' | 'ai' | 'marketing';
/** "보기"로 여는 문서 */
export type AgreementDoc = 'terms' | 'privacy' | 'ai' | 'marketing';

export interface AgreementItem {
  key: AgreementKey;
  label: string;
  isRequired: boolean;
  /** 한 줄 설명 (무엇에 동의하는지 짧게) */
  hint?: string;
  doc?: AgreementDoc;
}

/** 동의 항목 (법무 확인 전 제안 — 문구·항목은 바뀔 수 있다) */
export const AGREEMENTS: readonly AgreementItem[] = [
  { key: 'age', label: '만 14세 이상이에요', isRequired: true },
  { key: 'terms', label: '이용약관에 동의해요', isRequired: true, doc: 'terms' },
  { key: 'privacy', label: '개인정보 수집·이용에 동의해요', isRequired: true, doc: 'privacy' },
  {
    key: 'ai',
    label: '영상·제품 정보를 AI로 처리하는 데 동의해요',
    isRequired: true,
    hint: '올린 영상과 제품 정보로 훅 영상을 만들어요.',
    doc: 'ai',
  },
  { key: 'marketing', label: '이벤트·혜택 알림 받기', isRequired: false, hint: '안 받아도 쓰는 데 문제없어요.', doc: 'marketing' },
];

export type Agreements = Record<AgreementKey, boolean>;

/** 아무것도 체크하지 않은 상태 */
export const NO_AGREEMENTS: Agreements = { age: false, terms: false, privacy: false, ai: false, marketing: false };
