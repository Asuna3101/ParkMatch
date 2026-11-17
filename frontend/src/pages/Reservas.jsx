import { useEffect, useState } from 'react'
import { api, ErrorApi } from '../api'
import { useAuth } from '../auth'
import { ElegirEstrellas, Error, Estado, Vacio } from '../components/Comunes'
import { useTiempoReal } from '../tiempo-real'
import { fechaHora, rango, soles } from '../utils'

const FILTROS_ARRENDADOR = [
  { id: 'solicitudes', texto: 'Solicitudes', incluye: ['solicitada'] },
  { id: 'reservas', texto: 'Reservas', incluye: ['confirmada', 'en_curso'] },
  { id: 'historial', texto: 'Historial', incluye: ['finalizada', 'rechazada', 'cancelada'] },
]

const MEDIO = { tarjeta: 'Tarjeta', acordado: 'Acordado con el dueño' }
const TIPOS_DISPUTA = { reserva: 'Problema con la reserva', pago: 'Problema con el pago', conducta: 'Conducta de la otra parte' }

/** Calificar a la otra parte y abrir una disputa (US-20 y US-25). Lo usan ambas cuentas. */
function DespuesDeLaReserva({ r, aQuien, alTerminar }) {
  const { avisar } = useTiempoReal()
  const [estrellas, setEstrellas] = useState(0)
  const [comentario, setComentario] = useState('')
  const [disputa, setDisputa] = useState(null)   // null = cerrado; { tipo, descripcion } = abierto
  const [error, setError] = useState('')

  const calificar = async (e) => {
    e.preventDefault()
    setError('')
    try {
      await api.calificar(r.id, estrellas, comentario.trim() || null)
      avisar('¡Gracias por tu calificación!')
      alTerminar()
    } catch (err) {
      setError(err.message)
    }
  }

  const enviarDisputa = async (e) => {
    e.preventDefault()
    setError('')
    try {
      await api.abrirDisputa(r.id, disputa.tipo, disputa.descripcion.trim())
      avisar('Disputa enviada. El equipo de ParkMatch la revisará.')
      setDisputa(null)
      alTerminar()
    } catch (err) {
      setError(err.message)
    }
  }

  const puedeDisputar = ['confirmada', 'en_curso', 'finalizada', 'cancelada'].includes(r.estado) && !r.disputa_abierta

  return (
    <>
      {r.mi_calificacion && <p className="ayuda">Calificaste a {aQuien} con {r.mi_calificacion} ★</p>}
      {r.puede_calificar && (
        <form className="calificar" onSubmit={calificar}>
          <p><strong>¿Cómo te fue con {aQuien}?</strong></p>
          <ElegirEstrellas valor={estrellas} alCambiar={setEstrellas} />
          <label className="campo">
            <span>Comentario (opcional)</span>
            <textarea rows={2} maxLength={600} value={comentario} onChange={(e) => setComentario(e.target.value)} />
          </label>
          <button className="boton boton-primario" disabled={!estrellas}>Enviar calificación</button>
        </form>
      )}
      {r.disputa_abierta && <p className="ayuda ayuda-alerta">Hay una disputa abierta sobre esta reserva.</p>}
      {puedeDisputar && (disputa ? (
        <form className="calificar" onSubmit={enviarDisputa}>
          <label className="campo">
            <span>Tipo de problema</span>
            <select value={disputa.tipo} onChange={(e) => setDisputa({ ...disputa, tipo: e.target.value })}>
              {Object.entries(TIPOS_DISPUTA).map(([v, t]) => <option key={v} value={v}>{t}</option>)}
            </select>
          </label>
          <label className="campo">
            <span>Cuéntanos qué pasó <em>(mínimo 15 caracteres)</em></span>
            <textarea rows={3} maxLength={1500} value={disputa.descripcion}
              onChange={(e) => setDisputa({ ...disputa, descripcion: e.target.value })} />
          </label>
          <div className="fila-botones">
            <button className="boton boton-primario" disabled={disputa.descripcion.trim().length < 15}>Enviar disputa</button>
            <button type="button" className="boton boton-texto" onClick={() => setDisputa(null)}>Cancelar</button>
          </div>
        </form>
      ) : (
        <button className="boton boton-texto" onClick={() => setDisputa({ tipo: 'reserva', descripcion: '' })}>
          Reportar un problema
        </button>
      ))}
      <Error>{error}</Error>
    </>
  )
}

/** Reservas del arrendatario o solicitudes del arrendador, según el tipo de cuenta. */
export default function Reservas() {
  const { esArrendador } = useAuth()
  return esArrendador ? <PanelArrendador /> : <PanelArrendatario />
}

function useCarga(cargar) {
  const [datos, setDatos] = useState(null)
  const [error, setError] = useState('')
  const recargar = () => cargar().then(setDatos).catch((e) => setError(e.message))
  useEffect(() => {
    recargar()
  }, []) // eslint-disable-line react-hooks/exhaustive-deps
  return { datos, error, setError, recargar }
}

/* --------------------------------------------------------- arrendatario */
function PanelArrendatario() {
  const { escuchar, avisar } = useTiempoReal()
  const { datos: reservas, error, setError, recargar } = useCarga(api.misReservas)

  useEffect(() => escuchar((e) => { if (e.tipo === 'reserva') recargar() }), [escuchar]) // eslint-disable-line react-hooks/exhaustive-deps

  const accion = async (fn, mensaje) => {
    setError('')
    try {
      await fn()
      if (mensaje) avisar(mensaje)
      recargar()
    } catch (e) {
      setError(e instanceof ErrorApi ? e.message : 'No pudimos completar la acción.')
    }
  }

  if (!reservas) return error ? <Error>{error}</Error> : <p className="cargando">Cargando…</p>

  return (
    <div className="pagina">
      <h1>Mis reservas</h1>
      <Error>{error}</Error>
      <div className="dos-columnas">
        <div>
          {reservas.length === 0 ? (
            <Vacio titulo="Aún no tienes reservas">
              <p>Busca una cochera en el mapa y pide el horario que necesitas.</p>
            </Vacio>
          ) : (
            <ul className="lista-reservas">
              {reservas.map((r) => (
                <ReservaArrendatario key={r.id} r={r} recargar={recargar}
                  onCancelar={() => accion(() => api.cancelar(r.id), 'Reserva cancelada.')} />
              ))}
            </ul>
          )}
        </div>
        <Tarjetas />
      </div>
    </div>
  )
}

function ReservaArrendatario({ r, onCancelar, recargar }) {
  const [qr, setQr] = useState(null)
  const [confirmando, setConfirmando] = useState(false)
  const [error, setError] = useState('')

  const verQr = async () => {
    try {
      const blob = await api.codigoQr(r.id)
      setQr(URL.createObjectURL(blob))
    } catch (e) {
      setError(e.message)
    }
  }

  return (
    <li className="tarjeta-reserva-lista">
      <div className="cabecera-reserva">
        <div>
          <h2>{r.cochera_titulo}</h2>
          <p className="tarjeta-lugar">{r.cochera_direccion}</p>
        </div>
        <Estado estado={r.estado} />
      </div>
      <p>{rango(r.inicio, r.fin)}</p>
      <p className="ayuda">
        {MEDIO[r.medio_pago]}{r.tarjeta ? ` · ${r.tarjeta}` : ''} · Total {soles(r.total_final)}
        {r.minutos_exceso > 0 && ` (incluye ${r.minutos_exceso} min adicionales)`}
      </p>
      {r.pago && <p className="ayuda">Pago: <Estado estado={r.pago.estado} />{r.pago.comprobante_numero && ` · Comprobante ${r.pago.comprobante_numero}`}</p>}
      {r.motivo_rechazo && <p className="ayuda ayuda-alerta">Motivo: {r.motivo_rechazo}</p>}
      {r.otro_telefono && <p className="ayuda">Contacto del dueño: {r.otro_telefono}</p>}

      {r.codigo && (
        <div className="codigo-acceso">
          {qr ? (
            <>
              <img src={qr} alt="Código QR de acceso" className="qr" />
              <p>Muestra este código al dueño al llegar. Código: <strong>{r.codigo.codigo}</strong></p>
            </>
          ) : (
            <button className="boton boton-secundario" onClick={verQr}>Mostrar código de acceso</button>
          )}
          <p className="ayuda">Válido desde {fechaHora(r.codigo.valido_desde)} hasta {fechaHora(r.codigo.valido_hasta)}.</p>
        </div>
      )}

      <Error>{error}</Error>
      {r.puede_cancelar && (
        confirmando ? (
          <div className="confirmar">
            <p>{r.estado === 'confirmada'
              ? (r.devolucion_si_cancela
                ? 'Si cancelas ahora te devolvemos el pago.'
                : 'Faltan menos de 2 horas: la cancelación no tiene devolución.')
              : 'Se cancelará tu solicitud.'}</p>
            <button className="boton boton-peligro" onClick={() => { setConfirmando(false); onCancelar() }}>Sí, cancelar</button>
            <button className="boton boton-texto" onClick={() => setConfirmando(false)}>No</button>
          </div>
        ) : (
          <button className="boton boton-texto boton-peligro" onClick={() => setConfirmando(true)}>Cancelar reserva</button>
        )
      )}
      <DespuesDeLaReserva r={r} aQuien={r.arrendador_nombre} alTerminar={recargar} />
    </li>
  )
}

function Tarjetas() {
  const { datos: tarjetas, error, setError, recargar } = useCarga(api.tarjetas)
  const { avisar } = useTiempoReal()
  const [form, setForm] = useState({ titular: '', numero: '', vence_mes: '', vence_anio: '', cvv: '' })
  const set = (c) => (e) => setForm({ ...form, [c]: e.target.value })

  const agregar = async (e) => {
    e.preventDefault()
    setError('')
    try {
      await api.agregarTarjeta({ ...form, vence_mes: Number(form.vence_mes), vence_anio: Number(form.vence_anio) })
      setForm({ titular: '', numero: '', vence_mes: '', vence_anio: '', cvv: '' })
      avisar('Tarjeta guardada.')
      recargar()
    } catch (err) {
      setError(err instanceof ErrorApi ? err.message : 'No pudimos guardar la tarjeta.')
    }
  }

  const quitar = async (id) => {
    await api.eliminarTarjeta(id)
    recargar()
  }

  return (
    <aside className="panel-tarjetas">
      <h2>Mis tarjetas</h2>
      <p className="ayuda">Tarjetas simuladas para probar el pago. Usa 4111 1111 1111 1111 (aprobada) o una que termine en 9995 (sin fondos).</p>
      {tarjetas?.length ? (
        <ul className="lista-simple">
          {tarjetas.map((t) => (
            <li key={t.id}>{t.marca} •••• {t.ultimos4} · {t.titular}
              <button className="boton boton-texto boton-peligro" onClick={() => quitar(t.id)}>Quitar</button>
            </li>
          ))}
        </ul>
      ) : <p className="ayuda">No tienes tarjetas guardadas.</p>}

      <form onSubmit={agregar} className="formulario-tarjeta" noValidate>
        <label className="campo"><span>Titular</span><input required value={form.titular} onChange={set('titular')} /></label>
        <label className="campo"><span>Número</span><input required inputMode="numeric" value={form.numero} onChange={set('numero')} /></label>
        <div className="fila-campos">
          <label className="campo campo-corto"><span>Mes</span><input required inputMode="numeric" value={form.vence_mes} onChange={set('vence_mes')} /></label>
          <label className="campo campo-corto"><span>Año</span><input required inputMode="numeric" value={form.vence_anio} onChange={set('vence_anio')} placeholder="2030" /></label>
          <label className="campo campo-corto"><span>CVV</span><input required inputMode="numeric" value={form.cvv} onChange={set('cvv')} /></label>
        </div>
        <Error>{error}</Error>
        <button className="boton boton-secundario boton-ancho">Guardar tarjeta</button>
      </form>
    </aside>
  )
}

/* ------------------------------------------------------------ arrendador */
function PanelArrendador() {
  const { escuchar, avisar } = useTiempoReal()
  const [filtro, setFiltro] = useState('solicitudes')
  const { datos: reservas, error, setError, recargar } = useCarga(api.reservasRecibidas)
  const { datos: pagos, recargar: recargarPagos } = useCarga(api.pagosArrendador)

  useEffect(() => escuchar((e) => { if (e.tipo === 'reserva') recargar() }), [escuchar]) // eslint-disable-line react-hooks/exhaustive-deps

  const accion = async (fn, mensaje) => {
    setError('')
    try {
      await fn()
      if (mensaje) avisar(mensaje)
      recargar()
      recargarPagos()
    } catch (e) {
      setError(e instanceof ErrorApi ? e.message : 'No pudimos completar la acción.')
    }
  }

  if (!reservas) return error ? <Error>{error}</Error> : <p className="cargando">Cargando…</p>

  const grupo = FILTROS_ARRENDADOR.find((f) => f.id === filtro)
  const visibles = reservas.filter((r) => grupo.incluye.includes(r.estado))

  return (
    <div className="pagina">
      <h1>Solicitudes y reservas</h1>
      <nav className="pestanas" aria-label="Filtro">
        {FILTROS_ARRENDADOR.map((f) => (
          <button key={f.id} className={`pestana${filtro === f.id ? ' activa' : ''}`} onClick={() => setFiltro(f.id)}>
            {f.texto} <span className="contador-pestana">{reservas.filter((r) => f.incluye.includes(r.estado)).length}</span>
          </button>
        ))}
      </nav>
      <Error>{error}</Error>

      {visibles.length === 0 ? (
        <Vacio titulo={filtro === 'solicitudes' ? 'No tienes solicitudes pendientes' : 'Nada por aquí todavía'}>
          <p>Cuando alguien pida un horario en tus cocheras, aparecerá aquí.</p>
        </Vacio>
      ) : (
        <ul className="lista-reservas">
          {visibles.map((r) => (
            <ReservaArrendador key={r.id} r={r} recargar={recargar}
              onConfirmar={() => accion(() => api.confirmar(r.id), 'Reserva confirmada.')}
              onRechazar={(motivo) => accion(() => api.rechazar(r.id, motivo), 'Solicitud rechazada.')}
              onPagoRecibido={(medio) => accion(() => api.pagoRecibido(r.id, medio), 'Pago registrado. Se emitió el comprobante.')}
              onIngreso={(codigo) => accion(() => api.registrarIngreso(r.id, codigo), 'Ingreso registrado.')}
              onSalida={() => accion(() => api.registrarSalida(r.id), 'Salida registrada.')}
              onDevuelto={() => accion(() => api.pagoDevuelto(r.id), 'Devolución registrada.')} />
          ))}
        </ul>
      )}

      {pagos && pagos.pagos.length > 0 && (
        <section className="bloque">
          <h2>Pagos</h2>
          <p className="ayuda">Cobrado: {soles(pagos.total_pagado)} · Pendiente: {soles(pagos.total_pendiente)} · Devuelto: {soles(pagos.total_reembolsado)}</p>
          <table className="tabla">
            <thead><tr><th>Cochera</th><th>Horario</th><th>Monto</th><th>Estado</th><th>Comprobante</th></tr></thead>
            <tbody>
              {pagos.pagos.map((p) => (
                <tr key={p.reserva_id}>
                  <td>{p.cochera_titulo}</td>
                  <td>{rango(p.inicio, p.fin)}</td>
                  <td>{soles(p.monto)}</td>
                  <td><Estado estado={p.estado} /></td>
                  <td>{p.comprobante_numero || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
    </div>
  )
}

function ReservaArrendador({ r, recargar, onConfirmar, onRechazar, onPagoRecibido, onIngreso, onSalida, onDevuelto }) {
  const [motivo, setMotivo] = useState('')
  const [medio, setMedio] = useState('efectivo')
  const [codigo, setCodigo] = useState('')
  const pendientePago = r.pago?.estado === 'pendiente'

  return (
    <li className="tarjeta-reserva-lista">
      <div className="cabecera-reserva">
        <div>
          <h2>{r.cochera_titulo}</h2>
          <p className="tarjeta-lugar">{r.arrendatario_nombre} · {rango(r.inicio, r.fin)}</p>
        </div>
        <Estado estado={r.estado} />
      </div>
      <p className="ayuda">
        {MEDIO[r.medio_pago]}{r.tarjeta ? ` · ${r.tarjeta}` : ''} · {soles(r.costo_total)}
        {r.minutos_exceso > 0 && ` · salida tarde: ${soles(r.cargo_exceso + r.penalizacion)} adicionales`}
      </p>
      {r.pago && <p className="ayuda">Pago: <Estado estado={r.pago.estado} />{r.pago.medio && ` · ${r.pago.medio}`}{r.pago.comprobante_numero && ` · ${r.pago.comprobante_numero}`}</p>}

      {r.estado === 'solicitada' && (
        <div className="acciones-reserva">
          <button className="boton boton-primario" onClick={onConfirmar}>Aceptar</button>
          <input value={motivo} onChange={(e) => setMotivo(e.target.value)} placeholder="Motivo (opcional)" aria-label="Motivo del rechazo" />
          <button className="boton boton-texto boton-peligro" onClick={() => onRechazar(motivo)}>Rechazar</button>
        </div>
      )}

      {r.estado === 'confirmada' && (
        <div className="acciones-reserva">
          {pendientePago && (
            <>
              <select value={medio} onChange={(e) => setMedio(e.target.value)} aria-label="Medio de pago">
                <option value="efectivo">Efectivo</option>
                <option value="billetera">Billetera digital</option>
              </select>
              <button className="boton boton-secundario" onClick={() => onPagoRecibido(medio)}>Registrar pago recibido</button>
            </>
          )}
          <input value={codigo} onChange={(e) => setCodigo(e.target.value)} placeholder="Código del arrendatario" aria-label="Código de acceso" />
          <button className="boton boton-primario" disabled={!codigo.trim()} onClick={() => onIngreso(codigo)}>Registrar ingreso</button>
        </div>
      )}

      {r.estado === 'en_curso' && (
        <div className="acciones-reserva">
          <button className="boton boton-primario" onClick={onSalida}>Registrar salida</button>
          {pendientePago && <button className="boton boton-secundario" onClick={() => onPagoRecibido(medio)}>Registrar pago recibido</button>}
        </div>
      )}

      {r.pago?.estado === 'por_devolver' && (
        <div className="acciones-reserva">
          <p className="ayuda ayuda-alerta">Esta reserva se canceló con devolución. Entrega {soles(r.pago.monto)} al arrendatario.</p>
          <button className="boton boton-secundario" onClick={onDevuelto}>Marcar como devuelto</button>
        </div>
      )}
      <DespuesDeLaReserva r={r} aQuien={r.arrendatario_nombre} alTerminar={recargar} />
    </li>
  )
}
