// Geometría del símbolo de Laboratorio ML en una retícula de 48 × 48.
// Debe coincidir con los SVG de public/brand/ (lo comprueba BrandSymbol.test.tsx).
// sheet: hoja de datos con tres puntos en ascenso; heldOut: celda apartada donde el patrón se comprueba.
export const symbolGeometry = {
  full: {
    sheet: 'M12 4H25A2 2 0 0 1 27 6V19A2 2 0 0 0 29 21H42A2 2 0 0 1 44 23V36A8 8 0 0 1 36 44H12A8 8 0 0 1 4 36V12A8 8 0 0 1 12 4ZM8 37a3 3 0 1 0 6 0a3 3 0 1 0 -6 0ZM14 31a3 3 0 1 0 6 0a3 3 0 1 0 -6 0ZM20 25a3 3 0 1 0 6 0a3 3 0 1 0 -6 0Z',
    heldOut: 'M32 4H36A8 8 0 0 1 44 12V16A2 2 0 0 1 42 18H32A2 2 0 0 1 30 16V6A2 2 0 0 1 32 4ZM34 11a3 3 0 1 0 6 0a3 3 0 1 0 -6 0Z',
  },
  // Versión reducida para 24 px o menos: dos puntos más grandes y separaciones más anchas.
  reduced: {
    sheet: 'M11 2H22A2 2 0 0 1 24 4V22A2 2 0 0 0 26 24H44A2 2 0 0 1 46 26V37A9 9 0 0 1 37 46H11A9 9 0 0 1 2 37V11A9 9 0 0 1 11 2ZM6 38a4 4 0 1 0 8 0a4 4 0 1 0 -8 0ZM14 30a4 4 0 1 0 8 0a4 4 0 1 0 -8 0Z',
    heldOut: 'M30 2H37A9 9 0 0 1 46 11V18A2 2 0 0 1 44 20H30A2 2 0 0 1 28 18V4A2 2 0 0 1 30 2ZM33 11a4 4 0 1 0 8 0a4 4 0 1 0 -8 0Z',
  },
} as const

export const REDUCED_MAX_SIZE = 24
