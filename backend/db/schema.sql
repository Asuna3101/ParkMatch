-- =====================================================================
--  ParkMatch — esquema de base de datos del MVP
--  PostgreSQL 13 o superior
--
--  Cómo usarlo en pgAdmin:
--    1. Clic derecho en Databases > Create > Database…  y nómbrala  parkmatch
--    2. Selecciónala y abre  Tools > Query Tool
--    3. Abre este archivo (ícono de carpeta) o pega su contenido
--    4. Presiona Execute (F5)
--
--  El script se puede ejecutar varias veces: borra y vuelve a crear
--  todas las tablas. OJO: eso elimina los datos que hubiera.
--
--  Las clases salen del diagrama conceptual del equipo:
--    Usuario (Arrendador, Arrendatario, Administrador), Vehiculo, Cochera,
--    Ubicacion, Tarifa, Disponibilidad, Reserva, PagoSimulado, Comprobante,
--    CodigoQR, Conversacion, Mensaje, Notificacion, Incidencia_Disputa, Reporte.
-- =====================================================================

-- Extensión estándar de PostgreSQL (viene con el instalador normal).
-- Hace posible la restricción que impide las dobles reservas.
CREATE EXTENSION IF NOT EXISTS btree_gist;

DROP TABLE IF EXISTS log_auditoria            CASCADE;
DROP TABLE IF EXISTS disputa                  CASCADE;
DROP TABLE IF EXISTS reporte                  CASCADE;
DROP TABLE IF EXISTS calificacion             CASCADE;
DROP TABLE IF EXISTS notificacion             CASCADE;
DROP TABLE IF EXISTS mensaje                  CASCADE;
DROP TABLE IF EXISTS conversacion             CASCADE;
DROP TABLE IF EXISTS comprobante              CASCADE;
DROP TABLE IF EXISTS pago                     CASCADE;
DROP TABLE IF EXISTS codigo_acceso            CASCADE;
DROP TABLE IF EXISTS reserva                  CASCADE;
DROP TABLE IF EXISTS disponibilidad           CASCADE;
DROP TABLE IF EXISTS tarifa                   CASCADE;
DROP TABLE IF EXISTS foto_cochera             CASCADE;
DROP TABLE IF EXISTS ubicacion                CASCADE;
DROP TABLE IF EXISTS cochera                  CASCADE;
DROP TABLE IF EXISTS metodo_pago              CASCADE;
DROP TABLE IF EXISTS recuperacion_contrasena  CASCADE;
DROP TABLE IF EXISTS vehiculo                 CASCADE;
DROP TABLE IF EXISTS usuario                  CASCADE;

-- ---------------------------------------------------------------------
--  USUARIO  (requisitos 1 a 5, 38 y 40 · US-01 a US-04)
--  Arrendador, Arrendatario y Administrador comparten tabla; el rol
--  distingue a cada uno.
-- ---------------------------------------------------------------------
CREATE TABLE usuario (
    id              SERIAL PRIMARY KEY,
    nombre          VARCHAR(120) NOT NULL,
    correo          VARCHAR(160) NOT NULL UNIQUE,
    contrasena_hash VARCHAR(100) NOT NULL,          -- bcrypt, nunca texto plano
    telefono        VARCHAR(20),
    rol             VARCHAR(20)  NOT NULL
                    CHECK (rol IN ('arrendador', 'arrendatario', 'administrador')),
    foto_url        VARCHAR(255),
    -- Verificación básica de identidad (requisito 5)
    documento_url   VARCHAR(255),
    verificacion    VARCHAR(20)  NOT NULL DEFAULT 'sin_verificar'
                    CHECK (verificacion IN ('sin_verificar', 'pendiente', 'verificado', 'rechazado')),
    -- Consentimiento para el tratamiento de datos personales (Ley N.º 29733)
    acepto_datos_en TIMESTAMPTZ  NOT NULL DEFAULT now(),
    creado_en       TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------
--  VEHICULO  (diagrama conceptual: Usuario tiene 0..* Vehiculo)
-- ---------------------------------------------------------------------
CREATE TABLE vehiculo (
    id          SERIAL PRIMARY KEY,
    usuario_id  INTEGER     NOT NULL REFERENCES usuario(id) ON DELETE CASCADE,
    placa       VARCHAR(10) NOT NULL,
    tipo        VARCHAR(20) NOT NULL CHECK (tipo IN ('moto', 'auto', 'camioneta')),
    descripcion VARCHAR(80),                        -- marca, modelo y color
    UNIQUE (usuario_id, placa)
);

-- ---------------------------------------------------------------------
--  RECUPERACION_CONTRASENA  (requisito 3 · US-03)
--  Solo se guarda el hash del enlace; vence a las 24 horas y se usa
--  una sola vez.
-- ---------------------------------------------------------------------
CREATE TABLE recuperacion_contrasena (
    id         SERIAL PRIMARY KEY,
    usuario_id INTEGER     NOT NULL REFERENCES usuario(id) ON DELETE CASCADE,
    token_hash CHAR(64)    NOT NULL UNIQUE,
    expira_en  TIMESTAMPTZ NOT NULL,
    usado_en   TIMESTAMPTZ,
    creado_en  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------
--  METODO_PAGO  (requisitos 51 y 56 · US-26)
--  Tarjeta SIMULADA del arrendatario. El número completo se guarda
--  cifrado; el código de seguridad (CVV) no se guarda nunca.
-- ---------------------------------------------------------------------
CREATE TABLE metodo_pago (
    id             SERIAL PRIMARY KEY,
    usuario_id     INTEGER     NOT NULL REFERENCES usuario(id) ON DELETE CASCADE,
    titular        VARCHAR(80) NOT NULL,
    marca          VARCHAR(20) NOT NULL,            -- Visa, Mastercard…
    ultimos4       CHAR(4)     NOT NULL,
    vence_mes      SMALLINT    NOT NULL CHECK (vence_mes BETWEEN 1 AND 12),
    vence_anio     SMALLINT    NOT NULL,
    numero_cifrado TEXT        NOT NULL,            -- cifrado simétrico (Fernet)
    creado_en      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_metodo_pago_usuario ON metodo_pago(usuario_id);

-- ---------------------------------------------------------------------
--  COCHERA  (requisitos 6, 7, 8 y 9 · US-05, US-06)
-- ---------------------------------------------------------------------
CREATE TABLE cochera (
    id                SERIAL PRIMARY KEY,
    arrendador_id     INTEGER      NOT NULL REFERENCES usuario(id) ON DELETE CASCADE,
    titulo            VARCHAR(120) NOT NULL,
    descripcion       TEXT         NOT NULL,
    tipo_vehiculo     VARCHAR(20)  NOT NULL
                      CHECK (tipo_vehiculo IN ('moto', 'auto', 'camioneta')),
    largo_m           NUMERIC(4,2) NOT NULL CHECK (largo_m > 0),
    ancho_m           NUMERIC(4,2) NOT NULL CHECK (ancho_m > 0),
    techada           BOOLEAN      NOT NULL DEFAULT FALSE,
    precio_hora       NUMERIC(8,2) NOT NULL CHECK (precio_hora > 0),   -- tarifa base
    activa            BOOLEAN      NOT NULL DEFAULT TRUE,   -- la pausa el arrendador
    suspendida        BOOLEAN      NOT NULL DEFAULT FALSE,  -- la retira un administrador
    motivo_suspension VARCHAR(300),
    creado_en         TIMESTAMPTZ  NOT NULL DEFAULT now()
);
CREATE INDEX idx_cochera_arrendador ON cochera(arrendador_id);

-- ---------------------------------------------------------------------
--  UBICACION  (requisitos 6 y 12) — una por cochera
-- ---------------------------------------------------------------------
CREATE TABLE ubicacion (
    id         SERIAL PRIMARY KEY,
    cochera_id INTEGER       NOT NULL UNIQUE REFERENCES cochera(id) ON DELETE CASCADE,
    direccion  VARCHAR(200)  NOT NULL,
    distrito   VARCHAR(80)   NOT NULL,
    referencia VARCHAR(200),
    latitud    NUMERIC(9,6)  NOT NULL CHECK (latitud  BETWEEN -90  AND 90),
    longitud   NUMERIC(9,6)  NOT NULL CHECK (longitud BETWEEN -180 AND 180)
);
-- Índice que sostiene la búsqueda por proximidad (requisito 34)
CREATE INDEX idx_ubicacion_coordenadas ON ubicacion(latitud, longitud);

-- ---------------------------------------------------------------------
--  FOTO_COCHERA  (requisito 6: mínimo 3 fotografías por anuncio)
-- ---------------------------------------------------------------------
CREATE TABLE foto_cochera (
    id         SERIAL PRIMARY KEY,
    cochera_id INTEGER      NOT NULL REFERENCES cochera(id) ON DELETE CASCADE,
    url        VARCHAR(255) NOT NULL,
    orden      SMALLINT     NOT NULL DEFAULT 0
);
CREATE INDEX idx_foto_cochera ON foto_cochera(cochera_id);

-- ---------------------------------------------------------------------
--  TARIFA  (requisito 9 · US-06)
--  Precio distinto para una franja del día. Fuera de las franjas se
--  cobra cochera.precio_hora.
-- ---------------------------------------------------------------------
CREATE TABLE tarifa (
    id          SERIAL PRIMARY KEY,
    cochera_id  INTEGER      NOT NULL REFERENCES cochera(id) ON DELETE CASCADE,
    hora_inicio TIME         NOT NULL,
    hora_fin    TIME         NOT NULL,
    precio_hora NUMERIC(8,2) NOT NULL CHECK (precio_hora > 0),
    CHECK (hora_fin > hora_inicio)
);
CREATE INDEX idx_tarifa_cochera ON tarifa(cochera_id);

-- ---------------------------------------------------------------------
--  DISPONIBILIDAD  (requisito 10 · US-07)
--  Calendario semanal recurrente. dia_semana: 0 = lunes … 6 = domingo.
-- ---------------------------------------------------------------------
CREATE TABLE disponibilidad (
    id          SERIAL PRIMARY KEY,
    cochera_id  INTEGER  NOT NULL REFERENCES cochera(id) ON DELETE CASCADE,
    dia_semana  SMALLINT NOT NULL CHECK (dia_semana BETWEEN 0 AND 6),
    hora_inicio TIME     NOT NULL,
    hora_fin    TIME     NOT NULL,
    CHECK (hora_fin > hora_inicio)
);
CREATE INDEX idx_disponibilidad_cochera ON disponibilidad(cochera_id, dia_semana);

-- ---------------------------------------------------------------------
--  RESERVA  (requisitos 11, 21, 22, 23 y 26 · US-08, US-16 a US-19)
--
--  Estados:
--    solicitada → confirmada | rechazada | cancelada
--    confirmada → en_curso (ingreso con el código) | cancelada | finalizada
--    en_curso   → finalizada (al registrar la salida)
--
--  RIESGO R-01 (doble reserva). La restricción reserva_sin_solape hace
--  que la propia base de datos rechace dos reservas vigentes de la misma
--  cochera cuyos horarios se crucen, aunque dos solicitudes lleguen
--  exactamente al mismo tiempo.
-- ---------------------------------------------------------------------
CREATE TABLE reserva (
    id              SERIAL PRIMARY KEY,
    cochera_id      INTEGER       NOT NULL REFERENCES cochera(id) ON DELETE CASCADE,
    arrendatario_id INTEGER       NOT NULL REFERENCES usuario(id) ON DELETE CASCADE,
    inicio          TIMESTAMPTZ   NOT NULL,
    fin             TIMESTAMPTZ   NOT NULL,
    estado          VARCHAR(20)   NOT NULL DEFAULT 'solicitada'
                    CHECK (estado IN ('solicitada', 'confirmada', 'rechazada',
                                      'cancelada', 'en_curso', 'finalizada')),
    costo_total     NUMERIC(10,2) NOT NULL CHECK (costo_total >= 0),
    motivo_rechazo  VARCHAR(200),
    -- Cómo pagará el arrendatario: con su tarjeta simulada o acordándolo
    -- directamente con el arrendador (efectivo o billetera móvil)
    medio_pago      VARCHAR(20)   NOT NULL DEFAULT 'acordado'
                    CHECK (medio_pago IN ('tarjeta', 'acordado')),
    metodo_pago_id  INTEGER       REFERENCES metodo_pago(id) ON DELETE SET NULL,
    -- Uso real del espacio y penalización por exceso (requisito 26)
    ingreso_real    TIMESTAMPTZ,
    salida_real     TIMESTAMPTZ,
    minutos_exceso  INTEGER       NOT NULL DEFAULT 0 CHECK (minutos_exceso >= 0),
    cargo_exceso    NUMERIC(10,2) NOT NULL DEFAULT 0,   -- tiempo adicional usado
    penalizacion    NUMERIC(10,2) NOT NULL DEFAULT 0,   -- recargo del 10 %
    creado_en       TIMESTAMPTZ   NOT NULL DEFAULT now(),
    actualizado_en  TIMESTAMPTZ   NOT NULL DEFAULT now(),
    CHECK (fin > inicio),
    CONSTRAINT reserva_sin_solape
        EXCLUDE USING gist (
            cochera_id WITH =,
            tstzrange(inicio, fin, '[)') WITH &&
        ) WHERE (estado IN ('confirmada', 'en_curso'))
);
CREATE INDEX idx_reserva_cochera      ON reserva(cochera_id, estado);
CREATE INDEX idx_reserva_arrendatario ON reserva(arrendatario_id);

-- ---------------------------------------------------------------------
--  CODIGO_ACCESO  (requisito 25 · US-32) — el CodigoQR del diagrama
--  Se genera al confirmarse la reserva y sirve una sola vez.
-- ---------------------------------------------------------------------
CREATE TABLE codigo_acceso (
    id           SERIAL PRIMARY KEY,
    reserva_id   INTEGER     NOT NULL UNIQUE REFERENCES reserva(id) ON DELETE CASCADE,
    codigo       VARCHAR(12) NOT NULL UNIQUE,
    valido_desde TIMESTAMPTZ NOT NULL,
    valido_hasta TIMESTAMPTZ NOT NULL,
    usado_en     TIMESTAMPTZ,                      -- NULL mientras no se haya usado
    generado_en  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------
--  PAGO  (requisitos 24, 51 a 55 y 58 · US-27 a US-31) — PagoSimulado
--  Dos caminos, según lo que eligió el arrendatario al reservar:
--    · tarjeta:  la pasarela SIMULADA cobra al confirmarse la reserva.
--                Si el cobro falla, la reserva no se confirma.
--    · acordado: se paga fuera de la aplicación (efectivo o billetera) y
--                el arrendador lo marca como recibido.
--  Estados:  pendiente → pagado → reembolsado
--            pagado → por_devolver → reembolsado   (pago acordado que el
--            arrendador debe devolver tras una cancelación a tiempo)
--  No se procesa dinero real en ningún caso.
-- ---------------------------------------------------------------------
CREATE TABLE pago (
    id             SERIAL PRIMARY KEY,
    reserva_id     INTEGER       NOT NULL UNIQUE REFERENCES reserva(id) ON DELETE CASCADE,
    monto          NUMERIC(10,2) NOT NULL CHECK (monto >= 0),
    estado         VARCHAR(20)   NOT NULL DEFAULT 'pendiente'
                   CHECK (estado IN ('pendiente', 'pagado', 'por_devolver', 'reembolsado')),
    medio          VARCHAR(20)   CHECK (medio IN ('tarjeta', 'efectivo', 'billetera')),
    referencia     VARCHAR(40),                    -- código de operación de la pasarela simulada
    pagado_en      TIMESTAMPTZ,
    reembolsado_en TIMESTAMPTZ,
    registrado_por INTEGER       REFERENCES usuario(id),
    creado_en      TIMESTAMPTZ   NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------
--  COMPROBANTE  (requisito 52 · US-28)
--  Constancia digital que se emite cuando el pago queda registrado.
-- ---------------------------------------------------------------------
CREATE TABLE comprobante (
    id         SERIAL PRIMARY KEY,
    pago_id    INTEGER       NOT NULL UNIQUE REFERENCES pago(id) ON DELETE CASCADE,
    numero     VARCHAR(20)   NOT NULL UNIQUE,      -- PM-000001
    monto      NUMERIC(10,2) NOT NULL,
    medio      VARCHAR(20)   NOT NULL,
    emitido_en TIMESTAMPTZ   NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------
--  CONVERSACION y MENSAJE  (requisitos 17 y 35 · US-13)
-- ---------------------------------------------------------------------
CREATE TABLE conversacion (
    id              SERIAL PRIMARY KEY,
    cochera_id      INTEGER     NOT NULL REFERENCES cochera(id) ON DELETE CASCADE,
    arrendatario_id INTEGER     NOT NULL REFERENCES usuario(id) ON DELETE CASCADE,
    arrendador_id   INTEGER     NOT NULL REFERENCES usuario(id) ON DELETE CASCADE,
    creado_en       TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (cochera_id, arrendatario_id)
);

CREATE TABLE mensaje (
    id              SERIAL PRIMARY KEY,
    conversacion_id INTEGER     NOT NULL REFERENCES conversacion(id) ON DELETE CASCADE,
    emisor_id       INTEGER     NOT NULL REFERENCES usuario(id) ON DELETE CASCADE,
    texto           TEXT        NOT NULL CHECK (length(trim(texto)) > 0),
    leido           BOOLEAN     NOT NULL DEFAULT FALSE,
    enviado_en      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_mensaje_conversacion ON mensaje(conversacion_id, enviado_en);

-- ---------------------------------------------------------------------
--  NOTIFICACION  (requisitos 18, 19, 20 y 55 · US-14, US-15, US-31)
-- ---------------------------------------------------------------------
CREATE TABLE notificacion (
    id         SERIAL PRIMARY KEY,
    usuario_id INTEGER      NOT NULL REFERENCES usuario(id) ON DELETE CASCADE,
    tipo       VARCHAR(30)  NOT NULL,              -- mensaje, reserva, pago, moderacion…
    titulo     VARCHAR(120) NOT NULL,
    texto      VARCHAR(300) NOT NULL,
    enlace     VARCHAR(200),                       -- pantalla a la que lleva
    leida      BOOLEAN      NOT NULL DEFAULT FALSE,
    creado_en  TIMESTAMPTZ  NOT NULL DEFAULT now()
);
CREATE INDEX idx_notificacion_usuario ON notificacion(usuario_id, leida, creado_en DESC);

-- ---------------------------------------------------------------------
--  CALIFICACION  (requisitos 27, 28 y 29 · US-20, US-21)
--  Cada parte califica a la otra una sola vez por reserva finalizada.
-- ---------------------------------------------------------------------
CREATE TABLE calificacion (
    id              SERIAL PRIMARY KEY,
    reserva_id      INTEGER     NOT NULL REFERENCES reserva(id) ON DELETE CASCADE,
    autor_id        INTEGER     NOT NULL REFERENCES usuario(id) ON DELETE CASCADE,
    destinatario_id INTEGER     NOT NULL REFERENCES usuario(id) ON DELETE CASCADE,
    estrellas       SMALLINT    NOT NULL CHECK (estrellas BETWEEN 1 AND 5),
    comentario      TEXT,
    creado_en       TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (reserva_id, autor_id)
);
CREATE INDEX idx_calificacion_destinatario ON calificacion(destinatario_id);

-- ---------------------------------------------------------------------
--  REPORTE  (requisitos 31 y 32 · US-23, US-24)
--  Denuncia de una publicación; la resuelve un administrador.
-- ---------------------------------------------------------------------
CREATE TABLE reporte (
    id           SERIAL PRIMARY KEY,
    cochera_id   INTEGER     NOT NULL REFERENCES cochera(id) ON DELETE CASCADE,
    autor_id     INTEGER     NOT NULL REFERENCES usuario(id) ON DELETE CASCADE,
    motivo       VARCHAR(30) NOT NULL
                 CHECK (motivo IN ('informacion_falsa', 'fotos_enganosas', 'precio_abusivo',
                                   'inseguro', 'contenido_inapropiado', 'otro')),
    detalle      TEXT,
    estado       VARCHAR(20) NOT NULL DEFAULT 'pendiente'
                 CHECK (estado IN ('pendiente', 'procedente', 'desestimado')),
    nota         VARCHAR(300),
    resuelto_por INTEGER     REFERENCES usuario(id),
    resuelto_en  TIMESTAMPTZ,
    creado_en    TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- Una misma persona no puede tener dos reportes pendientes sobre la misma cochera
CREATE UNIQUE INDEX idx_reporte_pendiente ON reporte(cochera_id, autor_id) WHERE estado = 'pendiente';

-- ---------------------------------------------------------------------
--  DISPUTA  (requisito 33 · US-25) — la Incidencia_Disputa del diagrama
-- ---------------------------------------------------------------------
CREATE TABLE disputa (
    id           SERIAL PRIMARY KEY,
    reserva_id   INTEGER     NOT NULL REFERENCES reserva(id) ON DELETE CASCADE,
    autor_id     INTEGER     NOT NULL REFERENCES usuario(id) ON DELETE CASCADE,
    tipo         VARCHAR(20) NOT NULL CHECK (tipo IN ('reserva', 'pago', 'conducta')),
    descripcion  TEXT        NOT NULL,
    estado       VARCHAR(20) NOT NULL DEFAULT 'abierta' CHECK (estado IN ('abierta', 'resuelta')),
    resolucion   TEXT,
    resuelto_por INTEGER     REFERENCES usuario(id),
    resuelto_en  TIMESTAMPTZ,
    creado_en    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_disputa_reserva ON disputa(reserva_id);

-- ---------------------------------------------------------------------
--  LOG_AUDITORIA  (requisitos 50 y 57)
--  Registro de las operaciones sensibles: quién hizo qué y cuándo.
-- ---------------------------------------------------------------------
CREATE TABLE log_auditoria (
    id         BIGSERIAL PRIMARY KEY,
    usuario_id INTEGER     REFERENCES usuario(id) ON DELETE SET NULL,
    accion     VARCHAR(60) NOT NULL,
    entidad    VARCHAR(40) NOT NULL,
    entidad_id INTEGER,
    detalle    JSONB       NOT NULL DEFAULT '{}'::jsonb,
    creado_en  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_auditoria_entidad ON log_auditoria(entidad, entidad_id);
CREATE INDEX idx_auditoria_fecha   ON log_auditoria(creado_en DESC);
