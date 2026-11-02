import { defineConfig } from 'vitepress';
import { assets, bridge, copyAssets, GUIDES, PACKAGES, REPO } from './bridge.mts';

// Served from https://darmawanrobotics.github.io/HotDog/ by .github/workflows/docs.yml.
const base = process.env.DOCS_BASE ?? '/HotDog/';

const guides = [
  { text: 'User Manual', link: '/manual/user-manual' },
  { text: 'Technician Guide', link: '/technician/technician-guide' },
  { text: 'Site Acceptance Test', link: '/acceptance/acceptance-test' },
];

// A link with a target is external to VitePress: no base added, so it is written here.
const pdfs = Object.values(GUIDES).map((pdf) => ({
  text: pdf.replace('HotDog-', '').replace('.pdf', '').replace(/-/g, ' '),
  link: `${base}${pdf}`,
  target: '_blank',
}));

export default defineConfig({
  title: 'HotDog',
  description:
    'Autonomous substation patrol on the Deep Robotics Lynx M20: teach and repeat on odometry, ' +
    'overheat analysis with the UniPod MT11, partial discharge with the Hertzinno HZ-FA-371.',
  base,
  cleanUrls: true,
  lastUpdated: true,
  // Not pages: the GitHub index of docs/, the PDF pipeline, the npm packages.
  srcExclude: ['README.md', 'pdf/**', 'node_modules/**'],
  ignoreDeadLinks: [/^https?:\/\/(localhost|127\.0\.0\.1)/],
  head: [
    ['link', { rel: 'icon', type: 'image/png', href: `${base}logo.png` }],
    ['meta', { name: 'theme-color', content: '#0f2742' }],
  ],
  markdown: {
    config: bridge,
    image: { lazyLoading: true },
  },
  vite: { plugins: [assets(base)] },
  buildEnd: (site) => copyAssets(site.outDir),
  themeConfig: {
    logo: '/logo.png',
    nav: [
      { text: 'Get started', link: '/overview', activeMatch: '^/(overview|commissioning|operations)' },
      { text: 'Guides', items: guides, activeMatch: '^/(manual|technician|acceptance)/' },
      { text: 'Packages', link: '/packages/hotdog', activeMatch: '^/packages/' },
      { text: 'PDF', items: pdfs },
    ],
    sidebar: [
      {
        text: 'Get started',
        items: [
          { text: 'Overview', link: '/overview' },
          { text: 'Commissioning', link: '/commissioning' },
          { text: 'Operations', link: '/operations' },
        ],
      },
      { text: 'Guides', items: guides },
      {
        text: 'Packages',
        collapsed: false,
        items: PACKAGES.map((name) => ({ text: name, link: `/packages/${name}` })),
      },
      {
        text: 'Project',
        items: [
          { text: 'Changelog', link: '/changelog' },
          { text: 'Contributing', link: '/contributing' },
        ],
      },
    ],
    outline: { level: [2, 3], label: 'On this page' },
    socialLinks: [{ icon: 'github', link: REPO }],
    editLink: {
      // Runs in the browser (serialized): no outer variables. Mirrored pages edit their source.
      pattern: ({ filePath, frontmatter }) =>
        'https://github.com/DarmawanRobotics/HotDog/edit/main/' +
        (frontmatter.source ?? `docs/${filePath}`),
      text: 'Edit this page on GitHub',
    },
    search: { provider: 'local' },
    footer: {
      message: 'Released under the Apache License 2.0. Built on the Dharma stack.',
      copyright: 'HotDog · DarmawanRobotics',
    },
  },
});
