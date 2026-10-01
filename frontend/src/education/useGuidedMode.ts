import { useEffect, useState } from 'react'

const key = 'local-ml-lab-guided-mode'

export function useGuidedMode() {
  const [guided, setGuided] = useState(() => localStorage.getItem(key) !== 'technical')
  useEffect(() => localStorage.setItem(key, guided ? 'guided' : 'technical'), [guided])
  return { guided, toggle: () => setGuided(value => !value) }
}
