import logging
import sys
from contextvars import ContextVar

request_id_context: ContextVar[str] = ContextVar("request_id", default="-")


class RequestIdFilter(logging.Filter):
    def filter(self, record):
        record.request_id = request_id_context.get()
        return True


def configure_logging():
    logging.basicConfig(
        level=logging.INFO,
        format=(
            "%(asctime)s %(levelname)s "
            "Servicio=%(name)s id_Solicitud=%(request_id)s %(message)s"
        ),
        handlers=[logging.StreamHandler(sys.stdout)],
        force=True,
    )
    for handler in logging.getLogger().handlers:
        handler.addFilter(RequestIdFilter())
