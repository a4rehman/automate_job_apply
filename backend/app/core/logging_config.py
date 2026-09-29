import logging
import re
import sys

class SensitiveDataFilter(logging.Filter):
    """Filter out passwords, tokens, API keys, and authorization headers from logs."""
    PATTERNS = [
        (re.compile(r'(password|passwd|secret|token|api[_-]?key)["\']?\s*[:=]\s*["\']?([^"\'\s,]+)', re.IGNORECASE), r'\1: [REDACTED]'),
        (re.compile(r'Bearer\s+[A-Za-z0-9\-\._~\+\/]+=*', re.IGNORECASE), 'Bearer [REDACTED]'),
        (re.compile(r'sk-[a-zA-Z0-9]{20,}', re.IGNORECASE), 'sk-[REDACTED]'),
    ]

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            for pattern, repl in self.PATTERNS:
                record.msg = pattern.sub(repl, record.msg)
        if record.args:
            # Clean string arguments if any
            new_args = []
            for arg in record.args:
                if isinstance(arg, str):
                    for pattern, repl in self.PATTERNS:
                        arg = pattern.sub(repl, arg)
                new_args.append(arg)
            record.args = tuple(new_args)
        return True

def setup_logging():
    logger = logging.getLogger("job_agent")
    logger.setLevel(logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.INFO)
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    handler.setFormatter(formatter)
    handler.addFilter(SensitiveDataFilter())

    # Windows consoles default to a legacy codepage (cp1252), which makes any
    # non-ASCII log line (emoji, accented characters) raise inside the logging
    # handler. Reconfigure to UTF-8 so logs never break a run.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    # A logging failure must never abort a production cycle.
    logging.raiseExceptions = False

    # Persist a rotating log file as well as stdout. The hourly Actions worker
    # needs durable per-run logs to debug a failure after the console is gone.
    # Any failure here is swallowed: logs must never block a run.
    try:
        import os
        from logging.handlers import RotatingFileHandler

        log_dir = os.path.join(os.getcwd(), "logs")
        os.makedirs(log_dir, exist_ok=True)
        file_handler = RotatingFileHandler(
            os.path.join(log_dir, "automation.log"),
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(formatter)
        file_handler.addFilter(SensitiveDataFilter())
        handlers = [handler, file_handler]
    except Exception:
        handlers = [handler]

    # Avoid duplicate handlers if called multiple times
    if not logger.handlers:
        for h in handlers:
            logger.addHandler(h)

    return logger

logger = setup_logging()
