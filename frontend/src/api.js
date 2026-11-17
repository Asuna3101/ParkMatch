// Cliente HTTP del backend. Todas las llamadas pasan por aquí.
export const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'
export const WS_URL = API_URL.replace(/^http/, 'ws') + '/ws'

const CLAVE_TOKEN = 'parkmatch_token'

export const tokenGuardado = () => localStorage.getItem(CLAVE_TOKEN)
export const guardarToken = (t) => (t ? localStorage.setItem(CLAVE_TOKEN, t) : localStorage.removeItem(CLAVE_TOKEN))

// Las fotos se guardan como rutas relativas (/uploads/...).
export const urlFoto = (ruta) => (ruta ? (ruta.startsWith('http') ? ruta : API_URL + ruta) : null)

export class ErrorApi extends Error {
  constructor(mensaje, estado) {
    super(mensaje)
    this.estado = estado
  }
}

async function pedir(ruta, { metodo = 'GET', cuerpo, formulario } = {}) {
  const cabeceras = {}
  const token = tokenGuardado()
  if (token) cabeceras.Authorization = `Bearer ${token}`
  if (cuerpo !== undefined) cabeceras['Content-Type'] = 'application/json'

  let respuesta
  try {
    respuesta = await fetch(API_URL + ruta, {
      method: metodo,
      headers: cabeceras,
      body: formulario ?? (cuerpo !== undefined ? JSON.stringify(cuerpo) : undefined),
    })
  } catch {
    throw new ErrorApi('No pudimos conectar con el servidor. Revisa que el backend esté encendido.', 0)
  }

  const datos = respuesta.status === 204 ? null : await respuesta.json().catch(() => null)
  if (!respuesta.ok) {
    const detalle = typeof datos?.detail === 'string' ? datos.detail : 'Ocurrió un error. Inténtalo de nuevo.'
    if (respuesta.status === 401 && token) window.dispatchEvent(new Event('parkmatch:sesion-vencida'))
    throw new ErrorApi(detalle, respuesta.status)
  }
  return datos
}

const consulta = (params) => new URLSearchParams(params).toString()

/** Descarga un archivo (p. ej. el código QR) con el token, porque <img> no puede enviarlo. */
async function pedirArchivo(ruta) {
  const token = tokenGuardado()
  const respuesta = await fetch(API_URL + ruta, { headers: token ? { Authorization: `Bearer ${token}` } : {} })
  if (!respuesta.ok) throw new ErrorApi('No pudimos cargar el archivo.', respuesta.status)
  return respuesta.blob()
}

export const api = {
  // autenticación
  registro: (datos) => pedir('/api/auth/registro', { metodo: 'POST', cuerpo: datos }),
  login: (datos) => pedir('/api/auth/login', { metodo: 'POST', cuerpo: datos }),
  yo: () => pedir('/api/auth/yo'),
  recuperar: (correo) => pedir('/api/auth/recuperar', { metodo: 'POST', cuerpo: { correo } }),
  restablecer: (token, contrasena) => pedir('/api/auth/restablecer', { metodo: 'POST', cuerpo: { token, contrasena } }),

  // perfil
  perfil: () => pedir('/api/perfil'),
  editarPerfil: (datos) => pedir('/api/perfil', { metodo: 'PUT', cuerpo: datos }),
  cambiarContrasena: (actual, nueva) => pedir('/api/perfil/contrasena', { metodo: 'POST', cuerpo: { actual, nueva } }),
  subirFotoPerfil: (foto) => {
    const formulario = new FormData()
    formulario.append('foto', foto)
    return pedir('/api/perfil/foto', { metodo: 'POST', formulario })
  },
  subirDocumento: (documento) => {
    const formulario = new FormData()
    formulario.append('documento', documento)
    return pedir('/api/perfil/documento', { metodo: 'POST', formulario })
  },
  agregarVehiculo: (datos) => pedir('/api/perfil/vehiculos', { metodo: 'POST', cuerpo: datos }),
  eliminarVehiculo: (id) => pedir(`/api/perfil/vehiculos/${id}`, { metodo: 'DELETE' }),
  perfilPublico: (id) => pedir(`/api/usuarios/${id}`),

  // cocheras
  buscar: (lat, lng, radio_km, filtros = {}) => {
    const params = { lat, lng, radio_km }
    Object.entries(filtros).forEach(([k, v]) => { if (v !== '' && v != null) params[k] = v })
    return pedir(`/api/cocheras/buscar?${consulta(params)}`)
  },
  cochera: (id) => pedir(`/api/cocheras/${id}`),
  editarCochera: (id, datos) => pedir(`/api/cocheras/${id}`, { metodo: 'PUT', cuerpo: datos }),
  cotizar: (id, inicio, fin) => pedir(`/api/cocheras/${id}/cotizar?${consulta({ inicio, fin })}`),
  misCocheras: () => pedir('/api/cocheras/mias'),
  publicar: (datos, fotos) => {
    const formulario = new FormData()
    formulario.append('datos', JSON.stringify(datos))
    fotos.forEach((f) => formulario.append('fotos', f))
    return pedir('/api/cocheras', { metodo: 'POST', formulario })
  },
  cambiarEstado: (id, activa) => pedir(`/api/cocheras/${id}/estado`, { metodo: 'PATCH', cuerpo: { activa } }),
  guardarTarifas: (id, datos) => pedir(`/api/cocheras/${id}/tarifas`, { metodo: 'PUT', cuerpo: datos }),
  guardarCalendario: (id, franjas) => pedir(`/api/cocheras/${id}/disponibilidad`, { metodo: 'PUT', cuerpo: { franjas } }),

  // reservas y pagos
  solicitar: (cochera_id, inicio, fin, medio_pago = 'acordado', metodo_pago_id = null) =>
    pedir('/api/reservas', { metodo: 'POST', cuerpo: { cochera_id, inicio, fin, medio_pago, metodo_pago_id } }),
  reserva: (id) => pedir(`/api/reservas/${id}`),
  misReservas: () => pedir('/api/reservas/mias'),
  reservasRecibidas: () => pedir('/api/reservas/recibidas'),
  confirmar: (id) => pedir(`/api/reservas/${id}/confirmar`, { metodo: 'POST' }),
  rechazar: (id, motivo) => pedir(`/api/reservas/${id}/rechazar`, { metodo: 'POST', cuerpo: { motivo } }),
  cancelar: (id) => pedir(`/api/reservas/${id}/cancelar`, { metodo: 'POST' }),
  codigoQr: (id) => pedirArchivo(`/api/reservas/${id}/qr`),
  registrarIngreso: (id, codigo) => pedir(`/api/reservas/${id}/ingreso`, { metodo: 'POST', cuerpo: { codigo } }),
  registrarSalida: (id) => pedir(`/api/reservas/${id}/salida`, { metodo: 'POST' }),
  pagoRecibido: (id, medio) => pedir(`/api/pagos/${id}/recibido`, { metodo: 'POST', cuerpo: { medio } }),
  pagoDevuelto: (id) => pedir(`/api/pagos/${id}/devuelto`, { metodo: 'POST' }),
  pagosArrendador: () => pedir('/api/pagos/arrendador'),
  auditoria: () => pedir('/api/auditoria'),

  // calificaciones, notificaciones, reportes y disputas
  calificar: (id, estrellas, comentario) => pedir(`/api/reservas/${id}/calificar`, { metodo: 'POST', cuerpo: { estrellas, comentario } }),
  notificaciones: () => pedir('/api/notificaciones'),
  marcarLeidas: () => pedir('/api/notificaciones/leidas', { metodo: 'POST' }),
  reportar: (cocheraId, motivo, detalle) => pedir(`/api/cocheras/${cocheraId}/reportes`, { metodo: 'POST', cuerpo: { motivo, detalle } }),
  abrirDisputa: (reservaId, tipo, descripcion) => pedir(`/api/reservas/${reservaId}/disputas`, { metodo: 'POST', cuerpo: { tipo, descripcion } }),
  misDisputas: () => pedir('/api/disputas/mias'),

  // administración
  admin: {
    resumen: () => pedir('/api/admin/resumen'),
    reportes: (estado = 'pendiente') => pedir(`/api/admin/reportes?${consulta({ estado })}`),
    resolverReporte: (id, decision, nota) => pedir(`/api/admin/reportes/${id}/resolver`, { metodo: 'POST', cuerpo: { decision, nota } }),
    reactivarCochera: (id) => pedir(`/api/admin/cocheras/${id}/reactivar`, { metodo: 'POST' }),
    disputas: (estado = 'abierta') => pedir(`/api/admin/disputas?${consulta({ estado })}`),
    resolverDisputa: (id, accion, resolucion) => pedir(`/api/admin/disputas/${id}/resolver`, { metodo: 'POST', cuerpo: { accion, resolucion } }),
    verificaciones: () => pedir('/api/admin/verificaciones'),
    documento: (id) => pedirArchivo(`/api/admin/verificaciones/${id}/documento`),
    resolverVerificacion: (id, aprobar) => pedir(`/api/admin/verificaciones/${id}`, { metodo: 'POST', cuerpo: { aprobar } }),
  },

  // tarjetas simuladas
  tarjetas: () => pedir('/api/tarjetas'),
  agregarTarjeta: (datos) => pedir('/api/tarjetas', { metodo: 'POST', cuerpo: datos }),
  eliminarTarjeta: (id) => pedir(`/api/tarjetas/${id}`, { metodo: 'DELETE' }),

  // chat
  abrirConversacion: (cochera_id) => pedir('/api/conversaciones', { metodo: 'POST', cuerpo: { cochera_id } }),
  conversaciones: () => pedir('/api/conversaciones'),
  mensajes: (id) => pedir(`/api/conversaciones/${id}/mensajes`),
  enviarMensaje: (id, texto) => pedir(`/api/conversaciones/${id}/mensajes`, { metodo: 'POST', cuerpo: { texto } }),
}
