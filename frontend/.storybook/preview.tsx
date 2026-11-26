import type { Preview } from '@storybook/react-vite';
import { NapdaProvider, type ThemeMode } from '../src/ui/NapdaProvider';

const preview: Preview = {
  globalTypes: {
    napdaMode: {
      description: '라이트/다크',
      toolbar: {
        title: '모드',
        icon: 'mirror',
        items: [
          { value: 'light', title: '라이트', icon: 'sun' },
          { value: 'dark', title: '다크', icon: 'moon' },
        ],
        dynamicTitle: true,
      },
    },
  },
  initialGlobals: {
    napdaMode: 'light',
  },
  decorators: [
    (Story, context) => (
      <NapdaProvider mode={context.globals.napdaMode as ThemeMode}>
        <Story />
      </NapdaProvider>
    ),
  ],
  parameters: {
    controls: {
      matchers: {
        color: /(background|color)$/i,
        date: /Date$/i,
      },
    },
    options: {
      storySort: {
        order: ['NAPDA', ['화면', '흐름', '컴포넌트'], '*'],
      },
    },
    a11y: {
      // 'todo' - show a11y violations in the test UI only
      // 'error' - fail CI on a11y violations
      // 'off' - skip a11y checks entirely
      test: 'todo',
    },
  },
};

export default preview;
