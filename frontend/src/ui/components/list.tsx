import { useId, type ReactNode } from 'react';
import { ChevronRight } from '../icons';

export interface ListGroupProps {
  title: string;
  /** 줄 목록 위에 두는 설정 컨트롤(예: 화면 모드 고르기) */
  lead?: ReactNode;
  /** ListRow들 */
  children?: ReactNode;
  /** 목록 아래 한 줄 안내 */
  note?: ReactNode;
}

/** 설정·메뉴 한 묶음: 작은 제목 + 줄 목록. 카드로 감싸지 않고 화면에 바로 놓는다. */
export function ListGroup({ title, lead, children, note }: ListGroupProps) {
  const titleId = useId();
  return (
    <section className="n-list-group" aria-labelledby={titleId}>
      <h2 id={titleId} className="n-list-group__title">
        {title}
      </h2>
      {lead ? <div className="n-list-group__lead">{lead}</div> : null}
      {children ? <ul className="n-list">{children}</ul> : null}
      {note ? <p className="n-list-group__note">{note}</p> : null}
    </section>
  );
}

export interface ListRowProps {
  /** 왼쪽 20px 아이콘 */
  icon?: ReactNode;
  label: string;
  description?: string;
  /** 오른쪽 끝의 값·배지 */
  endContent?: ReactNode;
  /** 넘기면 누를 수 있는 줄(버튼)이 된다. 없으면 읽기만 하는 줄 */
  onClick?: () => void;
  /** 다른 화면으로 가는 줄이면 화살표를 붙인다(기본). 로그아웃처럼 바로 실행되는 줄은 false */
  hasChevron?: boolean;
}

/** 목록 한 줄: 아이콘 · 이름(+설명) · 오른쪽 값 · 화살표. 누르는 영역은 화면 좌우 끝까지, 높이 52px 이상. */
export function ListRow({ icon, label, description, endContent, onClick, hasChevron = true }: ListRowProps) {
  const content = (
    <>
      {icon ? (
        <span className="n-list-row__icon" aria-hidden="true">
          {icon}
        </span>
      ) : null}
      <span className="n-list-row__text">
        <span className="n-list-row__label">{label}</span>
        {description ? <span className="n-list-row__desc">{description}</span> : null}
      </span>
      {endContent ? <span className="n-list-row__end">{endContent}</span> : null}
      {onClick && hasChevron ? <ChevronRight className="n-list-row__chevron" size={20} /> : null}
    </>
  );
  return (
    <li>
      {onClick ? (
        <button type="button" className="n-list-row" onClick={onClick}>
          {content}
        </button>
      ) : (
        <div className="n-list-row n-list-row--static">{content}</div>
      )}
    </li>
  );
}
