import logging
import sys
import structlog

def setup_logging():
    """
    Configures structlog for structured JSON logging.
    Hooks into standard logging so that library logs are formatted consistently.
    """
    # Structlog processes log payloads through a list of sequential processors.
    # Each processor acts as a middleware that transforms the log dictionary.
    processors = [
        # Merges thread/task-local context variables (bind_contextvars) into the log payload
        structlog.contextvars.merge_contextvars,
        # Adds the log level string (e.g. "info", "error") under the "level" key
        structlog.processors.add_log_level,
        # Adds stack trace information (if logging an exception or thread trace)
        structlog.processors.StackInfoRenderer(),
        # Formats exception traceback info nicely as a string if an exc_info is passed
        structlog.processors.format_exc_info,
        # Adds an ISO-8601 formatted timestamp under the "timestamp" key
        structlog.processors.TimeStamper(fmt="iso"),
        # Renders the final dictionary as a single-line JSON string (JSON serialization)
        structlog.processors.JSONRenderer(),
    ]

    structlog.configure(
        processors=processors,
        # PrintLoggerFactory prints output directly to stdout/stderr (ideal for containers/stdout capturing)
        logger_factory=structlog.PrintLoggerFactory(),
        # Automatically filters out logs below INFO level to maintain speed
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        cache_logger_on_first_use=True,
    )

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=logging.INFO,
    )

    # uvicorn.access prints a plain-text access log for every single request by default (e.g., 'GET /health HTTP/1.1 200').
    # We silence it to WARNING so it does not output duplicate plain text lines, ensuring that
    # uvicorn's stdout ONLY contains our structured JSON log strings.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)
