import '@fontsource/barlow/400.css';
import '@fontsource/barlow/500.css';
import '@fontsource/barlow/600.css';
import '@fontsource/barlow-semi-condensed/600.css';
import '@fontsource/barlow-semi-condensed/700.css';
import '@fontsource/jetbrains-mono/400.css';
import type { Theme } from 'vitepress';
import DefaultTheme from 'vitepress/theme';
import GuideMeta from './GuideMeta.vue';
import './custom.css';

export default {
  extends: DefaultTheme,
  enhanceApp({ app }) {
    app.component('GuideMeta', GuideMeta);
  },
} satisfies Theme;
