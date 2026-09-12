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
    
    # Avoid duplicate handlers if called multiple times
    if not logger.handlers:
        logger.addHandler(handler)
        
    return logger

logger = setup_logging()
