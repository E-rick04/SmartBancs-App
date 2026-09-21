CREATE TABLE IF NOT EXISTS cuenta (
    id SERIAL NOT NULL,
    numero_cuenta VARCHAR(30) NOT NULL,
    moneda VARCHAR(3) NOT NULL,
    saldo NUMERIC(18,2) NOT NULL DEFAULT 0,

    CONSTRAINT pk_cuentas PRIMARY KEY (id),
    CONSTRAINT uq_cuentas_numero_cuenta UNIQUE (numero_cuenta),
    CONSTRAINT ck_cuentas_saldo_no_negativo CHECK (saldo >= 0)
);

CREATE TABLE IF NOT EXISTS transaccion (
    id SERIAL NOT NULL,
    id_cuenta_origen INTEGER NOT NULL,
    id_cuenta_destino INTEGER NOT NULL,
    monto NUMERIC(18,2) NOT NULL,
    moneda VARCHAR(3) NOT NULL,
    estado VARCHAR(20) NOT NULL,
    referencia_bancs VARCHAR(50),
    clave_idempotencia VARCHAR(100) NOT NULL,
    creado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_transacciones PRIMARY KEY (id),
    CONSTRAINT fk_transacciones_cuenta_origen
        FOREIGN KEY (id_cuenta_origen) REFERENCES cuenta(id),
    CONSTRAINT fk_transacciones_cuenta_destino
        FOREIGN KEY (id_cuenta_destino) REFERENCES cuenta(id),
    CONSTRAINT uq_transacciones_clave_idempotencia UNIQUE (clave_idempotencia),
    CONSTRAINT ck_transacciones_monto_positivo CHECK (monto > 0),
    CONSTRAINT ck_transacciones_cuentas_distintas
        CHECK (id_cuenta_origen <> id_cuenta_destino)
);

CREATE TABLE IF NOT EXISTS recomendacion (
    id SERIAL NOT NULL,
    id_transaccion INTEGER NOT NULL,
    mensaje TEXT NOT NULL,
    version_modelo VARCHAR(50) NOT NULL,
    creado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_recomendaciones PRIMARY KEY (id),
    CONSTRAINT fk_recomendaciones_transaccion
        FOREIGN KEY (id_transaccion) REFERENCES transaccion(id),
    CONSTRAINT uq_recomendaciones_transaccion UNIQUE (id_transaccion)
);

CREATE TABLE IF NOT EXISTS evento_salida (
    id SERIAL NOT NULL,
    id_transaccion INTEGER NOT NULL,
    tipo_evento VARCHAR(20) NOT NULL,
    estado VARCHAR(20) NOT NULL DEFAULT 'PENDIENTE',
    intentos INTEGER NOT NULL DEFAULT 0,
    disponible_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    bloqueado_en TIMESTAMP,
    ultimo_error VARCHAR(255),

    CONSTRAINT pk_eventos_salida PRIMARY KEY (id),
    CONSTRAINT fk_eventos_salida_transaccion
        FOREIGN KEY (id_transaccion) REFERENCES transaccion(id),
    CONSTRAINT uq_eventos_salida_transaccion_tipo
        UNIQUE (id_transaccion, tipo_evento)
);

CREATE INDEX IF NOT EXISTS ix_eventos_salida_pendientes
    ON evento_salida (estado, disponible_en, id);

CREATE INDEX IF NOT EXISTS ix_transacciones_creado_en
    ON transaccion (creado_en);
