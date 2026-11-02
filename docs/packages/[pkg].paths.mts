import { PACKAGES } from '../.vitepress/bridge.mts';

// One page per package, its README mirrored from src/<name>/README.md.
export default {
  paths: () =>
    PACKAGES.map((pkg) => ({
      params: { pkg },
      content: `<!--@source: ../../src/${pkg}/README.md-->`,
    })),
};
