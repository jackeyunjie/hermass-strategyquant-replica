import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 3000,
    host: true,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
    rollupOptions: {
      output: {
        manualChunks: (id: string) => {
          if (id.includes('node_modules/react') || id.includes('node_modules/react-dom') || id.includes('node_modules/react-router-dom')) {
            return 'vendor';
          }
          if (id.includes('node_modules/antd')) {
            return 'antd';
          }
          if (id.includes('node_modules/echarts') || id.includes('node_modules/lightweight-charts') || id.includes('node_modules/echarts-for-react')) {
            return 'charts';
          }
          if (id.includes('node_modules/reactflow')) {
            return 'reactflow';
          }
          if (id.includes('node_modules/ag-grid')) {
            return 'grid';
          }
          return undefined;
        },
      },
    },
  },
})
