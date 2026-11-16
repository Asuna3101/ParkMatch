import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { useAuth } from './auth'
import Layout from './components/Layout'
import Auditoria from './pages/Auditoria'
import Buscar from './pages/Buscar'
import Chat from './pages/Chat'
import CocheraDetalle from './pages/CocheraDetalle'
import EditarCochera from './pages/EditarCochera'
import Inicio from './pages/Inicio'
import Login from './pages/Login'
import MisCocheras from './pages/MisCocheras'
import PublicarCochera from './pages/PublicarCochera'
import Registro from './pages/Registro'
import Reservas from './pages/Reservas'

/** Exige sesión y, si se indica, un rol concreto. */
function Privada({ rol, children }) {
  const { usuario, cargando } = useAuth()
  const ubicacion = useLocation()
  if (cargando) return <p className="cargando">Cargando…</p>
  if (!usuario) return <Navigate to="/ingresar" state={{ desde: ubicacion.pathname }} replace />
  if (rol && usuario.rol !== rol) return <Navigate to="/" replace />
  return children
}

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Inicio />} />
        <Route path="/ingresar" element={<Login />} />
        <Route path="/registro" element={<Registro />} />
        <Route path="/buscar" element={<Buscar />} />
        <Route path="/cocheras/:id" element={<CocheraDetalle />} />
        <Route path="/mis-cocheras" element={<Privada rol="arrendador"><MisCocheras /></Privada>} />
        <Route path="/publicar" element={<Privada rol="arrendador"><PublicarCochera /></Privada>} />
        <Route path="/cocheras/:id/editar" element={<Privada rol="arrendador"><EditarCochera /></Privada>} />
        <Route path="/reservas" element={<Privada><Reservas /></Privada>} />
        <Route path="/chat" element={<Privada><Chat /></Privada>} />
        <Route path="/chat/:id" element={<Privada><Chat /></Privada>} />
        <Route path="/registro-de-actividad" element={<Privada><Auditoria /></Privada>} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  )
}
