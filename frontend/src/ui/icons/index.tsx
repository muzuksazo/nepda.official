import type { CSSProperties, SVGProps } from 'react';

/**
 * 냅다 아이콘 — Stratis UI Icons (Figma Community, Line Icons 24px, 2px 선)에서 가져온 SVG.
 * 원본: https://www.figma.com/design/8FMHemIvaENHFsHNLrvKrZ (페이지 "Line Icons")
 * 새 아이콘이 필요하면 같은 파일에서 찾아 SVG를 내보낸 뒤 아래 ICONS에 추가한다. 다른 아이콘 세트는 쓰지 않는다.
 *
 * 각 항목의 주석은 Stratis 아이콘 이름과 Figma 노드 ID다. Stratis에 없는 모양만 같은 규격으로 직접 그리고 '자체 제작'이라고 적는다.
 */

type Kind = 'stroke' | 'fill';

interface IconDef {
  d: string;
  kind: Kind;
  cap?: 'round';
  join?: 'round';
}

const ICONS = {
  // arrow-right · 101:1938
  ArrowRight: { d: 'M13.3333 19L20 12L13.3333 5M20 12L4 12', kind: 'stroke', cap: 'round', join: 'round' },
  // check-01 · 101:2136
  Check: { d: 'M16.8 8.3999L9.64043 15.5999L7.19995 13.1456', kind: 'stroke', cap: 'round', join: 'round' },
  // chevron-left · 101:2040
  ChevronLeft: { d: 'M15 17L10 12L15 7', kind: 'stroke', cap: 'round', join: 'round' },
  // chevron-right · 101:2044
  ChevronRight: { d: 'M10 7L15 12L10 17', kind: 'stroke', cap: 'round', join: 'round' },
  // media-strip-01 · 101:2969 (필름 — 내 영상)
  Film: {
    d: 'M3.0001 7.1999L21.0001 7.1999M3.0001 16.7999L21.0001 16.7999M12.0001 2.3999L12.0001 21.5999M16.8001 2.3999L16.8001 7.1999M16.8001 16.7999L16.8001 21.5999M7.2001 2.3999L7.2001 7.1999M7.2001 16.7999L7.2001 21.5999M5.99999 2.3999L18.0001 2.3999C19.9883 2.39991 21.6001 4.01168 21.6001 5.99991L21.6001 17.9999C21.6001 19.9881 19.9883 21.5999 18.0001 21.5999L5.99999 21.5999C4.01176 21.5999 2.39999 19.9881 2.39999 17.9999L2.39999 5.9999C2.39999 4.01168 4.01176 2.3999 5.99999 2.3999Z',
    kind: 'stroke',
    cap: 'round',
    join: 'round',
  },
  // slate · 냅다 자체 제작 (Stratis에 슬레이트가 없어 같은 규격 — 24px 그리드, 2px 선, 둥근 끝 — 으로 그림)
  Slate: {
    d: 'M3 11H21V19C21 20.1046 20.1046 21 19 21H5C3.89543 21 3 20.1046 3 19V11ZM3 11L2.4 8.6C2.2 7.6 2.8 6.6 3.8 6.4L17.6 3.1C18.6 2.9 19.6 3.5 19.8 4.5L20.4 6.8L3 11ZM7.6 5.5L9.6 9.6M13.2 4.2L15.2 8.3',
    kind: 'stroke',
    cap: 'round',
    join: 'round',
  },
  // clock-01 · 101:4922 (외곽선을 면으로 그린 아이콘)
  Clock: {
    d: 'M15.5588 15.1987C16.0827 15.3733 16.649 15.0902 16.8237 14.5662C16.9983 14.0423 16.7152 13.476 16.1912 13.3013L15.875 14.25L15.5588 15.1987ZM12.5 13.125H11.5C11.5 13.5554 11.7754 13.9376 12.1838 14.0737L12.5 13.125ZM13.5 8.42087C13.5 7.86858 13.0523 7.42087 12.5 7.42087C11.9477 7.42087 11.5 7.86858 11.5 8.42087H12.5H13.5ZM15.875 14.25L16.1912 13.3013L12.8162 12.1763L12.5 13.125L12.1838 14.0737L15.5588 15.1987L15.875 14.25ZM12.5 13.125H13.5V8.42087H12.5H11.5V13.125H12.5ZM21.5 12H20.5C20.5 16.4183 16.9183 20 12.5 20V21V22C18.0228 22 22.5 17.5228 22.5 12H21.5ZM12.5 21V20C8.08172 20 4.5 16.4183 4.5 12H3.5H2.5C2.5 17.5228 6.97715 22 12.5 22V21ZM3.5 12H4.5C4.5 7.58172 8.08172 4 12.5 4V3V2C6.97715 2 2.5 6.47715 2.5 12H3.5ZM12.5 3V4C16.9183 4 20.5 7.58172 20.5 12H21.5H22.5C22.5 6.47715 18.0228 2 12.5 2V3Z',
    kind: 'fill',
  },
  // download-02 · 101:2192
  Download: {
    d: 'M4 15.2044L4 18.8925C4 19.4514 4.21071 19.9875 4.58579 20.3827C4.96086 20.778 5.46957 21 6 21H18C18.5304 21 19.0391 20.778 19.4142 20.3827C19.7893 19.9875 20 19.4514 20 18.8925V15.2044M12.0011 3V14.9425M7.42969 10.3793L12.0011 14.9425L16.5725 10.3793',
    kind: 'stroke',
    cap: 'round',
    join: 'round',
  },
  // home-04 · 101:2314
  Home: {
    d: 'M9 21V14.1528C9 13.5226 9.53726 13.0116 10.2 13.0116H13.8C14.4627 13.0116 15 13.5226 15 14.1528V21M11.3046 3.21117L3.50457 8.48603C3.18802 8.7001 3 9.04665 3 9.41605V19.2882C3 20.2336 3.80589 21 4.8 21H19.2C20.1941 21 21 20.2336 21 19.2882V9.41605C21 9.04665 20.812 8.70011 20.4954 8.48603L12.6954 3.21117C12.2791 2.92961 11.7209 2.92961 11.3046 3.21117Z',
    kind: 'stroke',
    cap: 'round',
  },
  // image-01 · 101:3381
  Image: {
    d: 'M8.1599 15.6L11.9999 12L14.5599 13.8L18.1866 10.2L21.3866 13.2M2.3999 8.99995V19.8H15.1999M10.0799 7.79995V7.70972M21.5999 15.2V5.19995C21.5999 4.64767 21.1522 4.19995 20.5999 4.19995H7.2399C6.68762 4.19995 6.2399 4.64767 6.2399 5.19995V15.2C6.2399 15.7522 6.68762 16.2 7.2399 16.2H20.5999C21.1522 16.2 21.5999 15.7522 21.5999 15.2Z',
    kind: 'stroke',
    cap: 'round',
    join: 'round',
  },
  // information-circle-contained · 101:2326
  Info: {
    d: 'M12 12L12 16.5M12 8.66455V8.625M3 12C3 7.02944 7.02944 3 12 3C16.9706 3 21 7.02944 21 12C21 16.9706 16.9706 21 12 21C7.02944 21 3 16.9706 3 12Z',
    kind: 'stroke',
    cap: 'round',
    join: 'round',
  },
  // package-01 · 101:4587
  Package: {
    d: 'M11.9999 21.6L20.3137 16.8V7.19999L11.9999 2.39999L3.68604 7.19999V16.8L11.9999 21.6ZM11.9999 21.6V12.6M11.9999 12.6L4.19988 7.79999M11.9999 12.6L19.7999 7.79999',
    kind: 'stroke',
    cap: 'round',
    join: 'round',
  },
  // pause-03 · 101:3014
  Pause: { d: 'M7 20V4M17 20V4', kind: 'stroke', cap: 'round', join: 'round' },
  // play-03 · 101:3026
  Play: {
    d: 'M17.9733 13.5177C19.3447 12.6568 19.3397 11.6988 17.9733 10.9373L7.24887 3.32244C6.13721 2.6434 4.97059 3.04355 5.00057 4.45982L5.04553 19.418C5.14046 20.9556 6.04478 21.3751 7.37627 20.6645L17.9733 13.5177Z',
    kind: 'stroke',
  },
  // plus-02 · 101:2435
  Plus: { d: 'M12 6L12 18M18 12L6 12', kind: 'stroke', cap: 'round' },
  // upload-03 · 101:2560
  Upload: {
    d: 'M4 15.2044V18.8925C4 19.4514 4.21071 19.9875 4.58579 20.3827C4.96086 20.778 5.46957 21 6 21H18C18.5304 21 19.0391 20.778 19.4142 20.3827C19.7893 19.9875 20 19.4514 20 18.8925V15.2044M12.0007 14.9425L12.0007 3M16.5722 7.56318L12.0007 3L7.42931 7.56318',
    kind: 'stroke',
    cap: 'round',
    join: 'round',
  },
  // user-profile-01 · 101:4116
  User: {
    d: 'M20.3995 21.6L20.3998 18.0003C20.4 16.012 18.7881 14.4 16.7998 14.4H7.2005C5.21244 14.4 3.60073 16.0116 3.6005 17.9996L3.6001 21.6M15.6001 6.00002C15.6001 7.98825 13.9883 9.60002 12.0001 9.60002C10.0119 9.60002 8.4001 7.98825 8.4001 6.00002C8.4001 4.0118 10.0119 2.40002 12.0001 2.40002C13.9883 2.40002 15.6001 4.0118 15.6001 6.00002Z',
    kind: 'stroke',
    cap: 'round',
    join: 'round',
  },
  // users-profiles-01 · 101:4170
  Users: {
    d: 'M16.0253 20.5707L16.0256 17.3569C16.0258 15.5818 14.5867 14.1426 12.8115 14.1426H5.61432C3.83939 14.1426 2.40046 15.5814 2.40026 17.3563L2.3999 20.5707M21.5996 20.5709L21.5999 17.3571C21.6001 15.5819 20.161 14.1428 18.3858 14.1428M15.4062 4.06048C16.1955 4.64612 16.7071 5.58498 16.7071 6.64331C16.7071 7.70164 16.1955 8.64049 15.4062 9.22613M12.4937 6.64313C12.4937 8.41821 11.0547 9.85719 9.27964 9.85719C7.50457 9.85719 6.06559 8.41821 6.06559 6.64313C6.06559 4.86806 7.50457 3.42908 9.27964 3.42908C11.0547 3.42908 12.4937 4.86806 12.4937 6.64313Z',
    kind: 'stroke',
    cap: 'round',
    join: 'round',
  },
  // x-02 · 101:2576
  X: { d: 'M18 6L6 18M18 18L6 6', kind: 'stroke', cap: 'round' },
  // lightning-filled · 101:2342 (크레딧)
  Lightning: {
    d: 'M13.3 10.8002H18.2397C18.6442 10.8002 18.8813 11.2555 18.6493 11.5869L11.7097 21.5007C11.4293 21.9012 10.8 21.7029 10.8 21.214V14.5002C10.8 14.445 10.7553 14.4002 10.7 14.4002H5.71089C5.31634 14.4002 5.07723 13.9646 5.28905 13.6318L12.2782 2.64879C12.5468 2.22677 13.2 2.417 13.2 2.91722V10.7002C13.2 10.7554 13.2448 10.8002 13.3 10.8002Z',
    kind: 'stroke',
    join: 'round',
  },
} satisfies Record<string, IconDef>;

export type IconName = keyof typeof ICONS;

export interface IconProps extends Omit<SVGProps<SVGSVGElement>, 'fill' | 'stroke'> {
  /** 한 변 크기(px). 기본 24 */
  size?: number;
  /** 선 굵기. Stratis 기본은 2 */
  strokeWidth?: number;
  /** 'currentColor'를 넘기면 안을 채운다(재생·일시정지·번개처럼 꽉 찬 모양이 필요할 때) */
  fill?: 'currentColor' | 'none';
  style?: CSSProperties;
}

function makeIcon(name: IconName) {
  const def: IconDef = ICONS[name];
  function Icon({ size = 24, strokeWidth = 2, fill = 'none', ...rest }: IconProps) {
    const isFillKind = def.kind === 'fill';
    return (
      <svg
        width={size}
        height={size}
        viewBox="0 0 24 24"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        aria-hidden={rest['aria-label'] ? undefined : true}
        focusable="false"
        {...rest}
      >
        {isFillKind ? (
          <path d={def.d} fill="currentColor" />
        ) : (
          <path
            d={def.d}
            fill={fill}
            stroke="currentColor"
            strokeWidth={strokeWidth}
            strokeLinecap={def.cap}
            strokeLinejoin={def.join}
          />
        )}
      </svg>
    );
  }
  Icon.displayName = `Icon(${name})`;
  return Icon;
}

export const ArrowRight = makeIcon('ArrowRight');
export const Check = makeIcon('Check');
export const ChevronLeft = makeIcon('ChevronLeft');
export const ChevronRight = makeIcon('ChevronRight');
export const Film = makeIcon('Film');
export const Slate = makeIcon('Slate');
export const Clock = makeIcon('Clock');
export const Download = makeIcon('Download');
export const Home = makeIcon('Home');
export const ImageIcon = makeIcon('Image');
export const Info = makeIcon('Info');
export const Package = makeIcon('Package');
export const Pause = makeIcon('Pause');
export const Play = makeIcon('Play');
export const Plus = makeIcon('Plus');
export const Upload = makeIcon('Upload');
export const User = makeIcon('User');
export const Users = makeIcon('Users');
export const X = makeIcon('X');
export const Lightning = makeIcon('Lightning');
