import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { api } from '../api'
import { Error } from '../components/Comunes'

/** Pide el enlace para crear una nueva contraseña (US-03). */
export function Recuperar() {
  const [correo, setCorreo] = useState('')
  const [respuesta, setRespuesta] = useState(null)
  const [error, setError] = useState('')
  const [enviando, setEnviando] = useState(false)

  const enviar = async (e) => {
    e.preventDefault()
    setError('')
    setEnviando(true)
    try {
      setRespuesta(await api.recuperar(correo))
    } catch (err) {
      setError(err.message)
    } finally {
      setEnviando(false)
    }
  }

  return (
    <div className="tarjeta-formulario">
      <h1>Recuperar contraseña</h1>
      {respuesta ? (
        <>
          <p>{respuesta.mensaje}</p>
          {respuesta.enlace_demo && (
            <p className="ayuda">
              Modo demostración: como no hay servidor de correo,{' '}
              <a href={respuesta.enlace_demo}>usa este enlace</a>.
            </p>
          )}
        </>
      ) : (
        <form onSubmit={enviar} noValidate>
          <p className="ayuda">Escribe el correo de tu cuenta y te enviaremos un enlace para crear una nueva contraseña.</p>
          <label className="campo">
            <span>Correo</span>
            <input type="email" autoComplete="email" required value={correo}
              onChange={(e) => setCorreo(e.target.value)} placeholder="nombre@correo.com" />
          </label>
          <Error>{error}</Error>
          <button className="boton boton-primario boton-ancho" disabled={enviando || !correo}>
            {enviando ? 'Enviando…' : 'Enviar enlace'}
          </button>
        </form>
      )}
      <p className="pie-formulario"><Link to="/ingresar">Volver a ingresar</Link></p>
    </div>
  )
}

/** Crea la nueva contraseña con el enlace del correo. */
export function Restablecer() {
  const [params] = useSearchParams()
  const navegar = useNavigate()
  const [contrasena, setContrasena] = useState('')
  const [repetida, setRepetida] = useState('')
  const [error, setError] = useState('')
  const [listo, setListo] = useState(false)

  const enviar = async (e) => {
    e.preventDefault()
    if (contrasena !== repetida) return setError('Las contraseñas no coinciden.')
    setError('')
    try {
      await api.restablecer(params.get('token') || '', contrasena)
      setListo(true)
      setTimeout(() => navegar('/ingresar'), 2500)
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <div className="tarjeta-formulario">
      <h1>Nueva contraseña</h1>
      {listo ? (
        <p>Listo, ya puedes ingresar con tu nueva contraseña.</p>
      ) : (
        <form onSubmit={enviar} noValidate>
          <label className="campo">
            <span>Nueva contraseña <em>(mínimo 8 caracteres, con letras y números)</em></span>
            <input type="password" autoComplete="new-password" value={contrasena} onChange={(e) => setContrasena(e.target.value)} />
          </label>
          <label className="campo">
            <span>Repítela</span>
            <input type="password" autoComplete="new-password" value={repetida} onChange={(e) => setRepetida(e.target.value)} />
          </label>
          <Error>{error}</Error>
          <button className="boton boton-primario boton-ancho" disabled={!contrasena || !repetida}>Guardar contraseña</button>
        </form>
      )}
    </div>
  )
}
