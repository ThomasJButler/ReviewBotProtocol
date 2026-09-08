import nextCoreWebVitals from 'eslint-config-next/core-web-vitals'
import nextTypescript from 'eslint-config-next/typescript'
import prettier from 'eslint-config-prettier'

// eslint-config-next 16 ships flat config itself, so the eslintrc compatibility
// layer this file used until Next 15 is gone: eslint 10 could not load the new
// config through it at all ("Converting circular structure to JSON").
const config = [
  {
    ignores: [
      '.next/**',
      'node_modules/**',
      'next-env.d.ts',
      'backend/**',
      '.claude/**', // agent worktrees live here and carry their own next-env.d.ts
    ],
  },
  ...nextCoreWebVitals,
  ...nextTypescript,
  prettier,
]

export default config
