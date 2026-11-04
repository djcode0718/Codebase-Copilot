import path from 'path';
import { defineConfig } from 'vitest/config';

export default defineConfig({
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './'),
    },
  },
  test: {
    include: ['lib/**/*.test.ts', 'hooks/**/*.test.ts'],
    environment: 'node',
    globals: true,
  },
});
