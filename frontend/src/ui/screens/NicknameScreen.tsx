import { useState, type ReactNode } from 'react';
import { Button, MobileScreen, PageHeader, ScreenTitle, TextField } from '../components';
import { Check } from '../icons';

/** 닉네임 규칙 (임시값 — 정책 확정 전) */
export const NICKNAME_MIN = 2;
export const NICKNAME_MAX = 12;
const NICKNAME_PATTERN = /^[가-힣a-zA-Z0-9_]+$/;

/** 서버에 묻기 전에 화면에서 바로 알 수 있는 규칙 */
function checkNicknameRule(name: string): string | null {
  const trimmed = name.trim();
  if (trimmed.length === 0) return null;
  if (/\s/.test(trimmed)) return '띄어쓰기 없이 써 주세요';
  if (!NICKNAME_PATTERN.test(trimmed)) return '한글·영문·숫자·밑줄(_)만 쓸 수 있어요';
  if (trimmed.length < NICKNAME_MIN) return `${NICKNAME_MIN}자 이상 써 주세요`;
  return null;
}

export interface NicknameScreenProps {
  /** 처음 채워 둘 이름 (구글 이름이나 추천 이름) */
  initialNickname?: string;
  /**
   * 서버 확인 결과 (화면 규칙을 통과한 이름만 묻는다).
   * checking: 확인 중 · available: 쓸 수 있음 · taken: 이미 있음 · blocked: 쓸 수 없는 말
   */
  availability?: 'idle' | 'checking' | 'available' | 'taken' | 'blocked';
  /** 이름이 바뀔 때 (서버 중복 확인을 다시 하도록) */
  onNicknameChange?: (nickname: string) => void;
  /** "냅다 시작하기" — 가입을 마친다 */
  onSubmit?: (nickname: string) => void;
  /** 가입 저장 중 */
  isSubmitting?: boolean;
  /** 뒤로: 가입을 그만두고 로그인 화면으로 */
  onBack?: () => void;
}

/** 회원가입 2단계 — 커뮤니티에 보일 닉네임 정하기. 약관 동의 다음, 홈 직전에 한 번 거친다. */
export function NicknameScreen({
  initialNickname = '',
  availability = 'idle',
  onNicknameChange,
  onSubmit,
  isSubmitting = false,
  onBack,
}: NicknameScreenProps) {
  const [nickname, setNickname] = useState(initialNickname);
  const ruleError = checkNicknameRule(nickname);
  const isEmpty = nickname.trim().length === 0;

  let message: ReactNode = '한글·영문·숫자로 2~12자, 나중에 바꿀 수 있어요';
  let tone: 'neutral' | 'success' | 'error' = 'neutral';
  if (ruleError) {
    message = ruleError;
    tone = 'error';
  } else if (!isEmpty && availability === 'checking') {
    message = '쓸 수 있는지 보는 중…';
  } else if (!isEmpty && availability === 'taken') {
    message = '이미 누가 쓰고 있어요. 다른 이름은 어때요?';
    tone = 'error';
  } else if (!isEmpty && availability === 'blocked') {
    message = '쓸 수 없는 말이 들어 있어요';
    tone = 'error';
  } else if (!isEmpty && availability === 'available') {
    message = (
      <>
        <Check size={16} strokeWidth={3} aria-hidden="true" />
        좋은 이름이에요
      </>
    );
    tone = 'success';
  }

  const canSubmit = !isEmpty && !ruleError && availability === 'available' && !isSubmitting;

  return (
    <MobileScreen
      header={<PageHeader title="가입하기" onBack={onBack} />}
      footer={
        <Button
          label={isSubmitting ? '들어가는 중…' : '냅다 시작하기'}
          isBlock
          isDisabled={!canSubmit}
          onClick={() => onSubmit?.(nickname.trim())}
        />
      }
    >
      <ScreenTitle title="뭐라고 불러 드릴까요?" description="커뮤니티에 영상을 올리면 이 이름으로 보여요." />

      <TextField
        label="닉네임"
        value={nickname}
        onChange={(next) => {
          setNickname(next);
          onNicknameChange?.(next.trim());
        }}
        placeholder="예: 도마왕"
        maxLength={NICKNAME_MAX}
        hasClear
        hasCounter
        autoComplete="nickname"
        message={message}
        messageTone={tone}
      />
    </MobileScreen>
  );
}
