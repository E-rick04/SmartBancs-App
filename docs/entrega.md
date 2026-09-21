# Alcance y preparación de la entrega

## Relación con el enunciado

| Requisito | Estado en este repositorio |
| --- | --- |
| API de transacciones y base de datos | Implementadas con FastAPI, PostgreSQL y scripts SQL. |
| Concurrencia y evitar condiciones de carrera | Bloqueo de cuentas en orden fijo, operación atómica e idempotencia. |
| Levantar con un comando | `docker compose up --build -d`. |
| Integración Bancs | Worker y referencia **simulados**; la estrategia para un core real está en `arquitectura.md`. |
| ETL | Limpieza y clasificación del CSV de ejemplo; recomendación posterior sobre registros rechazados. |
| IA independiente y no bloqueante | Servicio separado de reglas y worker asíncrono. No hay modelo entrenado. |
| Observabilidad | Logs, métricas Prometheus y registro de consultas lentas; no hay tablero ni alertas centralizadas. |
| Incidente y post mortem | Procedimiento teórico en `operacion.md`. |
| Pruebas automáticas | Incluidas en `tests/`; se ejecutan de forma aislada con SQLite. No cubren concurrencia real en PostgreSQL. |
| Video, presentación y evidencia formal de carga | [Presentación en PDF](../presentacion/SmartBancs_Presentacion.pdf) y [HTML](../presentacion/SmartBancs.html) disponibles. El video está grabado y se comparte por separado debido a su tamaño. No se incluye una prueba formal de carga. |

## Evidencia sugerida para una demostración

El video puede mostrar una secuencia corta: arranque con Compose; cuentas iniciales; una transferencia y cambio de saldos; estado Bancs simulado; recomendación posterior; ejecución ETL con filas rechazadas y su recomendación; métricas y logs. La [presentación](../presentacion/SmartBancs.html) puede servir de apoyo durante la exposición. El video grabado se conserva fuera de Git y puede adjuntarse a una Release de GitHub.

Si se requiere demostrar rendimiento, define una prueba reproducible con herramientas de carga, número de clientes, duración, hardware, tasa alcanzada, percentiles de latencia, errores y estado de PostgreSQL. No presentes el objetivo de 10 000 transacciones/s como resultado medido sin esa evidencia.

## Declaración de uso de IA en el desarrollo

Declaración de uso de IA en el desarrollo
Durante el desarrollo del reto técnico se utilizó OpenAI Codex como herramienta de apoyo para consultar dudas puntuales sobre el flujo de transferencias, workers y comunicación entre los distintos componentes de la aplicación. También se utilizó como apoyo para interpretar errores durante el desarrollo, especialmente en la configuración y ejecución de los servicios mediante Docker Compose.

La herramienta se empleó adicionalmente para explorar alternativas de implementación, revisar fragmentos de código, preparar algunos casos de prueba y apoyar la elaboración de la documentación. Las decisiones de arquitectura, integración y comportamiento de la solución fueron realizadas durante el desarrollo y los cambios sugeridos fueron revisados, adaptados y validados mediante la ejecución local de los servicios y las pruebas disponibles en el repositorio.
