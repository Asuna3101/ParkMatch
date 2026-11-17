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

/** Promedio de estrellas en texto y con iconos (US-21). */
export const Estrellas = ({ valor, total }) => {
  if (valor == null) return <span className="estrellas estrellas-vacio">Sin calificaciones</span>
  const llenas = Math.round(valor)
  return (
    <span className="estrellas" aria-label={`${valor} de 5 estrellas`}>
      <span aria-hidden="true">{'★'.repeat(llenas)}<span className="estrella-gris">{'★'.repeat(5 - llenas)}</span></span>
      {' '}{valor.toFixed(1)}{total != null && <span className="ayuda"> ({total})</span>}
    </span>
  )
}

/** Selector de 1 a 5 estrellas. */
export const ElegirEstrellas = ({ valor, alCambiar }) => (
  <div className="elegir-estrellas" role="radiogroup" aria-label="Calificación">
    {[1, 2, 3, 4, 5].map((n) => (
      <button key={n} type="button" role="radio" aria-checked={valor === n} aria-label={`${n} estrella${n > 1 ? 's' : ''}`}
        className={n <= valor ? 'llena' : ''} onClick={() => alCambiar(n)}>★</button>
    ))}
  </div>
)

export const Resenas = ({ resenas }) => (
  <ul className="resenas">
    {resenas.map((r) => (
      <li key={r.id}>
        <p><strong>{r.autor_nombre}</strong> · <Estrellas valor={r.estrellas} /></p>
        {r.cochera_titulo && <p className="ayuda">{r.cochera_titulo}</p>}
        {r.comentario && <p className="texto">{r.comentario}</p>}
      </li>
    ))}
  </ul>
)
