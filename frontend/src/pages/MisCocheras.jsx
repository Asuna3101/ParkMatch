import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, urlFoto } from '../api'
import { Error, Vacio } from '../components/Comunes'
import { useTiempoReal } from '../tiempo-real'
import { TIPOS, soles } from '../utils'

/** Lista de las cocheras del arrendador, con su estado y accesos rápidos (US-05, US-08). */
export default function MisCocheras() {
  const { avisar } = useTiempoReal()
  const [cocheras, setCocheras] = useState(null)
  const [error, setError] = useState('')
  const [ocupada, setOcupada] = useState(null)

  const cargar = () => api.misCocheras().then(setCocheras).catch((e) => setError(e.message))
  useEffect(() => { cargar() }, [])

  const alternar = async (c) => {
    setOcupada(c.id)
    try {
      await api.cambiarEstado(c.id, !c.activa)
      avisar(c.activa ? 'Cochera pausada.' : 'Cochera activada.')
      await cargar()
    } catch (e) {
      setError(e.message)
    } finally {
      setOcupada(null)
    }
  }

  if (!cocheras) return error ? <Error>{error}</Error> : <p className="cargando">Cargando…</p>

  return (
    <div className="pagina">
      <div className="encabezado-pagina">
        <div>
          <h1>Mis cocheras</h1>
          <p className="bajada-pagina">{cocheras.length} {cocheras.length === 1 ? 'cochera publicada' : 'cocheras publicadas'}</p>
        </div>
        <Link to="/publicar" className="boton boton-primario">Publicar cochera</Link>
      </div>
      <Error>{error}</Error>

      {cocheras.length === 0 ? (
        <Vacio titulo="Todavía no publicaste cocheras">
          <p>Publica tu espacio con fotos, precio y horarios. Te avisaremos cuando alguien lo solicite.</p>
          <Link to="/publicar" className="boton boton-primario">Publicar mi primera cochera</Link>
        </Vacio>
      ) : (
        <ul className="grilla-cocheras">
          {cocheras.map((c) => (
            <li key={c.id} className="tarjeta-propia">
              <img src={urlFoto(c.foto)} alt="" />
              <div className="tarjeta-cuerpo">
                <h2>{c.titulo}</h2>
                <p className="tarjeta-lugar">{c.direccion}, {c.distrito}</p>
                <p className="tarjeta-precio"><strong>{soles(c.precio_hora)}</strong> por hora · {TIPOS[c.tipo_vehiculo]}</p>
                <p>
                  <span className={`etiqueta etiqueta-${c.suspendida ? 'error' : c.activa ? 'ok' : 'neutro'}`}>
                    {c.suspendida ? 'Suspendida' : c.activa ? 'Recibiendo reservas' : 'En pausa'}
                  </span>
                </p>
                <div className="acciones-tarjeta">
                  <Link to={`/cocheras/${c.id}/editar`} className="boton boton-secundario">Editar</Link>
                  <button className="boton boton-texto" onClick={() => alternar(c)} disabled={ocupada === c.id || c.suspendida}>
                    {c.activa ? 'Pausar' : 'Activar'}
                  </button>
                  <Link to={`/cocheras/${c.id}`} className="boton boton-texto">Ver anuncio</Link>
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
