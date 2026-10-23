/// <reference types="vitest" />
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

const env = (globalThis as { process?: { env: Record<string, string | undefined> } }).process?.env ?? {};

export default defineConfig({
  plugins: [react()],
  // the static demo is served from a sub-path (GitHub Pages); hash routing makes relative asset URLs safe
  base: env.VITE_DEMO === '1' ? './' : '/',
  build: { outDir: 'dist', chunkSizeWarningLimit: 900 },
  server: { proxy: { '/api': { target: env.API_TARGET ?? 'http://localhost:8000', changeOrigin: true } } },
  test: { environment: 'node', include: ['src/**/*.test.ts'] },
});
