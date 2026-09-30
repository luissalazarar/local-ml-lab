import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const release = JSON.parse(readFileSync(resolve(__dirname, '../version.json'), 'utf8'))

export default defineConfig({
  plugins:[react()],
  define:{__DISPLAY_VERSION__:JSON.stringify(release.display)},
  server:{proxy:{'/api':'http://localhost:8000'}},
  test:{environment:'jsdom',include:['src/**/*.test.{ts,tsx}']},
})
