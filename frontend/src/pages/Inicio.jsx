import { Link, Navigate } from 'react-router-dom'
import { useAuth } from '../auth'

export default function Inicio() {
  const { usuario, cargando, esArrendador } = useAuth()
  if (cargando) return <p className="cargando">Cargando…</p>
  if (usuario) return <Navigate to={esArrendador ? '/mis-cocheras' : '/buscar'} replace />

  return (
    <div className="inicio">
      <section className="portada">
        <div className="portada-texto">
          <p className="antetitulo">Cocheras entre particulares</p>
          <h1>Estaciona en una cochera que hoy está vacía.</h1>
          <p className="bajada">
            ParkMatch conecta a quien busca dónde dejar su auto con vecinos que tienen una cochera libre.
            Elige en el mapa, coordina por chat y reserva por horas.
          </p>
          <div className="portada-acciones">
            <Link to="/buscar" className="boton boton-primario boton-grande">Buscar una cochera</Link>
            <Link to="/registro?rol=arrendador" className="boton boton-secundario boton-grande">Publicar mi cochera</Link>
          </div>
        </div>
        <div className="portada-dibujo" aria-hidden="true">
          <div className="cajon"><span>S/ 6</span></div>
          <div className="cajon cajon-libre"><span>Libre</span></div>
          <div className="cajon"><span>S/ 4</span></div>
          <div className="cajon"><span>S/ 8</span></div>
        </div>
      </section>

      <section className="pasos" aria-label="Cómo funciona">
        <article>
          <h2>Para quien maneja</h2>
          <ol>
            <li>Busca en el mapa las cocheras cercanas a tu destino.</li>
            <li>Revisa fotos, precio por hora y horario disponible.</li>
            <li>Envía la solicitud y recibe la confirmación del dueño.</li>
          </ol>
        </article>
        <article>
          <h2>Para quien tiene cochera</h2>
          <ol>
            <li>Publica tu espacio con fotos, tarifa y los horarios en que está libre.</li>
            <li>Acepta o rechaza cada solicitud; el horario aceptado queda bloqueado.</li>
            <li>Cobra como acuerden y registra el pago recibido.</li>
          </ol>
        </article>
      </section>
    </div>
  )
}
