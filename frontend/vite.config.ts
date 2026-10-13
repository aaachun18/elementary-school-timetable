import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    // The backend's CORS allows only http://localhost:5173 -- fail loudly if
    // the port is taken instead of silently moving to 5174, where every API
    // call would be blocked by CORS.
    strictPort: true,
  },
})
