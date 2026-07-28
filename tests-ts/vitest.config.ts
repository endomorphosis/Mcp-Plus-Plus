import { defineConfig } from 'vitest/config';

export default defineConfig({
  // Keep this standalone validator package from inheriting an unrelated
  // PostCSS configuration from whichever monorepo happens to contain it.
  css: {
    postcss: {
      plugins: [],
    },
  },
  test: {
    globals: true,
    environment: 'node',
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html'],
      exclude: ['node_modules/', 'dist/', '**/*.test.ts'],
    },
  },
});
