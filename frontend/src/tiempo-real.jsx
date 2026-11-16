import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react'
import { WS_URL, api } from './api'
import { useAuth } from './auth'

const Contexto = createContext(null)
export const useTiempoReal = () => useContext(Contexto)

const AVISOS = {
  solicitada: (c) => `Nueva solicitud de reserva para «${c}».`,
  confirmada: (c) => `Tu reserva en «${c}» fue confirmada.`,
  rechazada: (c) => `Tu solicitud para «${c}» fue rechazada.`,
  cancelada: (c) => `Se canceló una reserva de «${c}».`,
  pago_recibido: (c) => `Se registró el pago de la reserva en «${c}».`,
}

// Cada parte recibe el aviso de lo que hizo la otra.
const AVISA_A = {
  arrendador: ['solicitada', 'cancelada'],
  arrendatario: ['confirmada', 'rechazada', 'pago_recibido'],
}

let siguienteAviso = 0

/** Mantiene el WebSocket abierto mientras hay sesión y reparte los eventos. */
export function ProveedorTiempoReal({ children }) {
  const { token, usuario } = useAuth()
  const socket = useRef(null)
  const oyentes = useRef(new Set())
  const [conectado, setConectado] = useState(false)
  const [sinLeer, setSinLeer] = useState(0)
  const [avisos, setAvisos] = useState([])

  const avisar = useCallback((texto, tono = 'info') => {
    const id = ++siguienteAviso
    setAvisos((a) => [...a, { id, texto, tono }])
    setTimeout(() => setAvisos((a) => a.filter((x) => x.id !== id)), 5000)
  }, [])

  const contarSinLeer = useCallback(() => {
    api.conversaciones().then((cs) => setSinLeer(cs.reduce((n, c) => n + c.sin_leer, 0))).catch(() => {})
  }, [])

  useEffect(() => {
    if (!token || !usuario) {
      setSinLeer(0)
      return
    }
    let cerrado = false
    let reintento

    const conectar = () => {
      const ws = new WebSocket(`${WS_URL}?token=${encodeURIComponent(token)}`)
      socket.current = ws
      ws.onopen = () => setConectado(true)
      ws.onmessage = (e) => {
        const evento = JSON.parse(e.data)
        if (evento.tipo === 'mensaje' && evento.mensaje.emisor_id !== usuario.id) contarSinLeer()
        if (evento.tipo === 'reserva' && AVISA_A[usuario.rol]?.includes(evento.evento)) {
          avisar(AVISOS[evento.evento](evento.cochera))
        }
        oyentes.current.forEach((fn) => fn(evento))
      }
      ws.onclose = () => {
        setConectado(false)
        if (!cerrado) reintento = setTimeout(conectar, 3000)
      }
    }

    conectar()
    contarSinLeer()
    return () => {
      cerrado = true
      clearTimeout(reintento)
      socket.current?.close()
    }
  }, [token, usuario, avisar, contarSinLeer])

  /** Se suscribe a los eventos del servidor. Devuelve la función para cancelar. */
  const escuchar = useCallback((fn) => {
    oyentes.current.add(fn)
    return () => oyentes.current.delete(fn)
  }, [])

  /** Envía por WebSocket. Devuelve false si no hay conexión, para usar HTTP de respaldo. */
  const enviar = useCallback((datos) => {
    if (socket.current?.readyState !== WebSocket.OPEN) return false
    socket.current.send(JSON.stringify(datos))
    return true
  }, [])

  return (
    <Contexto.Provider value={{ conectado, sinLeer, contarSinLeer, escuchar, enviar, avisar }}>
      {children}
      <div className="avisos" role="status" aria-live="polite">
        {avisos.map((a) => <div key={a.id} className={`aviso aviso-${a.tono}`}>{a.texto}</div>)}
      </div>
    </Contexto.Provider>
  )
}
