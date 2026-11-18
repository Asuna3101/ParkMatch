import { Link, NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth'
import { useTiempoReal } from '../tiempo-real'
import { urlFoto } from '../api'
import { iniciales } from '../utils'
import { IconoBuscar, IconoChat, IconoCochera, IconoEscudo, IconoReservas } from './Iconos'
import Notificaciones from './Notificaciones'

export default function Layout() {
  const { usuario, salir, esArrendador, esAdmin } = useAuth()
  const { sinLeer } = useTiempoReal()
  const navegar = useNavigate()

  const enlaces = esAdmin
    ? [
        { a: '/admin', texto: 'Moderación', icono: IconoEscudo },
        { a: '/buscar', texto: 'Mapa', icono: IconoBuscar },
      ]
    : usuario
    ? [
        esArrendador
          ? { a: '/mis-cocheras', texto: 'Mis cocheras', icono: IconoCochera }
          : { a: '/buscar', texto: 'Buscar', icono: IconoBuscar },
        { a: '/reservas', texto: esArrendador ? 'Solicitudes' : 'Mis reservas', icono: IconoReservas },
        { a: '/chat', texto: 'Mensajes', icono: IconoChat, contador: sinLeer },
      ]
    : []

  const cerrar = () => {
    salir()
    navegar('/')
  }

  return (
    <div className="app">
      <header className="cabecera">
        <div className="cabecera-contenido">
          <Link to="/" className="marca" aria-label="ParkMatch, inicio">
            <img className="marca-icono" src="/icono.png" alt="" width="32" height="32" />
            <span className="marca-nombre">ParkMatch</span>
          </Link>

          <nav className="nav-principal" aria-label="Principal">
            {enlaces.map(({ a, texto, contador }) => (
              <NavLink key={a} to={a}>
                {texto}
                {contador > 0 && <span className="contador">{contador}</span>}
              </NavLink>
            ))}
          </nav>

          <div className="cabecera-usuario">
            {usuario ? (
              <>
                <Notificaciones />
                <Link to="/perfil" className="avatar" title={`${usuario.nombre} · mi perfil`} aria-label="Mi perfil">
                  {usuario.foto_url ? <img src={urlFoto(usuario.foto_url)} alt="" /> : iniciales(usuario.nombre)}
                </Link>
                <button className="boton boton-texto" onClick={cerrar}>Salir</button>
              </>
            ) : (
              <>
                <Link to="/ingresar" className="boton boton-texto">Ingresar</Link>
                <Link to="/registro" className="boton boton-primario boton-chico">Crear cuenta</Link>
              </>
            )}
          </div>
        </div>
      </header>

      <main className="contenido">
        <Outlet />
      </main>

      {usuario && (
        <nav className="nav-inferior" aria-label="Principal">
          {enlaces.map(({ a, texto, icono: Icono, contador }) => (
            <NavLink key={a} to={a}>
              <span className="nav-icono">
                <Icono />
                {contador > 0 && <span className="contador">{contador}</span>}
              </span>
              {texto}
            </NavLink>
          ))}
        </nav>
      )}
    </div>
  )
}
