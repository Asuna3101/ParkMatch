import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { useAuth } from '../auth'
import { Error } from '../components/Comunes'

const ROLES = [
  { valor: 'arrendatario', titulo: 'Busco cochera', detalle: 'Quiero encontrar y reservar un espacio.' },
  { valor: 'arrendador', titulo: 'Tengo una cochera', detalle: 'Quiero publicar mi espacio y alquilarlo.' },
]

export default function Registro() {
  const { registrarse } = useAuth()
  const navegar = useNavigate()
  const [params] = useSearchParams()
  const [datos, setDatos] = useState({
    nombre: '', correo: '', telefono: '', contrasena: '',
    rol: params.get('rol') === 'arrendador' ? 'arrendador' : 'arrendatario',
  })
  const [acepta, setAcepta] = useState(false)
  const [error, setError] = useState('')
  const [enviando, setEnviando] = useState(false)
  const cambiar = (campo) => (e) => setDatos({ ...datos, [campo]: e.target.value })

  const claveValida = datos.contrasena.length >= 8 && /[A-Za-z]/.test(datos.contrasena) && /\d/.test(datos.contrasena)

  const enviar = async (e) => {
    e.preventDefault()
    setError('')
    if (!claveValida) return setError('La contraseña necesita al menos 8 caracteres, con letras y números.')
    if (!acepta) return setError('Para crear tu cuenta necesitamos que aceptes el tratamiento de tus datos.')
    setEnviando(true)
    try {
      const usuario = await registrarse({ ...datos, telefono: datos.telefono || null, acepta_datos: true })
      navegar(usuario.rol === 'arrendador' ? '/publicar' : '/buscar', { replace: true })
    } catch (err) {
      setError(err.message)
    } finally {
      setEnviando(false)
    }
  }

  return (
    <div className="tarjeta-formulario">
      <h1>Crear cuenta</h1>
      <form onSubmit={enviar} noValidate>
        <fieldset className="opciones-rol">
          <legend>¿Cómo vas a usar ParkMatch?</legend>
          {ROLES.map((r) => (
            <label key={r.valor} className={`opcion-rol${datos.rol === r.valor ? ' elegida' : ''}`}>
              <input type="radio" name="rol" value={r.valor} checked={datos.rol === r.valor} onChange={cambiar('rol')} />
              <strong>{r.titulo}</strong>
              <span>{r.detalle}</span>
            </label>
          ))}
        </fieldset>

        <label className="campo">
          <span>Nombre y apellido</span>
          <input id="nombre" autoComplete="name" required value={datos.nombre} onChange={cambiar('nombre')} />
        </label>
        <label className="campo">
          <span>Correo</span>
          <input id="correo" type="email" autoComplete="email" required value={datos.correo}
            onChange={cambiar('correo')} placeholder="nombre@correo.com" />
        </label>
        <label className="campo">
          <span>Celular <em>(opcional)</em></span>
          <input id="telefono" type="tel" autoComplete="tel" value={datos.telefono} onChange={cambiar('telefono')} />
        </label>
        <label className="campo">
          <span>Contraseña</span>
          <input id="contrasena" type="password" autoComplete="new-password" required value={datos.contrasena}
            onChange={cambiar('contrasena')} aria-describedby="ayuda-clave" />
          <small id="ayuda-clave" className={datos.contrasena && !claveValida ? 'ayuda ayuda-alerta' : 'ayuda'}>
            Mínimo 8 caracteres, con letras y números.
          </small>
        </label>

        <label className="casilla">
          <input type="checkbox" checked={acepta} onChange={(e) => setAcepta(e.target.checked)} />
          <span>Acepto que ParkMatch trate mis datos personales para gestionar mi cuenta, según la Ley N.º 29733. <a href="#politica">Ver política</a>.</span>
        </label>

        <Error>{error}</Error>
        <button className="boton boton-primario boton-ancho" disabled={enviando || !acepta}>
          {enviando ? 'Creando cuenta…' : 'Crear cuenta'}
        </button>
      </form>
      <p className="pie-formulario">¿Ya tienes cuenta? <Link to="/ingresar">Ingresa</Link></p>
    </div>
  )
}
