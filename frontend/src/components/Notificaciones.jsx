import { useCallback, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import { useTiempoReal } from '../tiempo-real'
import { fechaHora } from '../utils'
import { IconoCampana } from './Iconos'

/** Campana con la bandeja de notificaciones dentro de la aplicación (US-15). */
export default function Notificaciones() {
  const { escuchar, avisar } = useTiempoReal()
  const [bandeja, setBandeja] = useState({ sin_leer: 0, notificaciones: [] })
  const [abierta, setAbierta] = useState(false)
  const caja = useRef(null)

  const cargar = useCallback(() => api.notificaciones().then(setBandeja).catch(() => {}), [])

  useEffect(() => { cargar() }, [cargar])

  // Las notificaciones nuevas llegan por WebSocket.
  useEffect(() => escuchar((e) => {
    if (e.tipo !== 'notificacion') return
    setBandeja((b) => ({ sin_leer: b.sin_leer + 1, notificaciones: [e.notificacion, ...b.notificaciones].slice(0, 50) }))
    avisar(e.notificacion.titulo)
  }), [escuchar, avisar])

  useEffect(() => {
    if (!abierta) return
    const fuera = (e) => { if (!caja.current?.contains(e.target)) setAbierta(false) }
    const escape = (e) => { if (e.key === 'Escape') setAbierta(false) }
    document.addEventListener('mousedown', fuera)
    document.addEventListener('keydown', escape)
    return () => {
      document.removeEventListener('mousedown', fuera)
      document.removeEventListener('keydown', escape)
    }
  }, [abierta])

  const alternar = () => {
    const abrir = !abierta
    setAbierta(abrir)
    if (abrir && bandeja.sin_leer > 0) {
      api.marcarLeidas().then(() => setTimeout(cargar, 1500)).catch(() => {})
    }
  }

  return (
    <div className="campana" ref={caja}>
      <button className="campana-boton" onClick={alternar} aria-expanded={abierta}
        aria-label={`Notificaciones${bandeja.sin_leer ? `, ${bandeja.sin_leer} sin leer` : ''}`}>
        <IconoCampana />
        {bandeja.sin_leer > 0 && <span className="contador">{bandeja.sin_leer}</span>}
      </button>
      {abierta && (
        <div className="campana-panel">
          <header><h2>Notificaciones</h2></header>
          {bandeja.notificaciones.length === 0 ? (
            <p className="vacio-chico">No tienes notificaciones.</p>
          ) : (
            <ul>
              {bandeja.notificaciones.map((n) => {
                const contenido = (
                  <>
                    <p><strong>{n.titulo}</strong></p>
                    <p>{n.texto}</p>
                    <p className="ayuda">{fechaHora(n.creado_en)}</p>
                  </>
                )
                return (
                  <li key={n.id} className={n.leida ? '' : 'nueva'}>
                    {n.enlace ? <Link to={n.enlace} onClick={() => setAbierta(false)}>{contenido}</Link> : <div>{contenido}</div>}
                  </li>
                )
              })}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}
