# ParkMatch — MVP

Marketplace para reservar cocheras entre particulares.
- **Backend:** FastAPI + SQLAlchemy + PostgreSQL (pgAdmin)
- **Frontend:** React 18 + Vite + Leaflet (OpenStreetMap)

## 1. Base de datos (pgAdmin)
1. En pgAdmin, crea una base de datos llamada `parkmatch`.
2. Abre *Query Tool* sobre `parkmatch`, abre el archivo `backend/db/schema.sql` y ejecútalo (F5).
   Crea todas las tablas. Si ya existían, las vuelve a crear.

## 2. Backend
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # ajusta DATABASE_URL con tu usuario y clave de PostgreSQL
python seed.py                     # datos de demostración (contraseña: Parkmatch1)
uvicorn app.main:app --reload      # http://localhost:8000/docs
```
Pruebas (crea la base `parkmatch_test` antes):
```bash
pytest -q
pytest --cov=app                   # cobertura
```

## 3. Frontend
```bash
cd frontend
npm install
npm run dev                        # http://localhost:5173
```

## Cuentas de demostración
- Arrendadores: rosa@parkmatch.pe · carlos@parkmatch.pe
- Arrendatarios: luis@parkmatch.pe · maria@parkmatch.pe
- Administradora: admin@parkmatch.pe (panel de moderación en `/admin`)
- Contraseña de todas: Parkmatch1

El seed también deja reservas finalizadas con calificaciones y un reporte pendiente,
para que la reputación y la moderación se puedan mostrar desde el inicio.

## Módulos del Sprint 3
| Módulo | Historias | Dónde |
|---|---|---|
| Calificaciones, reputación e historial | US-20 a US-22 | `routers/comunidad.py`, `reputacion.py`, perfil público `/usuarios/:id` |
| Filtros por precio, vehículo, techo y horario | US-10, US-12 | `GET /api/cocheras/buscar` |
| Perfil, vehículos, verificación de identidad | US-04 | `routers/perfil.py`, página `/perfil` |
| Recuperación de contraseña (enlace de un solo uso) | US-03 | `/api/auth/recuperar` y `/restablecer` |
| Bandeja de notificaciones | US-15 | campana en la cabecera, `/api/notificaciones` |
| Reportes, suspensión, disputas | US-23 a US-25 | `routers/admin.py`, página `/admin` |

Sin servidor SMTP, los correos (p. ej. recuperar contraseña) se escriben en la consola y en
`backend/correos_enviados.log`; en modo demo el enlace también aparece en pantalla.

## Notas para Windows
- Si `python seed.py` falla con *No time zone found with key America/Lima*, falta `tzdata`:
  vuelve a correr `pip install -r requirements.txt`.
- PostgreSQL 17 con pgAdmin se instala con `winget install PostgreSQL.PostgreSQL.17`.

## Pagos
La pasarela es simulada. Tarjetas de prueba: número que termina en 9995 = fondos insuficientes; en 0002 = rechazada por el banco; cualquier otro = aprobada. Los pagos en efectivo o billetera se registran a mano por el arrendador.
