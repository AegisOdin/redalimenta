import logging
import sys
from contextvars import ContextVar

from pythonjsonlogger.json import JsonFormatter

request_id: ContextVar[str] = ContextVar("request_id", default="-")


class _Ctx(logging.Filter):
    def filter(self, record):
        record.request_id = request_id.get()
        return True


def setup(name: str = "redalimenta") -> logging.Logger:
    h = logging.StreamHandler(sys.stdout)
    h.setFormatter(JsonFormatter("%(asctime)s %(levelname)s %(name)s %(message)s %(request_id)s",
                                 rename_fields={"asctime": "ts", "levelname": "level"}))
    h.addFilter(_Ctx())
    root = logging.getLogger()
    root.handlers = [h]
    root.setLevel(logging.INFO)
    return logging.getLogger(name)
