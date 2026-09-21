# Operación, observabilidad e incidente simulado

## Qué mirar durante la ejecución

```bash
docker compose ps
docker compose logs --tail=100 api db worker ai_worker ai
```

La API expone métricas en `http://localhost:8000/metrics`. Entre las disponibles están el número de peticiones a transferencias por estado, la duración de transferencias, la espera para bloquear cuentas, la duración de consultas a la BD y los errores de base de datos. PostgreSQL registra esperas de bloqueo y consultas de más de 200 ms. El código registra transferencias exitosas, rechazos, fallos de workers y consultas lentas.

Para seguir una transferencia, anota su **ID** y la `Idempotency-Key` usada al crearla. La clave aparece como `id_Solicitud` en los logs de la API; los workers registran el ID de transacción. Son identificadores distintos, así que se correlacionan consultando la transacción. No hay trazas distribuidas completas ni un tablero de alertas instalado.

| Señal | Qué puede indicar |
| --- | --- |
| Aumenta la duración de transferencias | Espera en BD, bloqueo entre cuentas o saturación de la API. |
| Aumenta `lock_wait` | Muchas operaciones compiten por las mismas cuentas. |
| Crecen errores `deadlock`, `lock_timeout` o `pool_or_db_timeout` | Conflicto de bloqueos o falta de conexiones disponibles. |
| Hay eventos `FALLIDO` | Bancs simulado o IA no completaron una tarea posterior. |
| Suben las consultas lentas de PostgreSQL | Una consulta o bloqueo necesita revisión. |

Las métricas describen lo que ocurre en este proceso local. Para una operación real se necesitarían recolección central, tableros, alertas, retención de logs y pruebas de carga con objetivos medibles.

## Incidente simulado: quincena y transferencias lentas

**Situación:** suben la latencia, los timeouts de BD y los posibles deadlocks. El objetivo inicial es estabilizar el servicio sin perder ni duplicar movimientos.

1. **Confirmar el alcance.** Revisar `docker compose ps`, salud de API y BD, métricas de duración y errores, y la hora en que comenzó el problema.
2. **Localizar el cuello de botella.** Buscar en los logs `Solicitud lenta`, `Cuentas_bloqueadas`, `deadlock`, `lock_timeout` y `pool_or_db_timeout`. En PostgreSQL, inspeccionar sesiones activas y esperas:

   ```bash
   docker compose exec -T db psql -U smartbancs -d smartbancs -c "SELECT pid, state, wait_event_type, wait_event, now() - query_start AS duration, left(query, 120) AS query FROM pg_stat_activity WHERE datname = 'smartbancs' AND pid <> pg_backend_pid() ORDER BY query_start;"
   ```

3. **Contener.** Si la base está saturada, limitar temporalmente la entrada de nuevas solicitudes en el punto de acceso y priorizar las operaciones ya aceptadas. Si una consulta concreta quedó bloqueada, un operador puede cancelar esa consulta tras identificar su `pid` y evaluar su efecto. Terminar sesiones o aumentar límites a ciegas puede agravar el incidente.
4. **Evitar duplicados.** El usuario no debe gestionar claves técnicas. Si el resultado de una transferencia es incierto, el equipo de operaciones debe comprobar primero su estado antes de repetirla. En un sistema con reintentos automáticos, el frontend o la pasarela debe conservar y reutilizar la misma `Idempotency-Key` para esa operación. El frontend de este MVP genera una clave por envío y aún no implementa ese reintento automático seguro.
5. **Verificar la recuperación.** Comprobar nuevas transferencias, saldos, métricas y estados de eventos. Comparar las operaciones aceptadas con los eventos procesados; escalar diferencias pendientes.

Los tiempos de bloqueo y de consulta configurados en `app/database.py` hacen que algunas esperas terminen con error en vez de quedar indefinidas. No sustituyen la investigación de causa raíz.

## Escalamiento y post mortem

### Escalamiento durante el incidente

Ante el aumento de latencia y timeouts, el responsable de la API coordinaría el incidente y solicitaría apoyo al responsable de PostgreSQL para revisar conexiones, consultas y bloqueos. Se involucraría al equipo de infraestructura si existe saturación de CPU, memoria, red o capacidad de los contenedores. El equipo de Bancs participaría si hay operaciones confirmadas localmente sin acuse del core; el del servicio de recomendaciones, si también se acumulan tareas de IA. Cada equipo debería registrar qué comprobó y qué cambios realizó para que la investigación posterior tenga una línea de tiempo confiable.

### Estructura propuesta del informe post mortem

1. **Resumen e impacto:** qué ocurrió, cuándo comenzó y terminó, cuántas solicitudes fallaron o se retrasaron y si hubo operaciones cuyo estado requirió conciliación.
2. **Línea de tiempo:** alertas, síntomas observados, decisiones, acciones de contención y momento de recuperación, con horas y responsables.
3. **Evidencia y causa raíz:** métricas de latencia y errores, logs, consultas lentas, conexiones ocupadas y bloqueos. Se distinguiría la causa confirmada de las hipótesis pendientes; el escenario por sí solo no demuestra que haya ocurrido un deadlock.
4. **Respuesta y recuperación:** medidas aplicadas, efecto de cada una, verificación de saldos y eventos, y tiempo necesario para restablecer el servicio.
5. **Acciones de mejora:** tareas preventivas, responsable, fecha objetivo y forma de comprobar que cada cambio funciona. El informe se centraría en fallos del sistema y del proceso, no en culpar a personas.

### Acciones preventivas propuestas

| Ámbito | Medida | Cómo comprobarla |
| --- | --- | --- |
| Infraestructura | Monitorear conexiones, CPU, memoria, latencia y bloqueos; crear alertas antes de agotar la capacidad. | Simular carga y verificar que las alertas llegan con tiempo para actuar. |
| Infraestructura | Ajustar el número de instancias y conexiones disponibles según mediciones, con límites de entrada para evitar que un pico sature PostgreSQL. | Repetir una prueba de carga y revisar tasa de errores, tiempos de respuesta y uso de conexiones. |
| Infraestructura | Preparar copias de seguridad y practicar la recuperación y conciliación de operaciones. | Ejecutar un ejercicio controlado de restauración y comparar transacciones y saldos. |
| Código | Revisar consultas lentas e índices; mantener las transacciones de BD breves y el bloqueo de cuentas en un orden fijo. | Comparar tiempos de consulta y bloqueos antes y después del cambio. |
| Código | Conservar la misma clave de idempotencia en reintentos automáticos y evitar repetir una operación de resultado incierto sin consultar su estado. | Probar reintentos, timeouts y respuestas duplicadas sin duplicar transferencias. |
| Código | Mantener Bancs e IA fuera del camino principal y controlar reintentos y tareas fallidas de los workers. | Forzar fallos de esos servicios y comprobar que las transferencias locales responden y que las tareas se recuperan. |

Estas medidas son propuestas para evitar que se repita el incidente simulado; requieren implementación y pruebas antes de considerarse controles operativos del sistema.
