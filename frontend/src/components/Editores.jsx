import { DIAS, HORAS_FIN, HORAS_INICIO, hhmm } from '../utils'

const SelectorHora = ({ valor, opciones, alCambiar, etiqueta }) => (
  <select value={valor} onChange={(e) => alCambiar(e.target.value)} aria-label={etiqueta}>
    {opciones.map((h) => <option key={h} value={h}>{hhmm(h)}</option>)}
  </select>
)

/** Calendario semanal: por cada día, si está disponible y en qué horario (US-07). */
export function EditorCalendario({ valor, alCambiar }) {
  const cambiar = (dia, cambios) => alCambiar(valor.map((d, i) => (i === dia ? { ...d, ...cambios } : d)))
  const copiarATodos = () => {
    const base = valor.find((d) => d.activo)
    if (base) alCambiar(valor.map((d) => ({ ...d, activo: true, inicio: base.inicio, fin: base.fin })))
  }

  return (
    <div className="calendario-editor">
      {valor.map((d, i) => (
        <div key={i} className={`dia-fila${d.activo ? '' : ' dia-inactivo'}`}>
          <label className="dia-nombre">
            <input type="checkbox" checked={d.activo} onChange={(e) => cambiar(i, { activo: e.target.checked })} />
            {DIAS[i]}
          </label>
          {d.activo ? (
            <div className="dia-horas">
              <SelectorHora valor={d.inicio} opciones={HORAS_INICIO} etiqueta={`${DIAS[i]}, desde`}
                alCambiar={(inicio) => cambiar(i, { inicio })} />
              <span>a</span>
              <SelectorHora valor={d.fin} opciones={HORAS_FIN} etiqueta={`${DIAS[i]}, hasta`}
                alCambiar={(fin) => cambiar(i, { fin })} />
            </div>
          ) : (
            <span className="apagado">No disponible</span>
          )}
        </div>
      ))}
      <button type="button" className="boton boton-texto" onClick={copiarATodos}>
        Usar el mismo horario todos los días
      </button>
    </div>
  )
}

export const calendarioInicial = () =>
  DIAS.map((_, i) => ({ activo: i < 5, inicio: '08:00', fin: '20:00' }))

/** Del formato de la API al del editor: una franja por día (la primera, si hay varias). */
export const calendarioDesdeApi = (franjas) =>
  DIAS.map((_, i) => {
    const del = franjas.filter((f) => f.dia_semana === i)
    if (!del.length) return { activo: false, inicio: '08:00', fin: '20:00' }
    return { activo: true, inicio: String(del[0].hora_inicio).slice(0, 5), fin: String(del[del.length - 1].hora_fin).slice(0, 5) }
  })

export const calendarioParaApi = (valor) =>
  valor.flatMap((d, i) => (d.activo ? [{ dia_semana: i, hora_inicio: d.inicio, hora_fin: d.fin }] : []))

export const errorCalendario = (valor) => {
  if (!valor.some((d) => d.activo)) return 'Marca al menos un día disponible.'
  const malo = valor.findIndex((d) => d.activo && d.fin <= d.inicio)
  return malo >= 0 ? `${DIAS[malo]}: la hora final debe ser posterior a la inicial.` : null
}

/** Precio base y tarifas distintas por franja del día (US-06). */
export function EditorTarifas({ precio, tarifas, alCambiarPrecio, alCambiarTarifas }) {
  const cambiar = (i, cambios) => alCambiarTarifas(tarifas.map((t, n) => (n === i ? { ...t, ...cambios } : t)))
  const agregar = () => alCambiarTarifas([...tarifas, { inicio: '18:00', fin: '22:00', precio: '' }])
  const quitar = (i) => alCambiarTarifas(tarifas.filter((_, n) => n !== i))

  return (
    <div className="tarifas-editor">
      <label className="campo campo-corto">
        <span>Precio por hora</span>
        <div className="con-prefijo">
          <span>S/</span>
          <input type="number" min="0.5" step="0.5" inputMode="decimal" required value={precio}
            onChange={(e) => alCambiarPrecio(e.target.value)} placeholder="6.00" />
        </div>
      </label>

      {tarifas.length > 0 && <p className="ayuda">Dentro de estos horarios se cobra el precio indicado; el resto del día, el precio por hora.</p>}
      {tarifas.map((t, i) => (
        <div key={i} className="tarifa-fila">
          <SelectorHora valor={t.inicio} opciones={HORAS_INICIO} etiqueta="Desde" alCambiar={(inicio) => cambiar(i, { inicio })} />
          <span>a</span>
          <SelectorHora valor={t.fin} opciones={HORAS_FIN} etiqueta="Hasta" alCambiar={(fin) => cambiar(i, { fin })} />
          <div className="con-prefijo">
            <span>S/</span>
            <input type="number" min="0.5" step="0.5" inputMode="decimal" required value={t.precio}
              onChange={(e) => cambiar(i, { precio: e.target.value })} aria-label="Precio por hora en esta franja" placeholder="9.00" />
          </div>
          <button type="button" className="boton boton-texto boton-peligro" onClick={() => quitar(i)}>Quitar</button>
        </div>
      ))}
      <button type="button" className="boton boton-texto" onClick={agregar}>
        Agregar un precio distinto para un horario
      </button>
    </div>
  )
}

export const tarifasDesdeApi = (tarifas) =>
  tarifas.map((t) => ({ inicio: String(t.hora_inicio).slice(0, 5), fin: String(t.hora_fin).slice(0, 5), precio: String(t.precio_hora) }))

export const tarifasParaApi = (tarifas) =>
  tarifas.map((t) => ({ hora_inicio: t.inicio, hora_fin: t.fin, precio_hora: Number(t.precio) }))

export const errorTarifas = (precio, tarifas) => {
  if (!(Number(precio) > 0)) return 'Indica el precio por hora.'
  if (tarifas.some((t) => !(Number(t.precio) > 0))) return 'Indica el precio de cada horario especial.'
  if (tarifas.some((t) => t.fin <= t.inicio)) return 'En cada horario especial, la hora final debe ser posterior a la inicial.'
  const orden = [...tarifas].sort((a, b) => a.inicio.localeCompare(b.inicio))
  if (orden.some((t, i) => i > 0 && t.inicio < orden[i - 1].fin)) return 'Dos horarios especiales se cruzan.'
  return null
}
