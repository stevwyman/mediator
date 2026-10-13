import logging
import re

_UUID = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)


class RedactingFormatter(logging.Formatter):
    """Strip negotiation tokens from the formatted log line, including tracebacks."""

    def format(self, record):
        return _UUID.sub("[redacted]", super().format(record))
