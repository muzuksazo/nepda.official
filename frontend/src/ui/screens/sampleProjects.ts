import clip01 from '../../assets/samples/community/clip-01.webm';
import thumb01 from '../../assets/samples/community/thumb-01.webp';
import thumb02 from '../../assets/samples/community/thumb-02.webp';
import thumb03 from '../../assets/samples/community/thumb-03.webp';
import thumb04 from '../../assets/samples/community/thumb-04.webp';
import thumb05 from '../../assets/samples/community/thumb-05.webp';
import thumb06 from '../../assets/samples/community/thumb-06.webp';
import thumb07 from '../../assets/samples/community/thumb-07.webp';
import thumb08 from '../../assets/samples/community/thumb-08.webp';
import thumb09 from '../../assets/samples/community/thumb-09.webp';
import thumb10 from '../../assets/samples/community/thumb-10.webp';
import thumb11 from '../../assets/samples/community/thumb-11.webp';
import thumb12 from '../../assets/samples/community/thumb-12.webp';
import templateBlocks from '../../assets/samples/thumbnail/template-blocks.webp';
import templateCard from '../../assets/samples/thumbnail/template-card.webp';
import templateSplit from '../../assets/samples/thumbnail/template-split.webp';
import templateStroke from '../../assets/samples/thumbnail/template-stroke.webp';
import event1 from '../../assets/events/event1.webp';
import event2 from '../../assets/events/event2.webp';
import event3 from '../../assets/events/event3.webp';
import type { BannerItem, CreditPackage, ThumbnailTemplate, VideoComment } from '../components';
import type { CommunityVideo } from './CommunityScreen';
import type { CreatorProfile } from './CreatorProfileScreen';
import type { CreditEntry } from './CreditHistoryScreen';
import type { HookType } from './flowData';
import type { CompletedProject, InProgressProject } from './HomeScreen';
import type { AppNotification } from './NotificationsScreen';
import type { ProfileUser } from './ProfileScreen';
import type { GuideScene } from './ShootingGuideScreen';
import type { StoryboardScene } from './StoryboardScreen';

/** 스토리·프로토타입용 예시 데이터 */
export const SAMPLE_IN_PROGRESS: InProgressProject[] = [
  { id: 'p1', productName: '실리콘 접이식 도마', status: '촬영 가이드까지 받았어요', completedSteps: 5, nextStep: '찍은 영상 올리기', thumbnailUrl: thumb01 },
  { id: 'p2', productName: '무선 미니 가습기', status: '시나리오 글을 확인하고 있어요', completedSteps: 3, nextStep: '촬영 가이드 받기' },
  { id: 'p3', productName: '스테인리스 텀블러', status: '훅 유형을 골랐어요', completedSteps: 2, nextStep: '시나리오 글 보기' },
];

export const SAMPLE_COMPLETED: CompletedProject[] = [
  { id: 'c1', productName: '원목 데스크 정리함', status: '영상과 썸네일을 만들었어요', thumbnailUrl: thumb04 },
  { id: 'c2', productName: '접이식 빨래 건조대', status: '영상과 썸네일을 만들었어요', thumbnailUrl: thumb05 },
  { id: 'c3', productName: '휴대용 블렌더', status: '영상과 썸네일을 만들었어요', thumbnailUrl: thumb06 },
];

/** 이벤트 배너 (이미지는 1050×500 @3x로 받아 imageUrl에 넣는다. 이미지가 없는 칸은 자리표시) */
export const SAMPLE_BANNERS: BannerItem[] = [
  { id: 'b1', imageUrl: event1, alt: '블랙 프라이데이 세일, 최대 70% 할인' },
  {
    id: 'b2',
    imageUrl: event3,
    alt: '냅다 광고 뽑기 이벤트. 오늘은 또 무슨 광고가 나올까? 랜덤 미션에 도전하고 크레딧을 받아보세요! 이벤트 참여하기',
  },
  {
    id: 'b3',
    imageUrl: event2,
    alt: '미친 광고 공모전. 세상에서 가장 어이없는 광고에 도전하세요! 지금 바로 참여하기',
  },
];

/** 예시: 실리콘 접이식 도마 · B 유형 훅의 그림 콘티 설명 */
export const SAMPLE_STORYBOARD: StoryboardScene[] = [
  { caption: '좁은 싱크대, 도마 놓을 데가 없다' },
  { caption: '접힌 도마를 냅다 펼친다' },
  { caption: '채소를 썰고 그대로 접어 냄비에 붓기' },
  { caption: '납작하게 접어 서랍에 쏙' },
];

/** 예시: 같은 제품의 촬영 가이드 */
export const SAMPLE_GUIDE_SCENES: GuideScene[] = [
  { instruction: '싱크대를 위에서 찍어요. 좁은 게 보이게.', duration: '3초' },
  { instruction: '접힌 도마를 손으로 확 펼쳐요.', duration: '2초' },
  { instruction: '썬 채소를 도마째 접어 냄비에 부어요.', duration: '5초' },
  { instruction: '납작해진 도마를 서랍에 넣고 닫아요.', duration: '3초' },
];

/**
 * 예시: 썸네일 템플릿. 실제 템플릿은 팀이 만들어서 넣는다 — 이 이미지들은 자리를 확인하려고 만든 예시다.
 */
export const SAMPLE_THUMBNAIL_TEMPLATES: ThumbnailTemplate[] = [
  { id: 'stroke', name: '큼직', description: '굵은 글자를 가운데에 크게', previewUrl: templateStroke },
  { id: 'blocks', name: '띠지', description: '줄마다 띠를 깔아 또렷하게', previewUrl: templateBlocks },
  { id: 'card', name: '카드', description: '어두운 카드에 담아 차분하게', previewUrl: templateCard },
  { id: 'split', name: '반반', description: '위는 훅, 아래는 제품 장면', previewUrl: templateSplit },
];

export const SAMPLE_THUMBNAIL_CAPTION = '이 도마, 미쳤다';

/** 예시: 로그인 화면 위쪽에 펼쳐 보여 줄 냅다 영상 썸네일 3장 (예시용으로 만든 이미지) */
export const SAMPLE_LOGIN_SHOWCASE = [thumb02, thumb01, thumb03];

/**
 * 예시: 크레딧 충전 묶음과 영상 한 편 단가. 가격·크레딧 단가는 정해지지 않았다(OQ-003) — 화면 확인용 값이다.
 */
export const SAMPLE_CREDITS_PER_VIDEO = 12;

export const SAMPLE_CREDIT_PACKAGES: CreditPackage[] = [
  { id: 'c30', credits: 30, price: 4900 },
  { id: 'c100', credits: 100, price: 12900, isPopular: true },
  { id: 'c300', credits: 300, price: 33000 },
];

/**
 * 예시: 크레딧 내역 (최신순). 내역 조회 API가 아직 없다.
 * 9/30 추석 선물 5 → 10/20 충전 30 → 추석 선물 기간 끝 → 영상 3편(그중 1편은 실패해서 돌려받고 다시 만듦) → 11/26 충전 100 = 104.
 * 충전 크레딧의 유효기간은 정해지지 않아 비워 두고, 이벤트 선물만 30일로 적었다(예시).
 */
export const SAMPLE_CREDIT_HISTORY: CreditEntry[] = [
  { id: 'l10', kind: 'charge', amount: 100, balance: 104, createdAt: '2026-11-26T09:30:00+09:00', price: 12900 },
  { id: 'l09', kind: 'use', amount: -12, balance: 4, createdAt: '2026-11-24T15:10:00+09:00', productName: '스테인리스 텀블러' },
  { id: 'l08', kind: 'refund', amount: 12, balance: 16, createdAt: '2026-11-23T11:20:00+09:00', productName: '스테인리스 텀블러' },
  { id: 'l07', kind: 'use', amount: -12, balance: 4, createdAt: '2026-11-23T11:05:00+09:00', productName: '스테인리스 텀블러' },
  { id: 'l06', kind: 'use', amount: -12, balance: 16, createdAt: '2026-11-19T14:40:00+09:00', productName: '무선 미니 가습기' },
  { id: 'l05', kind: 'bonus', amount: 10, balance: 28, createdAt: '2026-11-12T10:05:00+09:00', eventName: '블랙프라이데이 선물', expiresAt: '2026-12-12T23:59:00+09:00' },
  { id: 'l04', kind: 'use', amount: -12, balance: 18, createdAt: '2026-11-02T16:20:00+09:00', productName: '실리콘 접이식 도마' },
  { id: 'l03', kind: 'expire', amount: -5, balance: 30, createdAt: '2026-10-30T00:00:00+09:00', eventName: '추석 선물' },
  { id: 'l02', kind: 'charge', amount: 30, balance: 35, createdAt: '2026-10-20T21:14:00+09:00', price: 4900 },
  { id: 'l01', kind: 'bonus', amount: 5, balance: 5, createdAt: '2026-09-30T10:00:00+09:00', eventName: '추석 선물', expiresAt: '2026-10-29T23:59:00+09:00' },
];

/** 예시: 30일 안에 사라질 크레딧 (블랙프라이데이 선물) */
export const SAMPLE_CREDIT_EXPIRING = { credits: 10, date: '2026-12-12T23:59:00+09:00' };

/** 예시 알림의 기준 시각 (스토리에서 "3시간 전" 같은 표시를 고정한다) */
export const SAMPLE_NOW = new Date('2026-11-26T15:00:00+09:00');

/** 예시: 알림 (최신순). 알림 목록·읽음 API가 아직 없다 */
export const SAMPLE_NOTIFICATIONS: AppNotification[] = [
  { id: 'n1', kind: 'videoReady', title: '영상 나왔어요!', body: '실리콘 접이식 도마 · 훅 붙여서 완성했어요. 썸네일만 고르면 끝.', createdAt: '2026-11-26T14:52:00+09:00', isRead: false, targetId: 'p1' },
  { id: 'n2', kind: 'communityLike', title: '도마왕님 외 23명이 좋아해요', body: '"이 도마, 미쳤다" 영상', createdAt: '2026-11-26T12:10:00+09:00', isRead: false, targetId: 'v01' },
  { id: 'n3', kind: 'creditCharged', title: '100 크레딧 충전 완료', body: '이제 영상 8편쯤 만들 수 있어요.', createdAt: '2026-11-26T09:30:00+09:00', isRead: false },
  { id: 'n4', kind: 'expiring', title: '내일 지워져요', body: '무선 미니 가습기 영상, 보관 7일이 거의 끝났어요. 내려받아 두세요.', createdAt: '2026-11-25T18:00:00+09:00', isRead: true, targetId: 'c2' },
  { id: 'n5', kind: 'videoFailed', title: '영상을 못 만들었어요', body: '스테인리스 텀블러 · 쓴 크레딧 12는 돌려드렸어요. 다시 해 볼까요?', createdAt: '2026-11-23T11:20:00+09:00', isRead: true, targetId: 'p3' },
  { id: 'n6', kind: 'notice', title: '블랙프라이데이, 크레딧 최대 70% 할인', body: '이번 주 일요일까지만 냅다 싸게 채워요.', createdAt: '2026-11-12T10:00:00+09:00', isRead: true },
];

/** 예시: 영상별 댓글 (오래된 것부터). 댓글 API가 아직 없다 */
export const SAMPLE_COMMENTS: Record<string, VideoComment[]> = {
  v01: [
    { id: 'c1', authorName: '자취9년차', text: '도마 접히는 거 실화냐 ㅋㅋㅋ 바로 삼', createdAt: '2026-11-26T10:12:00+09:00' },
    { id: 'c2', authorName: '텀블러수집가', text: '훅 B 유형 이렇게 쓰는 거구나… 배워 갑니다', createdAt: '2026-11-26T11:40:00+09:00' },
    { id: 'c3', authorName: '책상정리단', text: '마지막에 서랍 닫는 거 개운하다', createdAt: '2026-11-26T13:05:00+09:00' },
  ],
  v02: [{ id: 'c4', authorName: '도마왕', text: '가습기 등장 타이밍 미쳤어요', createdAt: '2026-11-25T21:30:00+09:00' }],
  v03: [
    { id: 'c5', authorName: '설거지장인', text: '던지는 장면 몇 번 찍으셨어요?', createdAt: '2026-11-24T09:00:00+09:00' },
    { id: 'c6', authorName: '냅다사장', text: '저도 이거 보고 만들어 봤어요!', createdAt: '2026-11-26T08:20:00+09:00', isMine: true },
  ],
};

/** 예시: 내 정보 (GET /v1/auth/me) */
export const SAMPLE_USER: ProfileUser = { name: '냅다사장', email: 'napda.sajang@example.com' };

/**
 * 예시: 커뮤니티에 올라온 영상 (추천 순서라고 본다). 썸네일은 예시용으로 만든 이미지이고, 첫 영상에만 4초짜리 예시 영상이 있다.
 * 실제 사용자 영상이 아니다 — 공개·목록 API가 생기면 서버 데이터로 바꾼다.
 */
export const SAMPLE_COMMUNITY: CommunityVideo[] = [
  { id: 'v01', productName: '실리콘 접이식 도마', creatorName: '도마왕', hookType: 'B', thumbnailUrl: thumb01, videoUrl: clip01, caption: '이 도마, 미쳤다', likeCount: 1284 },
  { id: 'v02', productName: '무선 미니 가습기', creatorName: '자취9년차', hookType: 'A', thumbnailUrl: thumb02, caption: '가습기가 왜 거기서 나와', likeCount: 962 },
  { id: 'v03', productName: '스테인리스 텀블러', creatorName: '텀블러수집가', hookType: 'C', thumbnailUrl: thumb03, caption: '텀블러 던져 봤습니다', likeCount: 12300, isLiked: true },
  { id: 'v04', productName: '원목 데스크 정리함', creatorName: '책상정리단', hookType: 'B', thumbnailUrl: thumb04, caption: '책상이 3초 만에', likeCount: 547 },
  { id: 'v05', productName: '접이식 빨래 건조대', creatorName: '빨래요정', hookType: 'A', thumbnailUrl: thumb05, caption: '빨래, 접지 마세요', likeCount: 318 },
  { id: 'v06', productName: '휴대용 블렌더', creatorName: '도마왕', hookType: 'C', thumbnailUrl: thumb06, caption: '갈아 버렸습니다', likeCount: 2051 },
  { id: 'v07', productName: '육각 젤펜', creatorName: '문구덕후', hookType: 'B', thumbnailUrl: thumb07, caption: '펜이 안 굴러가요', likeCount: 96 },
  { id: 'v08', productName: '충전식 무드등', creatorName: '방구석조명', hookType: 'A', thumbnailUrl: thumb08, caption: '자취방 조명 끝판왕', likeCount: 771 },
  { id: 'v09', productName: '실리콘 수세미', creatorName: '도마왕', hookType: 'C', thumbnailUrl: thumb09, caption: '설거지 3분 컷', likeCount: 433 },
  { id: 'v10', productName: '접이식 노트', creatorName: '필기왕', hookType: 'A', thumbnailUrl: thumb10, caption: '노트가 접힌다고?', likeCount: 1502 },
  { id: 'v11', productName: '침대 트레이', creatorName: '눕방전문', hookType: 'B', thumbnailUrl: thumb11, caption: '침대 밖은 위험해', likeCount: 254 },
  { id: 'v12', productName: '실리콘 냄비 받침', creatorName: '도마왕', hookType: 'C', thumbnailUrl: thumb12, caption: '냄비 받침의 반란', likeCount: 688 },
];

/** 스토리·프로토타입에서 서버 대신 예시 목록을 훅 유형으로 거른다 (순서는 추천 순서라고 보고 그대로 둔다) */
export function filterCommunityByType(items: CommunityVideo[], hookType: HookType | null): CommunityVideo[] {
  return hookType === null ? items : items.filter((video) => video.hookType === hookType);
}

/**
 * 예시: 만든 사람 프로필 — 예시 커뮤니티 영상에서 그 닉네임의 영상을 모아 숫자를 센다.
 * (도마왕은 주방용품 영상 4편을 올린 사람으로 잡아 두었다.) 사람별 공개 프로필 API는 아직 없다.
 */
export function sampleCreator(name: string): { profile: CreatorProfile; videos: CommunityVideo[] } {
  const videos = SAMPLE_COMMUNITY.filter((video) => video.creatorName === name);
  const counts = new Map<HookType, number>();
  for (const video of videos) counts.set(video.hookType, (counts.get(video.hookType) ?? 0) + 1);
  const mainHookType = [...counts.entries()].sort((a, b) => b[1] - a[1])[0]?.[0];
  return {
    profile: {
      name,
      videoCount: videos.length,
      likeCount: videos.reduce((sum, video) => sum + video.likeCount, 0),
      mainHookType,
    },
    videos,
  };
}
