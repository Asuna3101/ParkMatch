import { ESTADOS, TIPOS } from '../utils'

export const Estado = ({ estado }) => {
  const { texto, tono } = ESTADOS[estado] ?? { texto: estado, tono: 'neutro' }
  return <span className={`etiqueta etiqueta-${tono}`}>{texto}</span>
}

export const Error = ({ children }) => (children ? <p className="mensaje-error" role="alert">{children}</p> : null)

export const Vacio = ({ titulo, children }) => (
  <div className="vacio">
    <h2>{titulo}</h2>
    {children}
  </div>
)

export const Rasgos = ({ cochera }) => (
  <ul className="rasgos">
    <li>{TIPOS[cochera.tipo_vehiculo]}</li>
    <li>{cochera.techada ? 'Techada' : 'Descubierta'}</li>
    {cochera.largo_m && <li>{cochera.largo_m} × {cochera.ancho_m} m</li>}
  </ul>
)
