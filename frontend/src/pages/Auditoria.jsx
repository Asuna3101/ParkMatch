import { useEffect, useState } from 'react'
import { api } from '../api'
import { Error, Vacio } from '../components/Comunes'
import { ACCIONES, fechaHora } from '../utils'

const ETIQUETAS = { monto: 'Monto', medio: 'Medio', titulo: 'Título', costo_total: 'Costo', minutos_exceso: 'Minutos extra', motivo: 'Motivo' }

const resumen = (detalle) => Object.entries(detalle)
  .filter(([k, v]) => !k.endsWith('_id') && v !== null && v !== '' && typeof v !== 'object')
  .map(([k, v]) => `${ETIQUETAS[k] ?? k}: ${typeof v === 'number' && k.includes('costo') || k === 'monto' ? `S/ ${Number(v).toFixed(2)}` : v}`)
  .join(' · ')

/** Registro de actividad: quién hizo qué y cuándo (requisitos 50 y 57). */
export default function Auditoria() {
  const [registros, setRegistros] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => { api.auditoria().then(setRegistros).catch((e) => setError(e.message)) }, [])

  if (!registros) return error ? <Error>{error}</Error> : <p className="cargando">Cargando…</p>

  return (
    <div className="pagina">
      <h1>Registro de actividad</h1>
      <p className="bajada-pagina">Cada cambio importante queda guardado con fecha y responsable.</p>
      <Error>{error}</Error>
      {registros.length === 0 ? (
        <Vacio titulo="Todavía no hay actividad"><p>Aparecerá aquí cuando publiques, reserves o pagues.</p></Vacio>
      ) : (
        <ol className="linea-tiempo">
          {registros.map((r) => (
            <li key={r.id}>
              <time>{fechaHora(r.creado_en)}</time>
              <div>
                <strong>{ACCIONES[r.accion] ?? r.accion}</strong>
                {r.usuario_nombre && <span> · {r.usuario_nombre}</span>}
                {resumen(r.detalle) && <p className="ayuda">{resumen(r.detalle)}</p>}
              </div>
            </li>
          ))}
        </ol>
      )}
    </div>
  )
}
