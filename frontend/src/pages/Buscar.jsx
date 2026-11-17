import { useCallback, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, urlFoto } from '../api'
import { Estrellas, Rasgos } from '../components/Comunes'
import { IconoMira, IconoUbicacion } from '../components/Iconos'
import { MapaCocheras } from '../components/Mapa'
import { HORAS_FIN, HORAS_INICIO, LIMA, ZONAS, hhmm, hoyLima, isoLima, soles, sumarDias } from '../utils'

const SIN_FILTROS = { precio_max: '', tipo_vehiculo: '', techada: '', fecha: '', hora: '', horaFin: '' }

/** Mapa de cocheras disponibles alrededor de una ubicación (US-09). */
export default function Buscar() {
  const [centro, setCentro] = useState({ ...LIMA, zoom: 13 })
  const [cocheras, setCocheras] = useState([])
  const [seleccionada, setSeleccionada] = useState(null)
  const [miUbicacion, setMiUbicacion] = useState(null)
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState('')
  const [direccion, setDireccion] = useState('')
  const [aviso, setAviso] = useState('')
  const pedido = useRef(0)
  const espera = useRef()
  const tarjetas = useRef({})
  const [filtros, setFiltros] = useState(SIN_FILTROS)
  const [verFiltros, setVerFiltros] = useState(false)
  const zona = useRef(null)
  const filtrosRef = useRef(SIN_FILTROS)

  // Los filtros de horario solo se envían cuando están completos.
  const parametros = (f) => {
    const p = { precio_max: f.precio_max, tipo_vehiculo: f.tipo_vehiculo, techada: f.techada }
    if (f.fecha && f.hora && f.horaFin) {
      p.inicio = isoLima(f.fecha, f.hora)
      p.fin = isoLima(f.fecha, f.horaFin)
    }
    return p
  }

  // Cada vez que el mapa se mueve, se vuelve a buscar en la zona visible.
  const alMover = useCallback(({ lat, lng, radio }) => {
    zona.current = { lat, lng, radio }
    clearTimeout(espera.current)
    espera.current = setTimeout(async () => {
      const turno = ++pedido.current
      setCargando(true)
      try {
        const resultado = await api.buscar(lat.toFixed(6), lng.toFixed(6), radio.toFixed(2), parametros(filtrosRef.current))
        if (turno !== pedido.current) return // llegó una respuesta más nueva
        setCocheras(resultado)
        setError('')
      } catch (err) {
        if (turno === pedido.current) setError(err.message)
      } finally {
        if (turno === pedido.current) setCargando(false)
      }
    }, 250)
  }, [])

  const cambiarFiltro = (cambios) => {
    const nuevos = { ...filtros, ...cambios }
    setFiltros(nuevos)
    filtrosRef.current = nuevos
    if (zona.current) alMover(zona.current)
  }
  const activos = Object.values(filtros).some(Boolean)

  const irA = (lat, lng, zoom = 15) => setCentro({ lat, lng, zoom, sello: Date.now() })

  const usarMiUbicacion = () => {
    setAviso('')
    if (!navigator.geolocation) return setAviso('Tu navegador no permite obtener la ubicación.')
    navigator.geolocation.getCurrentPosition(
      ({ coords }) => {
        setMiUbicacion({ lat: coords.latitude, lng: coords.longitude })
        irA(coords.latitude, coords.longitude)
      },
      () => setAviso('No pudimos obtener tu ubicación. Revisa el permiso del navegador o elige una zona.'),
      { timeout: 8000 },
    )
  }

  const buscarDireccion = async (e) => {
    e.preventDefault()
    if (!direccion.trim()) return
    setAviso('')
    try {
      const url = `https://nominatim.openstreetmap.org/search?format=json&limit=1&countrycodes=pe&q=${encodeURIComponent(direccion + ', Lima')}`
      const [lugar] = await (await fetch(url)).json()
      if (!lugar) return setAviso('No encontramos esa dirección. Prueba con la avenida y el distrito.')
      irA(Number(lugar.lat), Number(lugar.lon))
    } catch {
      setAviso('No pudimos buscar la dirección. Mueve el mapa o elige una zona.')
    }
  }

  const seleccionar = useCallback((id) => {
    setSeleccionada(id)
    tarjetas.current[id]?.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' })
  }, [])

  useEffect(() => () => clearTimeout(espera.current), [])

  return (
    <div className="buscar">
      <aside className="buscar-panel">
        <form className="buscador" onSubmit={buscarDireccion} role="search">
          <input id="direccion" value={direccion} onChange={(e) => setDireccion(e.target.value)}
            placeholder="¿A dónde vas? Ej.: Av. Larco, Miraflores" aria-label="Dirección de destino" />
          <button className="boton boton-primario">Buscar</button>
        </form>

        <div className="zonas">
          <button type="button" className="chip chip-accion" onClick={usarMiUbicacion}>
            <IconoMira /> Mi ubicación
          </button>
          {ZONAS.map((z) => (
            <button key={z.nombre} type="button" className="chip" onClick={() => irA(z.lat, z.lng)}>{z.nombre}</button>
          ))}
        </div>
        {aviso && <p className="ayuda ayuda-alerta">{aviso}</p>}

        <div className="fila-botones">
          <button type="button" className="boton boton-texto filtros-alternar" aria-expanded={verFiltros}
            onClick={() => setVerFiltros(!verFiltros)}>
            {verFiltros ? 'Ocultar filtros' : 'Filtros'}{activos ? ' (activos)' : ''}
          </button>
          {activos && <button type="button" className="boton boton-texto filtros-alternar"
            onClick={() => cambiarFiltro(SIN_FILTROS)}>Quitar filtros</button>}
        </div>
        {verFiltros && (
          <div className="filtros">
            <label className="campo">
              <span>Precio máx. por hora</span>
              <input type="number" min="1" step="0.5" inputMode="decimal" value={filtros.precio_max}
                onChange={(e) => cambiarFiltro({ precio_max: e.target.value })} placeholder="S/" />
            </label>
            <label className="campo">
              <span>Mi vehículo</span>
              <select value={filtros.tipo_vehiculo} onChange={(e) => cambiarFiltro({ tipo_vehiculo: e.target.value })}>
                <option value="">Cualquiera</option>
                <option value="moto">Moto</option>
                <option value="auto">Auto</option>
                <option value="camioneta">Camioneta</option>
              </select>
            </label>
            <label className="campo">
              <span>Techo</span>
              <select value={filtros.techada} onChange={(e) => cambiarFiltro({ techada: e.target.value })}>
                <option value="">Indistinto</option>
                <option value="true">Techada</option>
                <option value="false">Descubierta</option>
              </select>
            </label>
            <label className="campo">
              <span>Día</span>
              <input type="date" value={filtros.fecha} min={hoyLima()} max={sumarDias(hoyLima(), 14)}
                onChange={(e) => cambiarFiltro({ fecha: e.target.value })} />
            </label>
            <label className="campo">
              <span>Llegada</span>
              <select value={filtros.hora} onChange={(e) => cambiarFiltro({ hora: e.target.value, horaFin: '' })}>
                <option value="">—</option>
                {HORAS_INICIO.map((h) => <option key={h} value={h}>{hhmm(h)}</option>)}
              </select>
            </label>
            <label className="campo">
              <span>Salida</span>
              <select value={filtros.horaFin} disabled={!filtros.hora}
                onChange={(e) => cambiarFiltro({ horaFin: e.target.value })}>
                <option value="">—</option>
                {HORAS_FIN.filter((h) => h > filtros.hora).map((h) => <option key={h} value={h}>{hhmm(h)}</option>)}
              </select>
            </label>
          </div>
        )}

        <p className="resultado-conteo" aria-live="polite">
          {error ? <span className="mensaje-error">{error}</span>
            : cargando && !cocheras.length ? 'Buscando cocheras…'
            : cocheras.length === 0 ? 'No hay cocheras en esta zona. Aleja el mapa o prueba otra zona.'
            : `${cocheras.length} ${cocheras.length === 1 ? 'cochera' : 'cocheras'} en esta zona`}
        </p>

        <ul className="lista-cocheras">
          {cocheras.map((c) => (
            <li key={c.id} ref={(el) => { tarjetas.current[c.id] = el }}>
              <Link to={`/cocheras/${c.id}`} className={`tarjeta-cochera${c.id === seleccionada ? ' activa' : ''}`}
                onMouseEnter={() => setSeleccionada(c.id)} onFocus={() => setSeleccionada(c.id)}>
                <img src={urlFoto(c.foto)} alt="" loading="lazy" />
                <div className="tarjeta-cuerpo">
                  <h2>{c.titulo}</h2>
                  <p className="tarjeta-lugar"><IconoUbicacion /> {c.direccion}, {c.distrito}</p>
                  <Rasgos cochera={c} />
                  {c.calificacion != null && <p><Estrellas valor={c.calificacion} total={c.total_calificaciones} /></p>}
                  <p className="tarjeta-precio"><strong>{soles(c.precio_hora)}</strong> por hora
                    {c.costo_horario != null && <span> · {soles(c.costo_horario)} en tu horario</span>}
                    {c.distancia_km != null && <span> · a {c.distancia_km < 1 ? `${Math.round(c.distancia_km * 1000)} m` : `${c.distancia_km.toFixed(1)} km`}</span>}
                  </p>
                </div>
              </Link>
            </li>
          ))}
        </ul>
      </aside>

      <div className="buscar-mapa">
        <MapaCocheras centro={centro} cocheras={cocheras} seleccionada={seleccionada}
          alSeleccionar={seleccionar} alMover={alMover} miUbicacion={miUbicacion} />
      </div>
    </div>
  )
}
