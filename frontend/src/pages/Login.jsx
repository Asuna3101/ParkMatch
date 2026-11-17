import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth'
import { Error } from '../components/Comunes'

export default function Login() {
  const { iniciarSesion } = useAuth()
  const navegar = useNavigate()
  const { state } = useLocation()
  const [correo, setCorreo] = useState('')
  const [contrasena, setContrasena] = useState('')
  const [error, setError] = useState('')
  const [enviando, setEnviando] = useState(false)

  const enviar = async (e) => {
    e.preventDefault()
    setError('')
    setEnviando(true)
    try {
      await iniciarSesion({ correo, contrasena })
      navegar(state?.desde ?? '/', { replace: true })
    } catch (err) {
      setError(err.message)
    } finally {
      setEnviando(false)
    }
  }

  return (
    <div className="tarjeta-formulario">
      <h1>Ingresar</h1>
      <form onSubmit={enviar} noValidate>
        <label className="campo">
          <span>Correo</span>
          <input id="correo" type="email" autoComplete="email" required value={correo}
            onChange={(e) => setCorreo(e.target.value)} placeholder="nombre@correo.com" />
        </label>
        <label className="campo">
          <span>Contraseña</span>
          <input id="contrasena" type="password" autoComplete="current-password" required value={contrasena}
            onChange={(e) => setContrasena(e.target.value)} />
        </label>
        <Error>{error}</Error>
        <button className="boton boton-primario boton-ancho" disabled={enviando || !correo || !contrasena}>
          {enviando ? 'Ingresando…' : 'Ingresar'}
        </button>
      </form>
      <p className="pie-formulario"><Link to="/recuperar">¿Olvidaste tu contraseña?</Link></p>
      <p className="pie-formulario">¿Aún no tienes cuenta? <Link to="/registro">Créala aquí</Link></p>
    </div>
  )
}
