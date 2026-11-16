import { Link, NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth'
import { useTiempoReal } from '../tiempo-real'
import { iniciales } from '../utils'
import { IconoBuscar, IconoChat, IconoCochera, IconoReservas } from './Iconos'

export default function Layout() {
  const { usuario, salir, esArrendador } = useAuth()
  const { sinLeer } = useTiempoReal()
  const navegar = useNavigate()

  const enlaces = usuario
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
            <span className="marca-p" aria-hidden="true">P</span>
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
                <Link to="/registro-de-actividad" className="avatar" title={`${usuario.nombre} · ver registro de actividad`}>
                  {iniciales(usuario.nombre)}
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
