import event1 from '../../assets/events/event1.webp';
import event2 from '../../assets/events/event2.webp';
import event3 from '../../assets/events/event3.webp';
import type { BannerItem } from '../components';
import type { CompletedProject, InProgressProject } from './HomeScreen';

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
