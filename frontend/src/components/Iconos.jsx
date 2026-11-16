// Iconos en SVG, sin dependencias externas.
const base = { width: 22, height: 22, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor',
  strokeWidth: 1.9, strokeLinecap: 'round', strokeLinejoin: 'round', 'aria-hidden': true }

export const IconoBuscar = () => (
  <svg {...base}><circle cx="11" cy="11" r="7" /><path d="m20 20-3.600-3.600" /></svg>
)
export const IconoCochera = () => (
  <svg {...base}><path d="M3 21V9l9-6 9 6v12" /><path d="M7 21v-8h10v8" /><path d="M7 17h10" /></svg>
)
export const IconoReservas = () => (
  <svg {...base}><rect x="3" y="5" width="18" height="16" rx="2" /><path d="M8 3v4M16 3v4M3 10h18" /></svg>
)
export const IconoChat = () => (
  <svg {...base}><path d="M21 12a8 8 0 0 1-11.800 7L4 20l1.100-4.400A8 8 0 1 1 21 12Z" /></svg>
)
export const IconoUbicacion = () => (
  <svg {...base} width="16" height="16"><path d="M12 21s7-6.200 7-11.500A7 7 0 0 0 5 9.500C5 14.800 12 21 12 21Z" /><circle cx="12" cy="9.500" r="2.500" /></svg>
)
export const IconoMira = () => (
  <svg {...base} width="18" height="18"><circle cx="12" cy="12" r="7" /><path d="M12 2v3M12 19v3M2 12h3M19 12h3" /></svg>
)
export const IconoEnviar = () => (
  <svg {...base} width="20" height="20"><path d="M4 12 20 4l-6 16-3-7-7-1Z" /></svg>
)
