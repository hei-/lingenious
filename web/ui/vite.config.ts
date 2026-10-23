/// <reference types="vitest" />
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  build: { outDir: 'dist', chunkSizeWarningLimit: 900 },
  server: { proxy: { '/api': { target: (globalThis as { process?: { env: Record<string, string | undefined> } }).process?.env.API_TARGET ?? 'http://localhost:8000', changeOrigin: true } } },
  test: { environment: 'node', include: ['src/**/*.test.ts'] },
});
