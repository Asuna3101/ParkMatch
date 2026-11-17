import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api, urlFoto } from '../api'
import { useAuth } from '../auth'
import { Error, Estado, Estrellas, Resenas, Vacio } from '../components/Comunes'
import { useTiempoReal } from '../tiempo-real'
import { TIPOS, fecha, iniciales } from '../utils'

const VERIFICACION = {
  sin_verificar: 'Aún no verificaste tu identidad.',
  pendiente: 'Recibimos tu documento. El equipo lo está revisando.',
  verificado: 'Tu identidad está verificada.',
  rechazado: 'No pudimos validar tu documento. Envía una foto más clara.',
}

/** Datos de la cuenta, vehículos, contraseña y verificación (US-04). */
export default function Perfil() {
  const { actualizarUsuario, esArrendatario, salir } = useAuth()
  const navegar = useNavigate()
  const { avisar } = useTiempoReal()
  const [perfil, setPerfil] = useState(null)
  const [datos, setDatos] = useState({ nombre: '', telefono: '' })
  const [vehiculo, setVehiculo] = useState({ placa: '', tipo: 'auto', descripcion: '' })
  const [claves, setClaves] = useState({ actual: '', nueva: '' })
  const [error, setError] = useState('')

  const cargar = (p) => {
    setPerfil(p)
    setDatos({ nombre: p.nombre, telefono: p.telefono || '' })
    actualizarUsuario({ nombre: p.nombre, telefono: p.telefono, foto_url: p.foto_url, verificacion: p.verificacion })
  }

  useEffect(() => { api.perfil().then(cargar).catch((e) => setError(e.message)) }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const hacer = async (fn, mensaje) => {
    setError('')
    try {
      const r = await fn()
      if (r) cargar(r)
      if (mensaje) avisar(mensaje)
      return true
    } catch (e) {
      setError(e.message)
      return false
    }
  }

  if (!perfil) return error ? <Error>{error}</Error> : <p className="cargando">Cargando…</p>

  return (
    <div className="pagina-formulario">
      <div className="perfil-cabecera">
        <div className="avatar-grande">
          {perfil.foto_url ? <img src={urlFoto(perfil.foto_url)} alt="" /> : iniciales(perfil.nombre)}
        </div>
        <div>
          <h1>{perfil.nombre}</h1>
          <p className="ayuda">{perfil.correo} · miembro desde {fecha(perfil.creado_en)}</p>
          <Link to={`/usuarios/${perfil.id}`}>Ver mi perfil público</Link>
        </div>
      </div>
      <Error>{error}</Error>

      <div className="rejilla-dos">
        <form className="bloque" onSubmit={(e) => { e.preventDefault(); hacer(() => api.editarPerfil(datos), 'Datos guardados.') }}>
          <h2>Mis datos</h2>
          <label className="campo">
            <span>Nombre completo</span>
            <input value={datos.nombre} onChange={(e) => setDatos({ ...datos, nombre: e.target.value })} />
          </label>
          <label className="campo">
            <span>Teléfono <em>(se comparte solo con reservas confirmadas)</em></span>
            <input type="tel" value={datos.telefono} onChange={(e) => setDatos({ ...datos, telefono: e.target.value })} />
          </label>
          <label className="campo">
            <span>Foto de perfil</span>
            <input type="file" accept="image/jpeg,image/png,image/webp"
              onChange={(e) => e.target.files[0] && hacer(() => api.subirFotoPerfil(e.target.files[0]), 'Foto actualizada.')} />
          </label>
          <button className="boton boton-primario">Guardar</button>
        </form>

        <section className="bloque">
          <h2>Verificación de identidad</h2>
          <p><Estado estado={perfil.verificacion} /></p>
          <p className="ayuda">{VERIFICACION[perfil.verificacion]}</p>
          {['sin_verificar', 'rechazado'].includes(perfil.verificacion) && (
            <label className="campo">
              <span>Foto de tu DNI <em>(solo la ve el equipo de ParkMatch)</em></span>
              <input type="file" accept="image/jpeg,image/png,image/webp"
                onChange={(e) => e.target.files[0] && hacer(() => api.subirDocumento(e.target.files[0]), 'Documento enviado.')} />
            </label>
          )}
        </section>

        {esArrendatario && (
          <section className="bloque">
            <h2>Mis vehículos</h2>
            {perfil.vehiculos.length > 0 && (
              <ul className="lista-vehiculos">
                {perfil.vehiculos.map((v) => (
                  <li key={v.id}>
                    <span><strong>{v.placa}</strong> · {TIPOS[v.tipo]}{v.descripcion ? ` · ${v.descripcion}` : ''}</span>
                    <button className="boton boton-texto boton-peligro"
                      onClick={() => hacer(() => api.eliminarVehiculo(v.id), 'Vehículo eliminado.')}>Quitar</button>
                  </li>
                ))}
              </ul>
            )}
            <form onSubmit={async (e) => {
              e.preventDefault()
              const ok = await hacer(() => api.agregarVehiculo({ ...vehiculo, descripcion: vehiculo.descripcion || null }), 'Vehículo agregado.')
              if (ok) setVehiculo({ placa: '', tipo: 'auto', descripcion: '' })
            }}>
              <div className="fila-campos">
                <label className="campo">
                  <span>Placa</span>
                  <input value={vehiculo.placa} onChange={(e) => setVehiculo({ ...vehiculo, placa: e.target.value })} placeholder="ABC-123" />
                </label>
                <label className="campo">
                  <span>Tipo</span>
                  <select value={vehiculo.tipo} onChange={(e) => setVehiculo({ ...vehiculo, tipo: e.target.value })}>
                    {Object.entries(TIPOS).map(([v, t]) => <option key={v} value={v}>{t}</option>)}
                  </select>
                </label>
              </div>
              <label className="campo">
                <span>Descripción <em>(opcional)</em></span>
                <input value={vehiculo.descripcion} maxLength={80} onChange={(e) => setVehiculo({ ...vehiculo, descripcion: e.target.value })} placeholder="Toyota Yaris gris" />
              </label>
              <button className="boton boton-secundario" disabled={vehiculo.placa.trim().length < 5}>Agregar vehículo</button>
            </form>
          </section>
        )}

        <form className="bloque" onSubmit={async (e) => {
          e.preventDefault()
          const ok = await hacer(() => api.cambiarContrasena(claves.actual, claves.nueva), 'Contraseña actualizada.')
          if (ok) setClaves({ actual: '', nueva: '' })
        }}>
          <h2>Cambiar contraseña</h2>
          <label className="campo">
            <span>Contraseña actual</span>
            <input type="password" autoComplete="current-password" value={claves.actual} onChange={(e) => setClaves({ ...claves, actual: e.target.value })} />
          </label>
          <label className="campo">
            <span>Nueva contraseña</span>
            <input type="password" autoComplete="new-password" value={claves.nueva} onChange={(e) => setClaves({ ...claves, nueva: e.target.value })} />
          </label>
          <button className="boton boton-secundario" disabled={!claves.actual || !claves.nueva}>Cambiar contraseña</button>
        </form>
      </div>

      <p className="pie-formulario">
        <Link to="/registro-de-actividad">Ver mi registro de actividad</Link>
        {' · '}
        <button className="boton boton-texto" onClick={() => { salir(); navegar('/') }}>Cerrar sesión</button>
      </p>
    </div>
  )
}

/** Perfil público con reputación (US-21). */
export function PerfilPublico({ id }) {
  const [p, setP] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => { api.perfilPublico(id).then(setP).catch((e) => setError(e.message)) }, [id])

  if (!p) return error ? <Error>{error}</Error> : <p className="cargando">Cargando…</p>
  return (
    <div className="pagina-formulario">
      <div className="perfil-cabecera">
        <div className="avatar-grande">{p.foto_url ? <img src={urlFoto(p.foto_url)} alt="" /> : iniciales(p.nombre)}</div>
        <div>
          <h1>{p.nombre} {p.verificado && <span className="etiqueta etiqueta-ok">Verificado</span>}</h1>
          <p className="ayuda">
            {p.rol === 'arrendador' ? 'Arrendador' : 'Conductor'} · miembro desde {fecha(p.miembro_desde)}
            {' '}· {p.transacciones_completadas} {p.transacciones_completadas === 1 ? 'reserva completada' : 'reservas completadas'}
          </p>
          <Estrellas valor={p.calificacion_promedio} total={p.total_calificaciones} />
        </div>
      </div>

      {p.cocheras.length > 0 && (
        <section className="bloque">
          <h2>Cocheras</h2>
          <ul className="lista-simple">
            {p.cocheras.map((c) => (
              <li key={c.id}><Link to={`/cocheras/${c.id}`}>{c.titulo}</Link> · {c.distrito}</li>
            ))}
          </ul>
        </section>
      )}

      <section className="bloque">
        <h2>Reseñas</h2>
        {p.resenas.length ? <Resenas resenas={p.resenas} /> : <Vacio titulo="Todavía no hay reseñas" />}
      </section>
    </div>
  )
}
