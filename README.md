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
- Contraseña de todas: Parkmatch1

## Pagos
La pasarela es simulada. Tarjetas de prueba: número que termina en 9995 = fondos insuficientes; en 0002 = rechazada por el banco; cualquier otro = aprobada. Los pagos en efectivo o billetera se registran a mano por el arrendador.
