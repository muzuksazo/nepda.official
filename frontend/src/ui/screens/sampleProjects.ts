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
import type { BannerItem, ThumbnailTemplate } from '../components';
import type { CommunityVideo } from './CommunityScreen';
import type { HookType } from './flowData';
import type { CompletedProject, InProgressProject } from './HomeScreen';
import type { ProfileUser } from './ProfileScreen';
import type { GuideScene } from './ShootingGuideScreen';
import type { StoryboardScene } from './StoryboardScreen';

/** 스토리·프로토타입용 예시 데이터 */
export const SAMPLE_IN_PROGRESS: InProgressProject[] = [
  { id: 'p1', productName: '실리콘 접이식 도마', status: '촬영 가이드까지 받았어요', completedSteps: 5, nextStep: '찍은 영상 올리기' },
  { id: 'p2', productName: '무선 미니 가습기', status: '시나리오 글을 확인하고 있어요', completedSteps: 3, nextStep: '촬영 가이드 받기' },
  { id: 'p3', productName: '스테인리스 텀블러', status: '훅 유형을 골랐어요', completedSteps: 2, nextStep: '시나리오 글 보기' },
];

export const SAMPLE_COMPLETED: CompletedProject[] = [
  { id: 'c1', productName: '원목 데스크 정리함', status: '영상과 썸네일을 만들었어요' },
  { id: 'c2', productName: '접이식 빨래 건조대', status: '영상과 썸네일을 만들었어요' },
  { id: 'c3', productName: '휴대용 블렌더', status: '영상과 썸네일을 만들었어요' },
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
  { id: 'v06', productName: '휴대용 블렌더', creatorName: '갈아만든사장', hookType: 'C', thumbnailUrl: thumb06, caption: '갈아 버렸습니다', likeCount: 2051 },
  { id: 'v07', productName: '육각 젤펜', creatorName: '문구덕후', hookType: 'B', thumbnailUrl: thumb07, caption: '펜이 안 굴러가요', likeCount: 96 },
  { id: 'v08', productName: '충전식 무드등', creatorName: '방구석조명', hookType: 'A', thumbnailUrl: thumb08, caption: '자취방 조명 끝판왕', likeCount: 771 },
  { id: 'v09', productName: '실리콘 수세미', creatorName: '설거지장인', hookType: 'C', thumbnailUrl: thumb09, caption: '설거지 3분 컷', likeCount: 433 },
  { id: 'v10', productName: '접이식 노트', creatorName: '필기왕', hookType: 'A', thumbnailUrl: thumb10, caption: '노트가 접힌다고?', likeCount: 1502 },
  { id: 'v11', productName: '침대 트레이', creatorName: '눕방전문', hookType: 'B', thumbnailUrl: thumb11, caption: '침대 밖은 위험해', likeCount: 254 },
  { id: 'v12', productName: '실리콘 냄비 받침', creatorName: '주방템연구소', hookType: 'C', thumbnailUrl: thumb12, caption: '냄비 받침의 반란', likeCount: 688 },
];

/** 스토리·프로토타입에서 서버 대신 예시 목록을 훅 유형으로 거른다 (순서는 추천 순서라고 보고 그대로 둔다) */
export function filterCommunityByType(items: CommunityVideo[], hookType: HookType | null): CommunityVideo[] {
  return hookType === null ? items : items.filter((video) => video.hookType === hookType);
}
