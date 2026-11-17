import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api, ErrorApi, urlFoto } from '../api'
import { useAuth } from '../auth'
import { Error, Estrellas, Resenas } from '../components/Comunes'
import { IconoUbicacion } from '../components/Iconos'
import { MapaPunto } from '../components/Mapa'
import { useTiempoReal } from '../tiempo-real'
import { DIAS, HORAS_FIN, HORAS_INICIO, TIPOS, fechaHora, hhmm, hoyLima, isoLima, rango, soles, sumarDias } from '../utils'

const MOTIVOS = {
  informacion_falsa: 'Información falsa', fotos_enganosas: 'Fotos engañosas', precio_abusivo: 'Precio abusivo',
  inseguro: 'Lugar inseguro', contenido_inapropiado: 'Contenido inapropiado', otro: 'Otro motivo',
}

/** Reportar el anuncio al equipo de moderación (US-23). */
function Reportar({ cocheraId }) {
  const [abierto, setAbierto] = useState(false)
  const [motivo, setMotivo] = useState('informacion_falsa')
  const [detalle, setDetalle] = useState('')
  const [estado, setEstado] = useState({ error: '', listo: '' })

  const enviar = async (e) => {
    e.preventDefault()
    try {
      const r = await api.reportar(cocheraId, motivo, detalle || null)
      setEstado({ error: '', listo: r.mensaje })
    } catch (err) {
      setEstado({ error: err.message, listo: '' })
    }
  }

  if (estado.listo) return <p className="ayuda">{estado.listo}</p>
  if (!abierto) return <button className="boton boton-texto" onClick={() => setAbierto(true)}>Reportar este anuncio</button>
  return (
    <form className="bloque" onSubmit={enviar}>
      <h2>Reportar anuncio</h2>
      <label className="campo">
        <span>Motivo</span>
        <select value={motivo} onChange={(e) => setMotivo(e.target.value)}>
          {Object.entries(MOTIVOS).map(([v, t]) => <option key={v} value={v}>{t}</option>)}
        </select>
      </label>
      <label className="campo">
        <span>Detalle (opcional)</span>
        <textarea rows={3} maxLength={600} value={detalle} onChange={(e) => setDetalle(e.target.value)} />
      </label>
      <Error>{estado.error}</Error>
      <div className="fila-botones">
        <button className="boton boton-primario">Enviar reporte</button>
        <button type="button" className="boton boton-texto" onClick={() => setAbierto(false)}>Cancelar</button>
      </div>
    </form>
  )
}

const ahoraEnLima = () => ({ fecha: hoyLima(), hora: HORAS_INICIO[Math.min(47, new Date().getHours() * 2 + 1)] })

/** Ficha pública de una cochera: fotos, horarios, precio, mapa y reserva (US-09 a US-18). */
export default function CocheraDetalle() {
  const { id } = useParams()
  const { usuario, esArrendatario, esArrendador, esAdmin } = useAuth()
  const { avisar } = useTiempoReal()
  const navegar = useNavigate()
  const [c, setC] = useState(null)
  const [error, setError] = useState('')
  const [foto, setFoto] = useState(0)
  const [reserva, setReserva] = useState(() => ({ ...ahoraEnLima(), horaFin: '', medio: 'acordado', tarjeta: '' }))
  const [cotizacion, setCotizacion] = useState(null)
  const [tarjetas, setTarjetas] = useState([])
  const [enviando, setEnviando] = useState(false)

  useEffect(() => {
    api.cochera(id).then(setC).catch((e) => setError(e.message))
  }, [id])

  useEffect(() => {
    if (esArrendatario) api.tarjetas().then(setTarjetas).catch(() => {})
  }, [esArrendatario])

  // Cada vez que cambia el horario se cotiza con el servidor (US-18).
  useEffect(() => {
    setCotizacion(null)
    if (!reserva.horaFin || !reserva.fecha) return
    const inicio = isoLima(reserva.fecha, reserva.hora)
    const fin = isoLima(reserva.fecha, reserva.horaFin === '24:00' ? '23:59' : reserva.horaFin)
    let vigente = true
    api.cotizar(id, inicio, fin).then((r) => { if (vigente) setCotizacion(r) }).catch((e) => {
      if (vigente) setCotizacion({ disponible: false, motivo: e.message })
    })
    return () => { vigente = false }
  }, [id, reserva.fecha, reserva.hora, reserva.horaFin])

  const pedirReserva = async (e) => {
    e.preventDefault()
    if (reserva.medio === 'tarjeta' && !reserva.tarjeta) return setError('Elige la tarjeta con la que vas a pagar.')
    setError('')
    setEnviando(true)
    try {
      await api.solicitar(id, isoLima(reserva.fecha, reserva.hora), isoLima(reserva.fecha, reserva.horaFin === '24:00' ? '23:59' : reserva.horaFin),
        reserva.medio, reserva.medio === 'tarjeta' ? Number(reserva.tarjeta) : null)
      avisar('Solicitud enviada. Te avisaremos cuando el dueño la responda.')
      navegar('/reservas')
    } catch (err) {
      setError(err instanceof ErrorApi ? err.message : 'No pudimos enviar la solicitud.')
    } finally {
      setEnviando(false)
    }
  }

  const escribir = async () => {
    try {
      const conversacion = await api.abrirConversacion(c.id)
      navegar(`/chat/${conversacion.id}`)
    } catch (err) {
      setError(err.message)
    }
  }

  if (!c) return error ? <Error>{error}</Error> : <p className="cargando">Cargando…</p>

  const fotos = c.fotos.map(urlFoto)
  const esDueno = usuario?.id === c.arrendador_id
  const horasFin = HORAS_FIN.filter((h) => h > reserva.hora)

  return (
    <div className="ficha">
      <div className="ficha-principal">
        <div className="galeria">
          <img src={urlFoto(fotos[foto])} alt={`${c.titulo}, foto ${foto + 1}`} />
          {fotos.length > 1 && (
            <div className="galeria-miniaturas">
              {fotos.map((f, i) => (
                <button key={f} className={i === foto ? 'activa' : ''} onClick={() => setFoto(i)} aria-label={`Ver foto ${i + 1}`}>
                  <img src={f} alt="" />
                </button>
              ))}
            </div>
          )}
        </div>

        <header className="ficha-cabecera">
          <h1>{c.titulo}</h1>
          <p className="tarjeta-lugar"><IconoUbicacion /> {c.ubicacion.direccion}, {c.ubicacion.distrito}</p>
          {c.ubicacion.referencia && <p className="ayuda">Referencia: {c.ubicacion.referencia}</p>}
          <ul className="rasgos">
            <li>{TIPOS[c.tipo_vehiculo]}</li>
            <li>{c.techada ? 'Techada' : 'Descubierta'}</li>
            <li>{c.largo_m} × {c.ancho_m} m</li>
          </ul>
        </header>

        <section className="bloque">
          <h2>Descripción</h2>
          <p className="texto">{c.descripcion}</p>
        </section>

        <section className="bloque">
          <h2>Precios</h2>
          <p><strong>{soles(c.precio_hora)}</strong> por hora</p>
          {c.tarifas.length > 0 && (
            <ul className="lista-simple">
              {c.tarifas.map((t) => (
                <li key={`${t.hora_inicio}-${t.hora_fin}`}>De {hhmm(t.hora_inicio)} a {hhmm(t.hora_fin)}: <strong>{soles(t.precio_hora)}</strong> por hora</li>
              ))}
            </ul>
          )}
        </section>

        <section className="bloque">
          <h2>Horarios disponibles</h2>
          <ul className="lista-simple">
            {c.disponibilidad.map((d) => (
              <li key={`${d.dia_semana}-${d.hora_inicio}`}>{DIAS[d.dia_semana]}: {hhmm(d.hora_inicio)} a {hhmm(d.hora_fin)}</li>
            ))}
          </ul>
          {c.ocupado.length > 0 && (
            <>
              <h3>Próximos horarios ya reservados</h3>
              <ul className="lista-simple">
                {c.ocupado.map((o) => <li key={o.inicio}>{rango(o.inicio, o.fin)}</li>)}
              </ul>
            </>
          )}
        </section>

        <section className="bloque">
          <h2>Ubicación</h2>
          <MapaPunto punto={{ lat: c.ubicacion.latitud, lng: c.ubicacion.longitud }} alto={240} />
        </section>

        <section className="bloque">
          <h2>Calificaciones</h2>
          {c.total_calificaciones === 0
            ? <p className="ayuda">Esta cochera todavía no tiene calificaciones.</p>
            : <>
                <p><Estrellas valor={c.calificacion} total={c.total_calificaciones} /></p>
                <Resenas resenas={c.resenas} />
              </>}
        </section>

        {usuario && !esDueno && <Reportar cocheraId={c.id} />}
      </div>

      <aside className="ficha-lateral">
        <div className="tarjeta-reserva">
          <p className="precio-grande"><strong>{soles(c.precio_hora)}</strong> <span>por hora</span></p>
          <p className="ayuda">
            Arrendador: <Link to={`/usuarios/${c.arrendador_id}`}>{c.arrendador_nombre}</Link>
            {c.arrendador_verificado && <span className="etiqueta etiqueta-ok">Verificado</span>}
          </p>
          {c.suspendida && (
            <p className="ayuda ayuda-alerta">Anuncio suspendido por moderación: {c.motivo_suspension}</p>
          )}

          {esDueno ? (
            <Link to={`/cocheras/${c.id}/editar`} className="boton boton-secundario boton-ancho">Editar mi cochera</Link>
          ) : !usuario ? (
            <>
              <p>Ingresa para reservar o escribirle al dueño.</p>
              <Link to="/ingresar" state={{ desde: `/cocheras/${c.id}` }} className="boton boton-primario boton-ancho">Ingresar para reservar</Link>
            </>
          ) : esArrendador || esAdmin ? (
            <p className="ayuda">{esAdmin ? 'Las cuentas de administración' : 'Las cuentas de arrendador'} no reservan cocheras.</p>
          ) : (
            <form onSubmit={pedirReserva} noValidate className="formulario-reserva">
              <label className="campo">
                <span>Día</span>
                <input type="date" value={reserva.fecha} min={hoyLima()} max={sumarDias(hoyLima(), 14)}
                  onChange={(e) => setReserva({ ...reserva, fecha: e.target.value, horaFin: '' })} />
              </label>
              <div className="fila-campos">
                <label className="campo">
                  <span>Llegada</span>
                  <select value={reserva.hora} onChange={(e) => setReserva({ ...reserva, hora: e.target.value, horaFin: '' })}>
                    {HORAS_INICIO.map((h) => <option key={h} value={h}>{hhmm(h)}</option>)}
                  </select>
                </label>
                <label className="campo">
                  <span>Salida</span>
                  <select value={reserva.horaFin} onChange={(e) => setReserva({ ...reserva, horaFin: e.target.value })}>
                    <option value="">Elige</option>
                    {horasFin.map((h) => <option key={h} value={h}>{hhmm(h)}</option>)}
                  </select>
                </label>
              </div>

              {cotizacion && (
                cotizacion.disponible ? (
                  <p className="cotizacion">Total <strong>{soles(cotizacion.costo_total)}</strong> · {cotizacion.minutos} min</p>
                ) : (
                  <p className="ayuda ayuda-alerta">{cotizacion.motivo}</p>
                )
              )}

              <fieldset className="medio-pago">
                <legend>¿Cómo pagas?</legend>
                <label className="casilla">
                  <input type="radio" name="medio" value="acordado" checked={reserva.medio === 'acordado'}
                    onChange={() => setReserva({ ...reserva, medio: 'acordado' })} />
                  <span>Acordado con el dueño (efectivo o billetera)</span>
                </label>
                <label className="casilla">
                  <input type="radio" name="medio" value="tarjeta" checked={reserva.medio === 'tarjeta'}
                    onChange={() => setReserva({ ...reserva, medio: 'tarjeta' })} />
                  <span>Tarjeta (pago simulado)</span>
                </label>
                {reserva.medio === 'tarjeta' && (
                  tarjetas.length ? (
                    <select value={reserva.tarjeta} onChange={(e) => setReserva({ ...reserva, tarjeta: e.target.value })} aria-label="Tarjeta">
                      <option value="">Elige una tarjeta</option>
                      {tarjetas.map((t) => <option key={t.id} value={t.id}>{t.marca} •••• {t.ultimos4} · {t.titular}</option>)}
                    </select>
                  ) : (
                    <p className="ayuda">No tienes tarjetas guardadas. <Link to="/reservas">Agrégala en Mis reservas</Link>.</p>
                  )
                )}
              </fieldset>

              <Error>{error}</Error>
              <button className="boton boton-primario boton-ancho" disabled={enviando || !cotizacion?.disponible}>
                {enviando ? 'Enviando…' : 'Solicitar reserva'}
              </button>
              <p className="ayuda">El dueño confirma la solicitud. El horario queda bloqueado solo cuando lo acepta.</p>
            </form>
          )}

          {usuario && !esDueno && (
            <button className="boton boton-texto boton-ancho" onClick={escribir}>Escribirle al dueño</button>
          )}
        </div>
      </aside>
    </div>
  )
}
