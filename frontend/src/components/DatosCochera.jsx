import { useState } from 'react'
import { MapaPunto } from './Mapa'
import { TIPOS } from '../utils'

const BUSCAR_DIRECCION = (texto) =>
  `https://nominatim.openstreetmap.org/search?format=json&limit=1&countrycodes=pe&q=${encodeURIComponent(texto + ', Lima, Perú')}`

/** Campos del anuncio: título, descripción, medidas, dirección y punto en el mapa (requisitos 6 y 7). */
export default function DatosCochera({ valor, alCambiar }) {
  const [aviso, setAviso] = useState('')
  const set = (campo) => (e) => alCambiar({ ...valor, [campo]: e.target.type === 'checkbox' ? e.target.checked : e.target.value })
  const punto = valor.latitud && valor.longitud ? { lat: Number(valor.latitud), lng: Number(valor.longitud) } : null

  const ubicarDireccion = async () => {
    setAviso('')
    if (valor.direccion.trim().length < 5) return setAviso('Escribe la dirección primero.')
    try {
      const [lugar] = await (await fetch(BUSCAR_DIRECCION(valor.direccion))).json()
      if (!lugar) return setAviso('No encontramos esa dirección. Ubica el punto tocando el mapa.')
      alCambiar({ ...valor, latitud: Number(lugar.lat).toFixed(6), longitud: Number(lugar.lon).toFixed(6) })
    } catch {
      setAviso('No pudimos buscar la dirección. Ubica el punto tocando el mapa.')
    }
  }

  return (
    <div className="datos-cochera">
      <label className="campo">
        <span>Título del anuncio</span>
        <input required value={valor.titulo} onChange={set('titulo')} placeholder="Ej.: Cochera techada cerca a la Av. Larco" />
      </label>
      <label className="campo">
        <span>Descripción</span>
        <textarea required rows={4} value={valor.descripcion} onChange={set('descripcion')}
          placeholder="Cuenta cómo se accede, si hay portón, si el espacio es estrecho, etc." />
        <small className="ayuda">Mínimo 20 caracteres.</small>
      </label>

      <div className="fila-campos">
        <label className="campo">
          <span>Tipo de vehículo</span>
          <select value={valor.tipo_vehiculo} onChange={set('tipo_vehiculo')}>
            {Object.entries(TIPOS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </label>
        <label className="campo campo-corto">
          <span>Largo (m)</span>
          <input type="number" min="0.5" step="0.1" inputMode="decimal" required value={valor.largo_m} onChange={set('largo_m')} />
        </label>
        <label className="campo campo-corto">
          <span>Ancho (m)</span>
          <input type="number" min="0.5" step="0.1" inputMode="decimal" required value={valor.ancho_m} onChange={set('ancho_m')} />
        </label>
      </div>
      <label className="casilla">
        <input type="checkbox" checked={valor.techada} onChange={set('techada')} />
        <span>La cochera es techada</span>
      </label>

      <label className="campo">
        <span>Dirección</span>
        <div className="fila-campos">
          <input required value={valor.direccion} onChange={set('direccion')} placeholder="Av. Larco 1234" />
          <button type="button" className="boton boton-secundario" onClick={ubicarDireccion}>Ubicar en el mapa</button>
        </div>
      </label>
      <div className="fila-campos">
        <label className="campo">
          <span>Distrito</span>
          <input required value={valor.distrito} onChange={set('distrito')} placeholder="Miraflores" />
        </label>
        <label className="campo">
          <span>Referencia <em>(opcional)</em></span>
          <input value={valor.referencia} onChange={set('referencia')} placeholder="Frente al parque" />
        </label>
      </div>
      {aviso && <p className="ayuda ayuda-alerta">{aviso}</p>}

      <p className="ayuda">Toca el mapa para marcar el punto exacto de la cochera.</p>
      <MapaPunto punto={punto} alto={260}
        alElegir={({ lat, lng }) => alCambiar({ ...valor, latitud: lat.toFixed(6), longitud: lng.toFixed(6) })} />
    </div>
  )
}

export const datosVacios = () => ({
  titulo: '', descripcion: '', tipo_vehiculo: 'auto', largo_m: '', ancho_m: '', techada: false,
  direccion: '', distrito: '', referencia: '', latitud: '', longitud: '',
})

/** Errores de los datos del anuncio, o null si están bien. */
export const errorDatos = (d) => {
  if (d.titulo.trim().length < 5) return 'El título necesita al menos 5 caracteres.'
  if (d.descripcion.trim().length < 20) return 'La descripción necesita al menos 20 caracteres.'
  if (!(Number(d.largo_m) > 0 && Number(d.ancho_m) > 0)) return 'Indica el largo y el ancho de la cochera.'
  if (d.direccion.trim().length < 5) return 'Escribe la dirección.'
  if (d.distrito.trim().length < 2) return 'Escribe el distrito.'
  if (!d.latitud || !d.longitud) return 'Marca el punto de la cochera en el mapa.'
  return null
}

export const datosParaApi = (d) => ({
  titulo: d.titulo.trim(), descripcion: d.descripcion.trim(), tipo_vehiculo: d.tipo_vehiculo,
  largo_m: Number(d.largo_m), ancho_m: Number(d.ancho_m), techada: d.techada,
  direccion: d.direccion.trim(), distrito: d.distrito.trim(), referencia: d.referencia.trim() || null,
  latitud: Number(d.latitud), longitud: Number(d.longitud),
})
