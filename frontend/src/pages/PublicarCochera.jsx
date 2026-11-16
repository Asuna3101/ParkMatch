import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, ErrorApi } from '../api'
import { Error } from '../components/Comunes'
import DatosCochera, { datosParaApi, datosVacios, errorDatos } from '../components/DatosCochera'
import { EditorCalendario, EditorTarifas, calendarioInicial, calendarioParaApi, errorCalendario, errorTarifas, tarifasParaApi } from '../components/Editores'
import { useTiempoReal } from '../tiempo-real'

const MIN_FOTOS = 3
const MAX_FOTOS = 8
const MAX_MB = 5
const TIPOS_FOTO = ['image/jpeg', 'image/png', 'image/webp']

/** Publicar una cochera nueva (US-05, US-06, US-07). */
export default function PublicarCochera() {
  const navegar = useNavigate()
  const { avisar } = useTiempoReal()
  const [datos, setDatos] = useState(datosVacios)
  const [precio, setPrecio] = useState('')
  const [tarifas, setTarifas] = useState([])
  const [calendario, setCalendario] = useState(calendarioInicial)
  const [fotos, setFotos] = useState([])
  const [error, setError] = useState('')
  const [enviando, setEnviando] = useState(false)

  const elegirFotos = (e) => {
    const elegidas = Array.from(e.target.files || [])
    const valida = elegidas.find((f) => !TIPOS_FOTO.includes(f.type))
    if (valida) return setError(`«${valida.name}» no es una imagen válida. Usa JPG, PNG o WebP.`)
    const grande = elegidas.find((f) => f.size > MAX_MB * 1024 * 1024)
    if (grande) return setError(`«${grande.name}» pesa más de ${MAX_MB} MB.`)
    setError('')
    setFotos((actuales) => [...actuales, ...elegidas].slice(0, MAX_FOTOS))
    e.target.value = ''
  }

  const quitarFoto = (i) => setFotos((actuales) => actuales.filter((_, n) => n !== i))

  const publicar = async (e) => {
    e.preventDefault()
    const problema = errorDatos(datos) || errorTarifas(precio, tarifas) || errorCalendario(calendario)
      || (fotos.length < MIN_FOTOS ? `Sube al menos ${MIN_FOTOS} fotos de la cochera.` : null)
    if (problema) return setError(problema)

    setError('')
    setEnviando(true)
    try {
      await api.publicar({
        ...datosParaApi(datos),
        precio_hora: Number(precio),
        tarifas: tarifasParaApi(tarifas),
        disponibilidad: calendarioParaApi(calendario),
      }, fotos)
      avisar('Tu cochera ya está publicada.')
      navegar('/mis-cocheras', { replace: true })
    } catch (err) {
      setError(err instanceof ErrorApi ? err.message : 'No pudimos publicar la cochera.')
    } finally {
      setEnviando(false)
    }
  }

  return (
    <div className="pagina-formulario">
      <h1>Publicar mi cochera</h1>
      <p className="bajada-pagina">Completa los datos, sube fotos y define precios y horarios. Podrás editarlo después.</p>

      <form onSubmit={publicar} noValidate className="formulario-amplio">
        <section className="bloque">
          <h2>1. Datos de la cochera</h2>
          <DatosCochera valor={datos} alCambiar={setDatos} />
        </section>

        <section className="bloque">
          <h2>2. Fotos</h2>
          <p className="ayuda">Sube entre {MIN_FOTOS} y {MAX_FOTOS} fotos (JPG, PNG o WebP, hasta {MAX_MB} MB cada una).</p>
          <div className="fotos-grilla">
            {fotos.map((f, i) => (
              <div key={`${f.name}-${i}`} className="foto-miniatura">
                <img src={URL.createObjectURL(f)} alt={`Foto ${i + 1}`} />
                <button type="button" className="boton boton-texto boton-peligro" onClick={() => quitarFoto(i)}>Quitar</button>
              </div>
            ))}
            {fotos.length < MAX_FOTOS && (
              <label className="subir-foto">
                <input type="file" accept={TIPOS_FOTO.join(',')} multiple onChange={elegirFotos} />
                <span>+ Agregar fotos</span>
                <small>{fotos.length} de {MAX_FOTOS}</small>
              </label>
            )}
          </div>
        </section>

        <section className="bloque">
          <h2>3. Precio</h2>
          <EditorTarifas precio={precio} tarifas={tarifas} alCambiarPrecio={setPrecio} alCambiarTarifas={setTarifas} />
        </section>

        <section className="bloque">
          <h2>4. Horarios disponibles</h2>
          <p className="ayuda">Marca los días y las horas en que la cochera está libre para alquilar.</p>
          <EditorCalendario valor={calendario} alCambiar={setCalendario} />
        </section>

        <Error>{error}</Error>
        <div className="acciones-formulario">
          <button type="button" className="boton boton-texto" onClick={() => navegar(-1)}>Cancelar</button>
          <button className="boton boton-primario boton-grande" disabled={enviando}>
            {enviando ? 'Publicando…' : 'Publicar cochera'}
          </button>
        </div>
      </form>
    </div>
  )
}
