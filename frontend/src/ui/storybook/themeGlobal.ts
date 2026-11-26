import { addons } from 'storybook/preview-api';
import type { ThemeSetting } from '../NapdaProvider';

/**
 * Storybook 채널의 전역 값 변경 이벤트 이름(= storybook/internal/core-events 의 UPDATE_GLOBALS).
 * 상수를 가져오면 테스트 실행 중에 새 의존성 묶음이 생겨 첫 실행이 실패할 수 있어 이름을 직접 쓴다.
 */
const UPDATE_GLOBALS = 'updateGlobals';

/**
 * 화면 안의 "화면 모드" 설정을 Storybook 툴바의 '모드'와 같은 값으로 묶는다.
 * 스토리에서 onThemeModeChange에 넘기면, 화면에서 고른 모드가 바로 적용되고 툴바도 함께 바뀐다.
 * 실제 앱에서는 이 자리에 설정 저장 + NapdaProvider의 mode 갱신이 들어간다.
 */
export function setStorybookTheme(mode: ThemeSetting) {
  addons.getChannel().emit(UPDATE_GLOBALS, { globals: { napdaMode: mode } });
}
