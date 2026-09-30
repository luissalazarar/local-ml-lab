import js from '@eslint/js'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import tseslint from 'typescript-eslint'

export default tseslint.config(
  { ignores: ['dist'] },
  { extends: [js.configs.recommended, ...tseslint.configs.recommended], files: ['**/*.{ts,tsx}'], languageOptions: { ecmaVersion: 2022, globals: { document: 'readonly', window: 'readonly', location: 'readonly', navigator: 'readonly', fetch: 'readonly', FormData: 'readonly', Headers: 'readonly', RequestInit: 'readonly', setTimeout: 'readonly', setInterval: 'readonly', clearInterval: 'readonly' } }, plugins: { 'react-hooks': reactHooks, 'react-refresh': reactRefresh }, rules: { ...reactHooks.configs.recommended.rules, 'react-refresh/only-export-components': ['warn', { allowConstantExport: true }] } }
)

