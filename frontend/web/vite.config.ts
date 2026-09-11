import react from '@vitejs/plugin-react';
import path from 'path';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [react()],
  resolve: {
    dedupe: ['react', 'react-dom', 'antd', 'ag-grid-community', 'ag-grid-react', '@rjsf/utils'],
    alias: {
      '@': path.resolve(__dirname, './src'),
      '@app': path.resolve(__dirname, './src/app'),
      '@modules': path.resolve(__dirname, './src/modules'),
      '@shared': path.resolve(__dirname, './src/shared'),
      '@mocks': path.resolve(__dirname, './src/mocks'),
      '@common': path.resolve(__dirname, '../../common'),
      'plotly.js/dist/plotly': 'plotly.js-dist',
    },
  },
  optimizeDeps: {
    include: ['plotly.js-dist'],
  },
  server: {
    // Polling avoids exhausting the host's inotify watcher quota in large
    // workspaces (for example when VS Code and Vite watch the same tree).
    watch: {
      usePolling: true,
      interval: 1000,
    },
    fs: {
      allow: [path.resolve(__dirname, '../..')],
    },
    port: 3010,
    proxy: {
      '/api': {
        target: 'http://localhost:5021',
        changeOrigin: true,
      },
    },
  },
});
