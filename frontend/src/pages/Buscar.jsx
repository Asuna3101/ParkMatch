import { useCallback, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, urlFoto } from '../api'
import { Rasgos } from '../components/Comunes'
import { IconoMira, IconoUbicacion } from '../components/Iconos'
import { MapaCocheras } from '../components/Mapa'
import { LIMA, ZONAS, soles } from '../utils'

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

  // Cada vez que el mapa se mueve, se vuelve a buscar en la zona visible.
  const alMover = useCallback(({ lat, lng, radio }) => {
    clearTimeout(espera.current)
    espera.current = setTimeout(async () => {
      const turno = ++pedido.current
      setCargando(true)
      try {
        const resultado = await api.buscar(lat.toFixed(6), lng.toFixed(6), radio.toFixed(2))
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
                  <p className="tarjeta-precio"><strong>{soles(c.precio_hora)}</strong> por hora
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
