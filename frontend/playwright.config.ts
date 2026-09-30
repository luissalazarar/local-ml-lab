import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  timeout: 120_000,
  expect: { timeout: 15_000 },
  use: { baseURL: process.env.APP_URL ?? 'http://localhost:3000', trace: 'retain-on-failure' },
  reporter: 'line',
})
