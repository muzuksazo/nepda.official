import { useEffect, useId, useRef, useState, type FormEvent, type KeyboardEvent } from 'react';
import { formatRelativeTime } from '../format';
import { Comment as CommentIcon, X } from '../icons';
import { Avatar } from './layout';

/** 댓글 한 개 (API 미정 — 댓글 목록·쓰기·지우기 API가 아직 없다) */
export interface VideoComment {
  id: string;
  authorName: string;
  text: string;
  /** ISO 시각 */
  createdAt: string;
  /** 내가 쓴 댓글이면 지울 수 있다 */
  isMine?: boolean;
}

/** 댓글 한 개의 최대 글자 수 (임시값) */
export const COMMENT_MAX = 200;

export interface CommentSheetProps {
  isOpen: boolean;
  /** 오래된 것부터 */
  comments: VideoComment[];
  /** 입력 줄 왼쪽에 보일 내 닉네임 */
  myName?: string;
  /** 상대 시각 기준 (스토리·테스트에서 고정할 때) */
  now?: Date;
  onSubmit: (text: string) => void;
  onDelete?: (id: string) => void;
  onClose: () => void;
}

/** 아래에서 올라오는 댓글 시트. 목록은 시트 안에서만 스크롤되고, 입력 줄은 맨 아래에 붙어 있다 */
export function CommentSheet({ isOpen, ...rest }: CommentSheetProps) {
  return isOpen ? <CommentSheetDialog {...rest} /> : null;
}

function CommentSheetDialog({ comments, myName, now, onSubmit, onDelete, onClose }: Omit<CommentSheetProps, 'isOpen'>) {
  const titleId = useId();
  const inputId = useId();
  const sheetRef = useRef<HTMLDivElement>(null);
  const listRef = useRef<HTMLUListElement>(null);
  const [text, setText] = useState('');
  const [openedAt] = useState(() => new Date());
  // 시트를 연 버튼을 기억해 두었다가 닫힐 때 포커스를 돌려준다
  const [opener] = useState(() => (document.activeElement instanceof HTMLElement ? document.activeElement : null));
  const countRef = useRef(comments.length);
  const base = now ?? openedAt;

  useEffect(() => {
    // 열자마자 키보드가 올라오지 않게 입력칸 대신 시트에 포커스를 둔다
    sheetRef.current?.focus();
    return () => opener?.focus();
  }, [opener]);

  // 댓글이 늘면(내가 올리면) 맨 아래 새 댓글이 보이게 내린다
  useEffect(() => {
    if (comments.length > countRef.current) listRef.current?.lastElementChild?.scrollIntoView({ block: 'nearest' });
    countRef.current = comments.length;
  }, [comments.length]);

  const submit = (event?: FormEvent) => {
    event?.preventDefault();
    const trimmed = text.trim();
    if (!trimmed) return;
    onSubmit(trimmed);
    setText('');
  };

  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key === 'Escape') {
      event.stopPropagation();
      onClose();
      return;
    }
    if (event.key !== 'Tab') return;
    // Tab이 시트 밖으로 나가지 않게 처음·끝에서 되돌린다
    const focusables = sheetRef.current?.querySelectorAll<HTMLElement>('button:not(:disabled), input');
    if (!focusables || focusables.length === 0) return;
    const first = focusables[0];
    const last = focusables[focusables.length - 1];
    const active = document.activeElement;
    if (event.shiftKey && (active === first || active === sheetRef.current)) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && active === last) {
      event.preventDefault();
      first.focus();
    }
  };

  return (
    <div className="n-sheet-layer">
      <div className="n-sheet-backdrop" onClick={onClose} />
      <div
        ref={sheetRef}
        className="n-sheet n-comments"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        onKeyDown={onKeyDown}
      >
        <div className="n-comments__head">
          <h2 id={titleId} className="n-comments__title">
            댓글 <span className="n-num n-muted">{comments.length}</span>
          </h2>
          <button type="button" className="n-comments__close" aria-label="댓글 닫기" onClick={onClose}>
            <X size={22} />
          </button>
        </div>

        {comments.length === 0 ? (
          <div className="n-comments__empty">
            <CommentIcon size={32} aria-hidden="true" />
            <p className="n-bold">아직 조용해요</p>
            <p className="n-small n-muted">첫 댓글로 분위기 띄워 줘요.</p>
          </div>
        ) : (
          <ul ref={listRef} className="n-comments__list" aria-label="댓글 목록">
            {comments.map((comment) => (
              <li key={comment.id} className="n-comment">
                <Avatar name={comment.authorName} />
                <div className="n-comment__main">
                  <p className="n-comment__meta">
                    <b>{comment.authorName}</b>
                    <span className="n-comment__time">{formatRelativeTime(comment.createdAt, base)}</span>
                  </p>
                  <p className="n-comment__text">{comment.text}</p>
                </div>
                {comment.isMine && onDelete ? (
                  <button
                    type="button"
                    className="n-comment__delete"
                    aria-label="내 댓글 지우기"
                    onClick={() => {
                      onDelete(comment.id);
                      // 누른 버튼이 사라지므로 포커스를 시트에 남겨 둔다 (Esc·Tab이 계속 시트 안에서 동작하게)
                      sheetRef.current?.focus();
                    }}
                  >
                    지우기
                  </button>
                ) : null}
              </li>
            ))}
          </ul>
        )}

        <form className="n-comments__composer" onSubmit={submit}>
          <Avatar name={myName} />
          <label htmlFor={inputId} className="napda-visually-hidden">
            댓글
          </label>
          <input
            id={inputId}
            className="n-comments__input"
            value={text}
            maxLength={COMMENT_MAX}
            placeholder="댓글 달기…"
            autoComplete="off"
            enterKeyHint="send"
            onChange={(e) => setText(e.target.value)}
          />
          <button type="submit" className="n-comments__send" disabled={!text.trim()}>
            올리기
          </button>
        </form>
      </div>
    </div>
  );
}
