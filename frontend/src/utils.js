// Formatos y constantes compartidas. Toda la aplicación trabaja en hora de Lima.
export const ZONA = 'America/Lima'
const DESFASE = '-05:00' // Lima no tiene horario de verano

export const DIAS = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
export const DIAS_CORTOS = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom']

export const TIPOS = { moto: 'Moto', auto: 'Auto', camioneta: 'Camioneta' }

export const LIMA = { lat: -12.0977, lng: -77.0 }
export const ZONAS = [
  { nombre: 'Miraflores', lat: -12.1211, lng: -77.0297 },
  { nombre: 'San Isidro', lat: -12.0931, lng: -77.026 },
  { nombre: 'Surco', lat: -12.1106, lng: -76.9812 },
  { nombre: 'U. de Lima', lat: -12.0847, lng: -76.9717 },
  { nombre: 'La Molina', lat: -12.0763, lng: -76.955 },
  { nombre: 'San Borja', lat: -12.099, lng: -76.996 },
]

export const soles = (n) => `S/ ${Number(n).toFixed(2)}`

// "08:00:00" → "08:00"; el final del día se guarda como 23:59 y se muestra como 24:00
export const hhmm = (h) => {
  const corto = String(h).slice(0, 5)
  return corto === '23:59' ? '24:00' : corto
}

// Opciones de hora cada 30 minutos
export const HORAS_INICIO = Array.from({ length: 48 }, (_, i) =>
  `${String(Math.floor(i / 2)).padStart(2, '0')}:${i % 2 ? '30' : '00'}`)
export const HORAS_FIN = [...HORAS_INICIO.slice(1), '23:59']

// Fecha (AAAA-MM-DD) y hora (HH:MM) de Lima → ISO con desfase
export const isoLima = (fecha, hora) => `${fecha}T${hora}:00${DESFASE}`

export const hoyLima = () => new Intl.DateTimeFormat('en-CA', { timeZone: ZONA }).format(new Date())

export const sumarDias = (fecha, dias) => {
  const d = new Date(`${fecha}T12:00:00${DESFASE}`)
  d.setUTCDate(d.getUTCDate() + dias)
  return new Intl.DateTimeFormat('en-CA', { timeZone: ZONA }).format(d)
}

const fmtFecha = new Intl.DateTimeFormat('es-PE', { timeZone: ZONA, weekday: 'short', day: 'numeric', month: 'short' })
const fmtHora = new Intl.DateTimeFormat('es-PE', { timeZone: ZONA, hour: '2-digit', minute: '2-digit', hour12: false })
const fmtCompleta = new Intl.DateTimeFormat('es-PE', {
  timeZone: ZONA, day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit', hour12: false,
})

export const fecha = (iso) => fmtFecha.format(new Date(iso))
export const hora = (iso) => {
  const h = fmtHora.format(new Date(iso))
  return h === '23:59' ? '24:00' : h
}
export const fechaHora = (iso) => fmtCompleta.format(new Date(iso))
export const rango = (inicio, fin) => `${fecha(inicio)} · ${hora(inicio)} a ${hora(fin)}`

export const duracion = (minutos) => {
  const h = Math.floor(minutos / 60)
  const m = minutos % 60
  if (!h) return `${m} min`
  return m ? `${h} h ${m} min` : `${h} h`
}

export const iniciales = (nombre) =>
  nombre.split(' ').filter(Boolean).slice(0, 2).map((p) => p[0].toUpperCase()).join('')

export const ESTADOS = {
  solicitada: { texto: 'Por confirmar', tono: 'aviso' },
  confirmada: { texto: 'Confirmada', tono: 'ok' },
  rechazada: { texto: 'Rechazada', tono: 'error' },
  cancelada: { texto: 'Cancelada', tono: 'neutro' },
  en_curso: { texto: 'En curso', tono: 'ok' },
  finalizada: { texto: 'Finalizada', tono: 'neutro' },
  pendiente: { texto: 'Pendiente', tono: 'aviso' },
  pagado: { texto: 'Pagado', tono: 'ok' },
  por_devolver: { texto: 'Por devolver', tono: 'aviso' },
  reembolsado: { texto: 'Devuelto', tono: 'neutro' },
}

export const ACCIONES = {
  usuario_registrado: 'Cuenta creada',
  reserva_solicitada: 'Reserva solicitada',
  reserva_confirmada: 'Reserva confirmada',
  reserva_rechazada: 'Reserva rechazada',
  reserva_rechazada_por_cruce: 'Solicitud cruzada, rechazada',
  reserva_cancelada: 'Reserva cancelada',
  pago_recibido: 'Pago registrado',
  pago_devuelto: 'Pago devuelto',
  ingreso_registrado: 'Ingreso registrado',
  salida_registrada: 'Salida registrada',
  cochera_editada: 'Cochera editada',
  calendario_actualizado: 'Calendario actualizado',
  tarjeta_registrada: 'Tarjeta registrada',
  tarjeta_eliminada: 'Tarjeta eliminada',
  cochera_publicada: 'Cochera publicada',
  cochera_pausada: 'Cochera pausada',
  cochera_activada: 'Cochera activada',
  tarifas_actualizadas: 'Tarifas actualizadas',
  calendario_actualizado: 'Calendario actualizado',
  reserva_solicitada: 'Reserva solicitada',
  reserva_confirmada: 'Reserva confirmada',
  reserva_rechazada: 'Reserva rechazada',
  reserva_rechazada_por_cruce: 'Solicitud rechazada por cruce de horario',
  reserva_cancelada: 'Reserva cancelada',
  pago_recibido: 'Pago registrado como recibido',
}
