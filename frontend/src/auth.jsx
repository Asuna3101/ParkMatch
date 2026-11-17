import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { api, guardarToken, tokenGuardado } from './api'

const Contexto = createContext(null)
export const useAuth = () => useContext(Contexto)

export function ProveedorAuth({ children }) {
  const [usuario, setUsuario] = useState(null)
  const [token, setToken] = useState(tokenGuardado())
  const [cargando, setCargando] = useState(Boolean(tokenGuardado()))

  const salir = useCallback(() => {
    guardarToken(null)
    setToken(null)
    setUsuario(null)
  }, [])

  // Al abrir la aplicación, se recupera la sesión guardada.
  useEffect(() => {
    if (!tokenGuardado()) return
    api.yo().then(setUsuario).catch(salir).finally(() => setCargando(false))
  }, [salir])

  useEffect(() => {
    window.addEventListener('parkmatch:sesion-vencida', salir)
    return () => window.removeEventListener('parkmatch:sesion-vencida', salir)
  }, [salir])

  const entrar = (sesion) => {
    guardarToken(sesion.token)
    setToken(sesion.token)
    setUsuario(sesion.usuario)
    return sesion.usuario
  }

  const valor = {
    usuario, token, cargando, salir,
    iniciarSesion: async (datos) => entrar(await api.login(datos)),
    registrarse: async (datos) => entrar(await api.registro(datos)),
    esArrendador: usuario?.rol === 'arrendador',
    esArrendatario: usuario?.rol === 'arrendatario',
    esAdmin: usuario?.rol === 'administrador',
    actualizarUsuario: (cambios) => setUsuario((u) => ({ ...u, ...cambios })),
  }
  return <Contexto.Provider value={valor}>{children}</Contexto.Provider>
}
