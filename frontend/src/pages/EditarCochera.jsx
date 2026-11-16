import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api, ErrorApi } from '../api'
import { Error } from '../components/Comunes'
import DatosCochera, { datosParaApi, datosVacios, errorDatos } from '../components/DatosCochera'
import { EditorCalendario, EditorTarifas, calendarioDesdeApi, calendarioParaApi, errorCalendario, errorTarifas, tarifasDesdeApi, tarifasParaApi } from '../components/Editores'
import { useTiempoReal } from '../tiempo-real'

const SECCIONES = [
  { id: 'datos', texto: 'Datos' },
  { id: 'precios', texto: 'Precios' },
  { id: 'horarios', texto: 'Horarios' },
]

/** Editar una cochera publicada: datos, precios y horarios (US-05 a US-07, requisito 7). */
export default function EditarCochera() {
  const { id } = useParams()
  const { avisar } = useTiempoReal()
  const [cochera, setCochera] = useState(null)
  const [seccion, setSeccion] = useState('datos')
  const [datos, setDatos] = useState(datosVacios)
  const [precio, setPrecio] = useState('')
  const [tarifas, setTarifas] = useState([])
  const [calendario, setCalendario] = useState([])
  const [error, setError] = useState('')
  const [cargando, setCargando] = useState(true)
  const [guardando, setGuardando] = useState(false)

  useEffect(() => {
    api.cochera(id).then((c) => {
      setCochera(c)
      setDatos({
        titulo: c.titulo, descripcion: c.descripcion, tipo_vehiculo: c.tipo_vehiculo,
        largo_m: String(c.largo_m), ancho_m: String(c.ancho_m), techada: c.techada,
        direccion: c.ubicacion.direccion, distrito: c.ubicacion.distrito, referencia: c.ubicacion.referencia ?? '',
        latitud: String(c.ubicacion.latitud), longitud: String(c.ubicacion.longitud),
      })
      setPrecio(String(c.precio_hora))
      setTarifas(tarifasDesdeApi(c.tarifas))
      setCalendario(calendarioDesdeApi(c.disponibilidad))
    }).catch((err) => setError(err.message)).finally(() => setCargando(false))
  }, [id])

  const ejecutar = async (accion, mensaje) => {
    setError('')
    setGuardando(true)
    try {
      const actualizada = await accion()
      setCochera(actualizada)
      avisar(mensaje)
    } catch (err) {
      setError(err instanceof ErrorApi ? err.message : 'No pudimos guardar los cambios.')
    } finally {
      setGuardando(false)
    }
  }

  const guardarDatos = (e) => {
    e.preventDefault()
    const problema = errorDatos(datos)
    if (problema) return setError(problema)
    ejecutar(() => api.editarCochera(id, datosParaApi(datos)), 'Datos guardados.')
  }

  const guardarPrecios = (e) => {
    e.preventDefault()
    const problema = errorTarifas(precio, tarifas)
    if (problema) return setError(problema)
    ejecutar(() => api.guardarTarifas(id, { precio_hora: Number(precio), tarifas: tarifasParaApi(tarifas) }),
      'Precios actualizados. Aplican desde ahora.')
  }

  const guardarHorarios = (e) => {
    e.preventDefault()
    const problema = errorCalendario(calendario)
    if (problema) return setError(problema)
    ejecutar(() => api.guardarCalendario(id, calendarioParaApi(calendario)), 'Horarios guardados.')
  }

  const cambiarEstado = () => ejecutar(() => api.cambiarEstado(id, !cochera.activa).then(() => api.cochera(id)),
    cochera.activa ? 'La cochera está en pausa.' : 'La cochera está activa de nuevo.')

  if (cargando) return <p className="cargando">Cargando…</p>
  if (!cochera) return <Error>{error || 'No encontramos esa cochera.'}</Error>

  return (
    <div className="pagina-formulario">
      <Link to="/mis-cocheras" className="volver">← Mis cocheras</Link>
      <div className="encabezado-pagina">
        <h1>{cochera.titulo}</h1>
        <button className="boton boton-secundario" onClick={cambiarEstado} disabled={guardando || cochera.suspendida}>
          {cochera.activa ? 'Pausar reservas' : 'Activar reservas'}
        </button>
      </div>
      {cochera.suspendida && <p className="aviso-bloque">Esta cochera fue suspendida por la administración y no aparece en las búsquedas.</p>}

      <nav className="pestanas" aria-label="Secciones">
        {SECCIONES.map((s) => (
          <button key={s.id} className={`pestana${seccion === s.id ? ' activa' : ''}`} onClick={() => setSeccion(s.id)}>{s.texto}</button>
        ))}
      </nav>

      {seccion === 'datos' && (
        <form onSubmit={guardarDatos} noValidate className="formulario-amplio">
          <DatosCochera valor={datos} alCambiar={setDatos} />
          <Error>{error}</Error>
          <button className="boton boton-primario" disabled={guardando}>Guardar datos</button>
        </form>
      )}
      {seccion === 'precios' && (
        <form onSubmit={guardarPrecios} noValidate className="formulario-amplio">
          <EditorTarifas precio={precio} tarifas={tarifas} alCambiarPrecio={setPrecio} alCambiarTarifas={setTarifas} />
          <Error>{error}</Error>
          <button className="boton boton-primario" disabled={guardando}>Guardar precios</button>
        </form>
      )}
      {seccion === 'horarios' && (
        <form onSubmit={guardarHorarios} noValidate className="formulario-amplio">
          <p className="ayuda">Los cambios aplican a las próximas reservas. Las ya confirmadas no se mueven.</p>
          <EditorCalendario valor={calendario} alCambiar={setCalendario} />
          <Error>{error}</Error>
          <button className="boton boton-primario" disabled={guardando}>Guardar horarios</button>
        </form>
      )}
    </div>
  )
}
