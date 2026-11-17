import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import { Error, Estado, Vacio } from '../components/Comunes'
import { useTiempoReal } from '../tiempo-real'
import { fechaHora, rango, soles } from '../utils'

const MOTIVOS = {
  informacion_falsa: 'Información falsa', fotos_enganosas: 'Fotos engañosas', precio_abusivo: 'Precio abusivo',
  inseguro: 'Lugar inseguro', contenido_inapropiado: 'Contenido inapropiado', otro: 'Otro motivo',
}
const ACCIONES_DISPUTA = {
  sin_accion: 'Cerrar sin acción', reembolso: 'Devolver el pago', cancelacion: 'Cancelar la reserva y devolver',
}
const PESTANAS = [
  { id: 'reportes', texto: 'Reportes', cuenta: 'reportes_pendientes' },
  { id: 'disputas', texto: 'Disputas', cuenta: 'disputas_abiertas' },
  { id: 'verificaciones', texto: 'Identidad', cuenta: 'verificaciones_pendientes' },
]

/** Panel de moderación del administrador (US-23, US-24, US-25 y requisito 5). */
export default function Admin() {
  const { avisar } = useTiempoReal()
  const [resumen, setResumen] = useState(null)
  const [pestana, setPestana] = useState('reportes')
  const [casos, setCasos] = useState(null)
  const [error, setError] = useState('')

  const cargar = useCallback(async () => {
    setError('')
    try {
      setResumen(await api.admin.resumen())
      const fuente = { reportes: api.admin.reportes, disputas: api.admin.disputas, verificaciones: api.admin.verificaciones }
      setCasos(await fuente[pestana]())
    } catch (e) {
      setError(e.message)
    }
  }, [pestana])

  useEffect(() => { setCasos(null); cargar() }, [cargar])

  const hacer = async (fn, mensaje) => {
    setError('')
    try {
      await fn()
      avisar(mensaje)
      cargar()
    } catch (e) {
      setError(e.message)
    }
  }

  return (
    <div className="pagina">
      <h1>Administración</h1>
      {resumen && (
        <div className="resumen-admin">
          <div><strong>{resumen.usuarios}</strong><span>usuarios</span></div>
          <div><strong>{resumen.cocheras_activas}</strong><span>cocheras activas</span></div>
          <div><strong>{resumen.cocheras_suspendidas}</strong><span>suspendidas</span></div>
          <div><strong>{resumen.reservas}</strong><span>reservas</span></div>
        </div>
      )}

      <nav className="pestanas" aria-label="Casos">
        {PESTANAS.map((p) => (
          <button key={p.id} className={`pestana${pestana === p.id ? ' activa' : ''}`} onClick={() => setPestana(p.id)}>
            {p.texto} {resumen && <span className="contador-pestana">{resumen[p.cuenta]}</span>}
          </button>
        ))}
      </nav>
      <Error>{error}</Error>

      {!casos ? <p className="cargando">Cargando…</p>
        : casos.length === 0 ? <Vacio titulo="No hay casos pendientes"><p>Todo al día.</p></Vacio>
        : pestana === 'reportes' ? casos.map((r) => <CasoReporte key={r.id} r={r} hacer={hacer} />)
        : pestana === 'disputas' ? casos.map((d) => <CasoDisputa key={d.id} d={d} hacer={hacer} />)
        : casos.map((v) => <CasoVerificacion key={v.usuario_id} v={v} hacer={hacer} />)}
    </div>
  )
}

function CasoReporte({ r, hacer }) {
  const [nota, setNota] = useState('')
  return (
    <article className="caso">
      <h3><Link to={`/cocheras/${r.cochera_id}`}>{r.cochera_titulo}</Link></h3>
      <p className="ayuda">
        De {r.arrendador_nombre} · reportada por {r.autor_nombre} el {fechaHora(r.creado_en)}
        {r.reportes_previos > 0 && ` · ${r.reportes_previos} reporte(s) más de esta cochera`}
      </p>
      <p><strong>{MOTIVOS[r.motivo]}</strong>{r.detalle && `: ${r.detalle}`}</p>
      {r.cochera_suspendida && <p className="ayuda ayuda-alerta">La cochera ya está suspendida.</p>}
      <label className="campo">
        <span>Nota para el arrendador <em>(se muestra si se suspende)</em></span>
        <input value={nota} maxLength={300} onChange={(e) => setNota(e.target.value)} />
      </label>
      <div className="fila-botones">
        <button className="boton boton-peligro" onClick={() => hacer(() => api.admin.resolverReporte(r.id, 'procedente', nota || null), 'Cochera suspendida.')}>
          Procedente: suspender
        </button>
        <button className="boton boton-secundario" onClick={() => hacer(() => api.admin.resolverReporte(r.id, 'desestimado', nota || null), 'Reporte desestimado.')}>
          Desestimar
        </button>
        {r.cochera_suspendida && (
          <button className="boton boton-texto" onClick={() => hacer(() => api.admin.reactivarCochera(r.cochera_id), 'Suspensión levantada.')}>
            Levantar suspensión
          </button>
        )}
      </div>
    </article>
  )
}

function CasoDisputa({ d, hacer }) {
  const [accion, setAccion] = useState('sin_accion')
  const [resolucion, setResolucion] = useState('')
  return (
    <article className="caso">
      <h3>{d.cochera_titulo} · <Estado estado={d.estado_reserva} /></h3>
      <p className="ayuda">
        {d.arrendatario_nombre} con {d.arrendador_nombre} · {rango(d.inicio, d.fin)}
        {d.monto != null && <> · {soles(d.monto)} <Estado estado={d.estado_pago} /></>}
      </p>
      <p><strong>{d.autor_nombre}</strong> ({d.tipo}): {d.descripcion}</p>
      <div className="fila-campos">
        <label className="campo">
          <span>Decisión</span>
          <select value={accion} onChange={(e) => setAccion(e.target.value)}>
            {Object.entries(ACCIONES_DISPUTA).map(([v, t]) => <option key={v} value={v}>{t}</option>)}
          </select>
        </label>
      </div>
      <label className="campo">
        <span>Resolución <em>(mínimo 10 caracteres, la ven ambas partes)</em></span>
        <textarea rows={2} value={resolucion} onChange={(e) => setResolucion(e.target.value)} />
      </label>
      <button className="boton boton-primario" disabled={resolucion.trim().length < 10}
        onClick={() => hacer(() => api.admin.resolverDisputa(d.id, accion, resolucion.trim()), 'Disputa resuelta.')}>
        Resolver
      </button>
    </article>
  )
}

function CasoVerificacion({ v, hacer }) {
  const [imagen, setImagen] = useState(null)
  const [error, setError] = useState('')
  const ver = async () => {
    try {
      setImagen(URL.createObjectURL(await api.admin.documento(v.usuario_id)))
    } catch (e) {
      setError(e.message)
    }
  }
  return (
    <article className="caso">
      <h3>{v.nombre}</h3>
      <p className="ayuda">{v.correo} · {v.rol} · cuenta creada el {fechaHora(v.creado_en)}</p>
      {imagen ? <img src={imagen} alt={`Documento de ${v.nombre}`} style={{ maxHeight: 260 }} />
        : <button className="boton boton-texto" onClick={ver}>Ver documento</button>}
      <Error>{error}</Error>
      <div className="fila-botones">
        <button className="boton boton-primario" onClick={() => hacer(() => api.admin.resolverVerificacion(v.usuario_id, true), 'Identidad verificada.')}>Aprobar</button>
        <button className="boton boton-peligro" onClick={() => hacer(() => api.admin.resolverVerificacion(v.usuario_id, false), 'Verificación rechazada.')}>Rechazar</button>
      </div>
    </article>
  )
}

