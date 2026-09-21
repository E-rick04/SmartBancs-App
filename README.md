# SmartBancs App

Este repositorio corresponde al resultado del desarrollo del reto técnico **SmartBancs App**. Se construyó un producto para demostrar el procesamiento de transferencias, considerando casos de aseguramiento de la información en escenarios inesperados.

La aplicación permite transferir entre cuentas de ejemplo, consultar el estado de cada operación y recibir recomendaciones. También analiza un archivo CSV de prueba e identifica los registros que requieren corrección. La integración con Bancs, el sistema central descrito en el reto, está simulada. El servicio de recomendaciones utiliza reglas definidas en el código; no emplea un modelo entrenado ni IA generativa.

## Enfoque de la solución

El reto exige que las transferencias respondan con rapidez y que la generación de recomendaciones no retrase ese proceso. La solución separa ambos trabajos:

1. La aplicación comprueba las cuentas y guarda la transferencia en PostgreSQL.
2. Devuelve un identificador para consultarla.
3. Dos procesos en segundo plano (*workers*) gestionan la sincronización simulada con Bancs y la generación de recomendaciones.

De este modo, la respuesta de la transferencia no espera el resultado de la recomendación. El flujo se explica con más detalle en la [documentación de arquitectura](docs/arquitectura.md).

## Requisitos

Se requiere **Docker Desktop** con Docker Compose en funcionamiento. Compose inicia la interfaz, la API, PostgreSQL y los workers.

Los puertos `5173`, `8000`, `8001` y `5432` deben estar disponibles. Si alguno está ocupado, Docker informará del conflicto al iniciar.

## Puesta en marcha

Desde una terminal ubicada en la carpeta del proyecto, se ejecutan los siguientes comandos:

```bash
docker compose up --build -d
docker compose ps
```

El primer comando construye e inicia los servicios. El segundo muestra su estado.

La interfaz queda disponible en **http://localhost:5173**. La siguiente secuencia permite verificar las funciones principales:

1. Verificar que aparezcan cinco cuentas de ejemplo, entre ellas `CUEN_001` y `CUEN_002`.
2. En **Nueva transferencia**, seleccionar dos cuentas distintas, ingresar un monto y enviar la operación.
3. Consultar el identificador generado en **Estado de transacción** y comprobar la actualización de los saldos.
4. Esperar la referencia **Bancs** simulada y la recomendación. El estado local de la transferencia y el de sincronización Bancs se presentan por separado.
5. Ejecutar el **ETL de muestra**. De las 50 filas del CSV, 31 resultan válidas y 19 se rechazan. Posteriormente aparece una recomendación para corregir los datos.

El archivo utilizado está en [etl/etl_test_transaction.csv](etl/etl_test_transaction.csv). El ETL limpia estos datos de ejemplo; no los incorpora a las cuentas ni modifica saldos.

Para detener la aplicación sin perder las transferencias guardadas:

```bash
docker compose down
```

Al volver a ejecutar `docker compose up --build -d`, PostgreSQL conserva los datos en un volumen de Docker. El comando `docker compose down -v` elimina ese volumen y sus datos.

## Organización del proyecto

| Carpeta | Qué contiene |
| --- | --- |
| `frontend/` | Interfaz web. |
| `app/` | API, acceso a PostgreSQL y workers. |
| `ai_service/` | Las reglas que generan recomendaciones para transferencias y ETL. |
| `etl/` | El CSV de ejemplo y el código que valida sus filas. |
| `sql/` | Los scripts que crean las tablas y las cuentas de ejemplo. |
| `tests/` | Pruebas automáticas del comportamiento principal. |
| `docs/` | Documentación de arquitectura, operación y alcance. |

La API recibe las solicitudes de la interfaz y devuelve los datos. Sus rutas pueden explorarse en **http://localhost:8000/docs** mientras la aplicación está en ejecución.

## Pruebas automáticas

Las pruebas utilizan una base SQLite temporal y simulan las llamadas entre servicios. No modifican la base PostgreSQL del entorno local:

```bash
docker compose build api
docker compose run --rm --no-deps api python -m pytest -v tests
```

La terminal muestra `PASSED` o `FAILED` para cada prueba y un resumen final. La suite cubre transferencias, validaciones, idempotencia, workers, ETL y recomendaciones. No mide el rendimiento bajo carga ni los bloqueos reales de PostgreSQL.

## Solución de problemas

| Síntoma | Comprobación inicial |
| --- | --- |
| La página no abre | Ejecutar `docker compose ps` y comprobar que `frontend` esté `Up`. |
| No aparecen cuentas | Consultar «Base de datos existente» más abajo. |
| El ETL devuelve un error de tabla | Consultar «Base de datos existente» más abajo. |
| La recomendación tarda o falla | Revisar `docker compose logs --tail=100 ai_worker ai api`. |
| La API no responde | Revisar `docker compose logs --tail=100 api db` y `http://localhost:8000/health`. |

### Base de datos existente

Docker ejecuta los scripts de `sql/` solo cuando crea el volumen de PostgreSQL por primera vez. Reconstruir los contenedores **no** vuelve a ejecutarlos. Si existe un volumen previo y faltan las cuentas o la tabla del ETL, los siguientes comandos aplican los scripts sin borrar los datos:

```bash
docker compose exec -T db psql -v ON_ERROR_STOP=1 -U smartbancs -d smartbancs -f /docker-entrypoint-initdb.d/002_seed.sql
docker compose exec -T db psql -v ON_ERROR_STOP=1 -U smartbancs -d smartbancs -f /docker-entrypoint-initdb.d/003_etl_run.sql
```

Si también faltan las tablas principales, debe ejecutarse antes `001_squema.sql` mediante el mismo comando, cambiando el nombre del archivo. Los scripts pueden repetirse sin duplicar las cuentas de ejemplo.

## Documentación del reto

- [Arquitectura, flujo de transferencia, Bancs, ETL e IA](docs/arquitectura.md)
- [Logs, métricas y respuesta a un incidente](docs/operacion.md)
- [Qué requisitos cubre el proyecto y qué queda pendiente](docs/entrega.md)
- [Presentación del reto técnico en PDF](presentacion/SmartBancs_Presentacion.pdf)
- [Video demostrativo en Google Drive](https://drive.google.com/file/d/1svSs8Vx06XhFb91R2dloOxUYrNnnQbpR/view?usp=drive_link)
