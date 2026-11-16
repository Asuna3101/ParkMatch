import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api } from '../api'
import { useAuth } from '../auth'
import { Error, Vacio } from '../components/Comunes'
import { IconoEnviar } from '../components/Iconos'
import { useTiempoReal } from '../tiempo-real'
import { hora, iniciales } from '../utils'

/** Mensajes entre arrendador y arrendatario de una cochera (US-13). Tiempo real por WebSocket. */
export default function Chat() {
  const { id } = useParams()
  const navegar = useNavigate()
  const { usuario } = useAuth()
  const { escuchar, enviar, contarSinLeer } = useTiempoReal()
  const [conversaciones, setConversaciones] = useState(null)
  const [mensajes, setMensajes] = useState([])
  const [texto, setTexto] = useState('')
  const [error, setError] = useState('')
  const fin = useRef(null)
  const activa = conversaciones?.find((c) => String(c.id) === String(id))

  const cargarLista = () => api.conversaciones().then(setConversaciones).catch((e) => setError(e.message))

  useEffect(() => { cargarLista() }, []) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!id) return
    setMensajes([])
    api.mensajes(id).then((lista) => { setMensajes(lista); contarSinLeer() }).catch((e) => setError(e.message))
  }, [id]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => escuchar((evento) => {
    if (evento.tipo !== 'mensaje') return
    cargarLista()
    if (String(evento.mensaje.conversacion_id) === String(id)) {
      setMensajes((actuales) => actuales.some((m) => m.id === evento.mensaje.id) ? actuales : [...actuales, evento.mensaje])
    }
  }), [escuchar, id]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { fin.current?.scrollIntoView({ behavior: 'smooth' }) }, [mensajes])

  const enviarMensaje = async (e) => {
    e.preventDefault()
    const limpio = texto.trim()
    if (!limpio || !activa) return
    setTexto('')
    setError('')
    // Por WebSocket si está conectado; si no, por HTTP.
    if (!enviar({ tipo: 'mensaje', conversacion_id: activa.id, texto: limpio })) {
      try {
        const nuevo = await api.enviarMensaje(activa.id, limpio)
        setMensajes((actuales) => [...actuales, nuevo])
      } catch (err) {
        setError(err.message)
        setTexto(limpio)
      }
    }
  }

  if (!conversaciones) return error ? <Error>{error}</Error> : <p className="cargando">Cargando…</p>

  return (
    <div className={`chat${id ? ' chat-abierto' : ''}`}>
      <aside className="chat-lista">
        <h1>Mensajes</h1>
        {conversaciones.length === 0 ? (
          <Vacio titulo="Sin conversaciones">
            <p>Escribe al dueño desde la ficha de una cochera para empezar.</p>
          </Vacio>
        ) : (
          <ul>
            {conversaciones.map((c) => (
              <li key={c.id}>
                <Link to={`/chat/${c.id}`} className={`fila-chat${String(c.id) === String(id) ? ' activa' : ''}`}>
                  <span className="avatar">{iniciales(c.otro_nombre)}</span>
                  <span className="fila-chat-texto">
                    <strong>{c.otro_nombre}</strong>
                    <small>{c.cochera_titulo}</small>
                    <span className="ultimo">{c.ultimo_mensaje || 'Sin mensajes todavía'}</span>
                  </span>
                  {c.sin_leer > 0 && <span className="contador">{c.sin_leer}</span>}
                </Link>
              </li>
            ))}
          </ul>
        )}
      </aside>

      <section className="chat-hilo">
        {!activa ? (
          <div className="chat-vacio"><p>Elige una conversación para leer y responder.</p></div>
        ) : (
          <>
            <header className="chat-cabecera">
              <button className="boton boton-texto chat-volver" onClick={() => navegar('/chat')}>← Volver</button>
              <div>
                <strong>{activa.otro_nombre}</strong>
                <small>{activa.cochera_titulo}</small>
              </div>
            </header>
            <div className="chat-mensajes">
              {mensajes.map((m) => (
                <div key={m.id} className={`burbuja${m.emisor_id === usuario.id ? ' propia' : ''}`}>
                  <p>{m.texto}</p>
                  <small>{hora(m.enviado_en)}</small>
                </div>
              ))}
              <div ref={fin} />
            </div>
            <Error>{error}</Error>
            <form className="chat-enviar" onSubmit={enviarMensaje}>
              <input value={texto} onChange={(e) => setTexto(e.target.value)} placeholder="Escribe un mensaje" maxLength={1000} aria-label="Mensaje" />
              <button className="boton boton-primario boton-icono" aria-label="Enviar" disabled={!texto.trim()}><IconoEnviar /></button>
            </form>
          </>
        )}
      </section>
    </div>
  )
}
