import L from 'leaflet'
import { useEffect, useMemo } from 'react'
import { MapContainer, Marker, TileLayer, useMap, useMapEvents } from 'react-leaflet'

const MOSAICOS = 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png'
const CREDITO = '&copy; colaboradores de <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'

// Marcador con el precio: es HTML, así no depende de archivos de imagen.
const pinPrecio = (precio, activo) => L.divIcon({
  className: '',
  html: `<div class="pin${activo ? ' pin-activo' : ''}">S/ ${Number(precio).toFixed(Number.isInteger(Number(precio)) ? 0 : 2)}</div>`,
  iconSize: [0, 0],
})

const pinPunto = L.divIcon({ className: '', html: '<div class="pin-punto"></div>', iconSize: [0, 0] })
const pinYo = L.divIcon({ className: '', html: '<div class="pin-yo"></div>', iconSize: [0, 0] })

/** Mueve el mapa cuando cambia el centro desde fuera (zona elegida, "mi ubicación"). */
function Centrar({ centro, zoom }) {
  const mapa = useMap()
  useEffect(() => {
    if (centro) mapa.setView([centro.lat, centro.lng], zoom ?? mapa.getZoom(), { animate: true })
  }, [centro?.lat, centro?.lng, centro?.sello]) // eslint-disable-line react-hooks/exhaustive-deps
  return null
}

/** Avisa al terminar de mover el mapa: centro y radio visible en km. */
function AlMover({ alMover }) {
  const mapa = useMapEvents({
    moveend: () => {
      const c = mapa.getCenter()
      const radio = c.distanceTo(mapa.getBounds().getNorthEast()) / 1000
      alMover({ lat: c.lat, lng: c.lng, radio: Math.min(50, Math.max(0.5, radio)) })
    },
  })
  useEffect(() => { mapa.fire('moveend') }, [mapa])
  return null
}

function AlHacerClic({ alElegir }) {
  useMapEvents({ click: (e) => alElegir({ lat: e.latlng.lat, lng: e.latlng.lng }) })
  return null
}

/** Mapa de búsqueda: un pin con el precio por cada cochera. */
export function MapaCocheras({ centro, cocheras, seleccionada, alSeleccionar, alMover, miUbicacion }) {
  const pines = useMemo(() => cocheras.map((c) => (
    <Marker
      key={`${c.id}-${c.id === seleccionada}`}
      position={[c.latitud, c.longitud]}
      icon={pinPrecio(c.precio_hora, c.id === seleccionada)}
      zIndexOffset={c.id === seleccionada ? 1000 : 0}
      title={c.titulo}
      eventHandlers={{ click: () => alSeleccionar(c.id) }}
    />
  )), [cocheras, seleccionada, alSeleccionar])

  return (
    <MapContainer center={[centro.lat, centro.lng]} zoom={13} className="mapa" scrollWheelZoom>
      <TileLayer url={MOSAICOS} attribution={CREDITO} />
      <Centrar centro={centro} zoom={centro.zoom} />
      <AlMover alMover={alMover} />
      {miUbicacion && <Marker position={[miUbicacion.lat, miUbicacion.lng]} icon={pinYo} title="Tu ubicación" />}
      {pines}
    </MapContainer>
  )
}

/** Mapa pequeño con un solo punto. Si recibe alElegir, el punto se mueve al hacer clic. */
export function MapaPunto({ punto, alElegir, alto = 260 }) {
  const centro = punto ?? { lat: -12.0977, lng: -77.0 }
  return (
    <MapContainer center={[centro.lat, centro.lng]} zoom={punto ? 16 : 12} className="mapa"
      style={{ height: alto }} scrollWheelZoom={Boolean(alElegir)}>
      <TileLayer url={MOSAICOS} attribution={CREDITO} />
      {punto && <Centrar centro={punto} zoom={16} />}
      {alElegir && <AlHacerClic alElegir={alElegir} />}
      {punto && <Marker position={[punto.lat, punto.lng]} icon={pinPunto} />}
    </MapContainer>
  )
}
