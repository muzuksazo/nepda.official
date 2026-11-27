import type { CSSProperties, SVGProps } from 'react';

/**
 * 냅다 아이콘 — Stratis UI Icons (Figma Community, Line Icons 24px, 2px 선)에서 가져온 SVG.
 * 원본: https://www.figma.com/design/8FMHemIvaENHFsHNLrvKrZ (페이지 "Line Icons")
 * 새 아이콘이 필요하면 같은 파일에서 찾아 SVG를 내보낸 뒤 아래 ICONS에 추가한다. 다른 아이콘 세트는 쓰지 않는다.
 *
 * 예외: 좋아요 하트(Heart)만 Free Icon Pack 1800+의 `Favorite`을 쓴다.
 *
 * 각 항목의 주석은 Stratis 아이콘 이름과 Figma 노드 ID다. 직접 그린 아이콘은 없다 — 딱 맞는 모양이 없으면 라이브러리에서 가장 가까운 것을 고른다.
 *
 * 픽셀 맞춤: 원본은 선이 픽셀 칸 사이(예: y=17.18)에 걸쳐 일반 모니터(1배율)에서 자글자글해 보인다.
 * 그래서 가로·세로 직선과 곡선의 평평한 꼭대기·옆을 정수 좌표로 옮기고, 곡선 손잡이도 같은 만큼 옮겨 모양을 지켰다.
 * 새 아이콘도 Figma에서 내보낸 경로를 `python3 scripts/snap_icons.py "<d>"`로 맞춰서 넣는다 (24px · 선 2px 기준).
 */

type Kind = 'stroke' | 'fill';

interface IconDef {
  d: string;
  /** 채운 상태에서도 보여야 하는 안쪽 선. 채우면 배경색으로 그어 면을 가른다 */
  detail?: string;
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
    d: 'M3.0001 7L21.0001 7M3.0001 17L21.0001 17M12 2.3999L12 21.5999M17 2.3999L17 7.1999M17 16.7999L17 21.5999M7 2.3999L7 7.1999M7 16.7999L7 21.5999M6 2L18.0001 2C19.9883 2 22 4.0117 22 5.9999L22 17.9999C22 19.9881 19.9883 22 18.0001 22L6 22C4.0118 22 2 19.9881 2 17.9999L2 5.9999C2 4.0117 4.0118 2 6 2Z',
    kind: 'stroke',
    cap: 'round',
    join: 'round',
  },
  // folder · 101:3587 (내 영상 — 기본 폴더)
  Folder: {
    d: 'M2 8.4167L2 17.941C2 19.0456 3.2963 20 4.4008 20L19.5996 20C20.7041 20 21.9999 19.0457 22 17.9412L22 8.0125C22 7.4602 21.1522 7 20.5999 7L12.0836 7L9.3186 4L3.4003 4C2.8479 4 1.9998 4.5061 2 5.0585C2.0003 6.0093 2 7.4362 2 8.4167Z',
    kind: 'stroke',
    cap: 'round',
    join: 'round',
  },
  // clock-01 · 101:4922 (외곽선을 면으로 그린 아이콘)
  Clock: {
    d: 'M16 15.1987C16.5239 15.3733 16.649 15.0902 16.8237 14.5662C16.9983 14.0423 16.524 13.476 16 13.3013L16 14.25L16 15.1987ZM12 13L12 13C12 13.4304 11.5916 13.9376 12 14.0737L12 13ZM14 8C14 7.4477 13.0523 7 12.5 7C11.9477 7 12 7.4477 12 8L12.5 8L14 8ZM16 14.25L16 13.3013L13 12.1763L12 13L12 14.0737L16 15.1987L16 14.25ZM12 13L14 13L14 8L12.5 8L12 8L12 13L12 13ZM21.5 12L20 12C20 16.4183 16.4183 20 12 20L12 21L12 22C17.5228 22 22 17.5228 22 12L21.5 12ZM12 21L12 20C7.5817 20 4 16.4183 4 12L3.5 12L2 12C2 17.5228 6.4771 22 12 22L12 21ZM3.5 12L4 12C4 7.5817 7.5817 4 12 4L12 3L12 2C6.4771 2 2 6.4771 2 12L3.5 12ZM12 3L12 4C16.4183 4 20 7.5817 20 12L21.5 12L22 12C22 6.4771 17.5228 2 12 2L12 3Z',
    kind: 'fill',
  },
  // download-02 · 101:2192
  Download: {
    d: 'M4 15.2044L4 18.8925C4 19.4514 4.2107 19.9875 4.5858 20.3827C4.9609 20.778 5.4696 21 6 21L18 21C18.5304 21 19.0391 20.778 19.4142 20.3827C19.7893 19.9875 20 19.4514 20 18.8925L20 15.2044M12 3L12 14.9425M7.4297 10.3793L12 14.9425L16.5725 10.3793',
    kind: 'stroke',
    cap: 'round',
    join: 'round',
  },
  // home-03 · 101:2309
  Home: {
    d: 'M11.3046 3.21117L3.50457 8.48603C3.18802 8.7001 3 9.04665 3 9.41605V19.2882C3 20.2336 3.80589 21 4.8 21H19.2C20.1941 21 21 20.2336 21 19.2882V9.41605C21 9.04665 20.812 8.70011 20.4954 8.48603L12.6954 3.21117C12.2791 2.92961 11.7209 2.92961 11.3046 3.21117Z',
    kind: 'stroke',
  },
  // image-01 · 101:3381
  Image: {
    d: 'M8.1599 15.6L11.9999 12L14.5599 13.8L18.1866 10.2L21.3866 13.2M2 9L2 20L15.1999 20M10.0799 7.7999L10.0799 7.7097M22 15.2L22 5.2C22 4.6477 21.1522 4 20.5999 4L7.2399 4C6.6876 4 6 4.6477 6 5.2L6 15.2C6 15.7522 6.6876 16 7.2399 16L20.5999 16C21.1522 16 22 15.7522 22 15.2Z',
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
    d: 'M12 21.6L20 16.8L20 7.2L11.9999 2.4L4 7.2L4 16.8L12 21.6ZM12 21.6L12 12.6M12 12.6L4.1999 7.8M12 12.6L19.7999 7.8',
    kind: 'stroke',
    cap: 'round',
    join: 'round',
  },
  // pause-03 · 101:3014
  Pause: { d: 'M7 20V4M17 20V4', kind: 'stroke', cap: 'round', join: 'round' },
  // play-03 · 101:3026
  Play: {
    d: 'M17.9733 13.5177C19.3447 12.6568 19.3397 11.6988 17.9733 10.9373L7.2489 3.3224C6.1372 2.6434 4.97 3.0436 5 4.4598L5 19.418C5.0949 20.9556 6.0448 21.3751 7.3763 20.6645L17.9733 13.5177Z',
    kind: 'stroke',
  },
  // plus-02 · 101:2435
  Plus: { d: 'M12 6L12 18M18 12L6 12', kind: 'stroke', cap: 'round' },
  // upload-03 · 101:2560
  Upload: {
    d: 'M4 15.2044L4 18.8925C4 19.4514 4.2107 19.9875 4.5858 20.3827C4.9609 20.778 5.4696 21 6 21L18 21C18.5304 21 19.0391 20.778 19.4142 20.3827C19.7893 19.9875 20 19.4514 20 18.8925L20 15.2044M12 14.9425L12 3M16.5722 7.5632L12 3L7.4293 7.5632',
    kind: 'stroke',
    cap: 'round',
    join: 'round',
  },
  // user-profile-01 · 101:4116
  User: {
    d: 'M20 21.6L20 18.0003C20.0002 16.012 18.7881 14 16.7998 14L7.2005 14C5.2124 14 4.0002 16.0116 4 17.9996L4 21.6M16 6C16 7.9882 13.9883 10 12.0001 10C10.0119 10 8 7.9882 8 6C8 4.0118 10.0119 2 12.0001 2C13.9883 2 16 4.0118 16 6Z',
    kind: 'stroke',
    cap: 'round',
    join: 'round',
  },
  // users-profiles-01 · 101:4170
  Users: {
    d: 'M16 20.5707L16 17.3569C16.0002 15.5818 14.5867 14 12.8115 14L5.6143 14C3.8394 14 2.0002 15.5814 2 17.3563L2 20.5707M22 20.5709L22 17.3571C22.0002 15.5819 20.161 14 18.3858 14M15.4062 4.0605C16.1955 4.6461 17 5.585 17 6.6433C17 7.7016 16.1955 8.6405 15.4062 9.2261M12 6.6431C12 8.4182 11.0547 10 9.2796 10C7.5046 10 6 8.4182 6 6.6431C6 4.8681 7.5046 3 9.2796 3C11.0547 3 12 4.8681 12 6.6431Z',
    kind: 'stroke',
    cap: 'round',
    join: 'round',
  },
  // x-02 · 101:2576
  X: { d: 'M18 6L6 18M18 18L6 6', kind: 'stroke', cap: 'round' },
  // lightning-filled · 101:2342 (크레딧)
  Lightning: {
    d: 'M13.3 11L18.2397 11C18.6442 11 18.8813 11.2555 18.6493 11.5869L11.7097 21.5007C11.4293 21.9012 11 21.7029 11 21.214L11 14.5002C11 14.445 10.7553 14 10.7 14L5.7109 14C5.3163 14 5.0772 13.9646 5.289 13.6318L12.2782 2.6488C12.5468 2.2268 13 2.417 13 2.9172L13 10.7002C13 10.7554 13.2448 11 13.3 11Z',
    kind: 'stroke',
    join: 'round',
  },
  // bell-02 · 101:3169 (알림)
  Bell: {
    d: 'M9.3333 20.0909C10.041 20.6562 10.9755 21 12 21C13.0245 21 13.959 20.6562 14.6667 20.0909M4.5076 17C4.086 17 3.8505 16.5194 4.1056 16.1514C4.6974 15.2975 5 14.0451 5 12.537L5 10.3517C5 6.2915 8.2958 3 12 3C15.7588 3 19 6.3399 19 10.4599L19 12.537C19 14.0555 19.3329 15.3147 19.9006 16.169C20.1458 16.5379 19.9097 17 19.4933 17L4.5076 17Z',
    kind: 'stroke',
    cap: 'round',
    join: 'round',
  },
  // help-circle-contained · 101:2293 (도움말·문의)
  Help: {
    d: 'M11.999 16.5L11.999 16.5396M10 9.23C10 7.9639 10.7574 7 12 7C13.2426 7 14 7.9639 14 9.23C14 10.4961 13.2426 12 12 12C12 12 12 12.2067 12 13.0508M21 12C21 16.9706 16.9706 21 12 21C7.0294 21 3 16.9706 3 12C3 7.0294 7.0294 3 12 3C16.9706 3 21 7.0294 21 12Z',
    kind: 'stroke',
    cap: 'round',
    join: 'round',
  },
  // file-02 · 101:3460 (약관 문서)
  FileText: {
    d: 'M8.4003 7L15.6003 7M8.4003 11L15.6003 11M8.4003 14L12.0003 14M6.6 2L17.4003 2C18.7258 2 20 3.4745 20 4.7999L20 19.2C20 20.5254 18.7254 22 17.4 22L6.5999 22C5.2745 22 4 20.5253 4 19.1998L4 4.7999C4 3.4744 5.2746 2 6.6 2Z',
    kind: 'stroke',
    cap: 'round',
    join: 'round',
  },
  // shield-check · 101:3336 (개인정보)
  ShieldCheck: {
    d: 'M9.6 11.1876L11.4 12.9876L15.0001 9.3876M5 5.7876L10.3901 2.9926C11.4036 2.4859 12.5965 2.4859 13.61 2.9926L19 5.7876C19 5.7876 19 11.0436 19 13.8156C19 16.5876 16.6377 18.4588 12 21.3876C7.3624 18.4588 5 15.9876 5 13.8156L5 5.7876Z',
    kind: 'stroke',
    cap: 'round',
    join: 'round',
  },
  // stars · 101:3726 (AI 라벨)
  Stars: {
    d: 'M14.8234 2.3999L16.6537 7.34611L21.5999 9.17637L16.6537 11.0066L14.8234 15.9528L12.9932 11.0066L8.04696 9.17637L12.9932 7.34611L14.8234 2.3999ZM6.35284 13.694L7.95167 16.0481L10.3058 17.647L7.95167 19.2458L6.35284 21.5999L4.75402 19.2458L2.3999 17.647L4.75402 16.0481L6.35284 13.694Z',
    kind: 'stroke',
    join: 'round',
  },
  // logout-02 · 101:2378
  Logout: {
    d: 'M8.7801 4L5.0742 4C4.5126 4 3.9739 3.8213 3.5768 4.2152C3.1797 4.609 3 5.1431 3 5.7001L3 18.3001C3 18.8571 3.1797 19.3912 3.5768 19.785C3.9739 20.1788 4.5126 20 5.0742 20L8.7801 20M9.0433 12L21.0433 12M16.4581 16.8001L21.0433 12L16.4581 7.2001',
    kind: 'stroke',
    cap: 'round',
    join: 'round',
  },
  // Favorite · 2165:6349 — Free Icon Pack 1800+ (Figma vCWtA42hSgsber0woDJCiC). 하트만 이 팩 모양을 쓴다 (좋아요)
  Heart: {
    d: 'M20.0978 6.92607L19.7885 6.52734C17.8203 3.99058 13.8696 4.41601 12.4867 7.31365C12.2913 7.72296 11.7087 7.72296 11.5133 7.31365C10.1304 4.41601 6.17972 3.99058 4.21154 6.52735L3.90219 6.92607C2.25695 9.0466 2.4945 12.0706 4.45067 13.9082L11.4033 20.4395C11.6428 20.6644 11.7625 20.7769 11.9037 20.8046C11.9673 20.8171 12.0327 20.8171 12.0963 20.8046C12.2375 20.7769 12.3572 20.6644 12.5967 20.4395L19.5493 13.9082C21.5055 12.0706 21.743 9.0466 20.0978 6.92607Z',
    kind: 'stroke',
  },
  // send-01 · 101:4832 (공유 — 종이비행기)
  Share: {
    d: 'M21.0703 2.92961L10.4063 13.5936M3.271 8.23529L19.8769 2.47406C20.8995 2.11927 21.8807 3.1004 21.5259 4.12303L15.7646 20.7289C15.37 21.8665 13.7725 21.8977 13.3337 20.7764L10.6968 14.0377C10.5651 13.7011 10.2988 13.4348 9.96226 13.3031L3.22354 10.6662C2.10219 10.2275 2.13338 8.62997 3.271 8.23529Z',
    kind: 'stroke',
    cap: 'round',
  },
  // message-circle · 101:4729 (댓글)
  Comment: {
    d: 'M21 12C21 13.2938 20.7253 14.5238 20.2338 15.6356L21 20.9991L16.4039 19.85C15.1019 20.5823 13.5993 21 11.9991 21C7.0291 21 3 16.9706 3 12C3 7.0294 7.0291 3 11.9991 3C16.9692 3 21 7.0294 21 12Z',
    kind: 'stroke',
    cap: 'round',
    join: 'round',
  },
  // alert-triangle · 101:3160 (신고 — Stratis에 깃발이 없어 경고 삼각형을 쓴다)
  Alert: {
    d: 'M12 12.9V8.41447M12 16.2248V16.2642M17.6699 20H6.33007C4.7811 20 3.47392 18.9763 3.06265 17.5757C2.88709 16.9778 3.10281 16.3551 3.43276 15.8249L9.10269 5.60102C10.4311 3.46632 13.5689 3.46633 14.8973 5.60103L20.5672 15.8249C20.8972 16.3551 21.1129 16.9778 20.9373 17.5757C20.5261 18.9763 19.2189 20 17.6699 20Z',
    kind: 'stroke',
    cap: 'round',
    join: 'round',
  },
  // volume-05 · 101:3108 (소리 켜짐)
  SoundOn: {
    d: 'M19.6824 8.0794C21.2661 10.5939 21.4898 13.9404 19.9833 16.9018M16.3459 9.7241C17.6827 11.2866 17.8715 13.3662 16.5999 15.2065M12 6L7.5877 9L3 9L3 15L7.5877 15L12 18L12 6Z',
    kind: 'stroke',
    cap: 'round',
    join: 'round',
  },
  // volume-02 · 101:3095 (소리 꺼짐)
  SoundOff: {
    d: 'M21 9.7243L18.75 11.9173M18.75 11.9173L16.5 14.1102M18.75 11.9173L21 14.1102M18.75 11.9173L16.5 9.7243M12 6L7.6407 9L3 9L3 15L7.6407 15L12 18L12 6Z',
    kind: 'stroke',
    cap: 'round',
    join: 'round',
  },
} satisfies Record<string, IconDef>;

export type IconName = keyof typeof ICONS;

export interface IconProps extends Omit<SVGProps<SVGSVGElement>, 'fill' | 'stroke'> {
  /** 한 변 크기(px). 기본 24 */
  size?: number;
  /** 선 굵기. Stratis 기본은 2 */
  strokeWidth?: number;
  /** 안 채움 색. 'currentColor'(재생·번개처럼 꽉 찬 모양)나 색 토큰(예: 하단 내비게이션 현재 탭의 라임)을 넘긴다 */
  fill?: string;
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
          <>
            <path
              d={def.d}
              fill={fill}
              stroke="currentColor"
              strokeWidth={strokeWidth}
              strokeLinecap={def.cap}
              strokeLinejoin={def.join}
            />
            {def.detail ? (
              <path
                d={def.detail}
                fill="none"
                stroke={fill === 'none' ? 'currentColor' : 'var(--bg)'}
                strokeWidth={strokeWidth}
                strokeLinecap={def.cap}
                strokeLinejoin={def.join}
              />
            ) : null}
          </>
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
export const Folder = makeIcon('Folder');
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
export const Bell = makeIcon('Bell');
export const Help = makeIcon('Help');
export const FileText = makeIcon('FileText');
export const ShieldCheck = makeIcon('ShieldCheck');
export const Stars = makeIcon('Stars');
export const Logout = makeIcon('Logout');
export const Heart = makeIcon('Heart');
export const Share = makeIcon('Share');
export const Comment = makeIcon('Comment');
export const Alert = makeIcon('Alert');
export const SoundOn = makeIcon('SoundOn');
export const SoundOff = makeIcon('SoundOff');
