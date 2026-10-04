"""Timestamped application lifecycle, independent of scan diagnostics."""
import logging
from logging.handlers import RotatingFileHandler
import os
import signal
import threading
import time
from .model import VERSION, config_dir, settings

from .i18n import Strings

_log_strings = None


class SessionFormatter(logging.Formatter):
    def format(self,record):
        text=super().format(record)
        if getattr(record,'session_start',False):
            line='='*72
            return '\n'+line+'\n'+text+'\n'+line
        return text


def set_log_language(language):
    global _log_strings
    _log_strings = Strings(language)


def log_text(key, **values):
    global _log_strings
    if _log_strings is None:
        set_log_language(settings()['language'])
    return _log_strings(key, **values)


def execute_logged(operation, mode, language=None):
    set_log_language(language or settings()['language'])
    root = logging.getLogger()
    logger = logging.getLogger('checkweb.lifecycle')
    previous_level = root.level
    previous_logger_level = logger.level
    logger.setLevel(logging.INFO)
    root.setLevel(logging.WARNING)
    handler = None
    try:
        directory = config_dir() / 'logs'
        directory.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(directory / 'checkweb.log', maxBytes=1_000_000,
                                      backupCount=2, encoding='utf-8')
        handler.setFormatter(SessionFormatter('%(asctime)s %(levelname)s %(message)s',
                                             datefmt='%d.%m.%Y %H:%M:%S'))
        root.addHandler(handler)
    except OSError:
        # Logging must not prevent the application from running.
        if not root.handlers:
            logging.basicConfig(level=logging.WARNING)
    started = time.monotonic()
    pid = os.getpid()
    code = 1
    reason = 'log_unexpected'
    detail = ''
    old_term = None
    received_signal = None

    def terminate(signum, frame):
        nonlocal received_signal
        received_signal = signal.Signals(signum).name
        raise SystemExit(128 + signum)

    if threading.current_thread() is threading.main_thread():
        old_term = signal.signal(signal.SIGTERM, terminate)
    logger.info(log_text('log_started', version=VERSION, pid=pid, mode=log_text('log_local') if mode=='CLI lokal' else mode),extra={'session_start':True})
    try:
        code = operation()
        code = 0 if code is None else code
        reason = {0: 'log_normal', 1: 'log_findings',
                  2: 'log_failed', 130: 'log_interrupt'}.get(code, 'log_exit')
        return code
    except KeyboardInterrupt:
        code = 130
        reason = 'log_interrupt'
        return code
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else (0 if exc.code is None else 1)
        reason = 'log_signal' if received_signal else 'log_system_exit'
        detail = received_signal or ''
        raise
    except Exception as exc:
        reason = 'log_exception'
        detail = type(exc).__name__
        raise
    finally:
        logger.info(log_text('log_ended', version=VERSION, pid=pid,
                             mode=log_text('log_local') if mode=='CLI lokal' else mode,
                             reason=log_text(reason, detail=detail), code=code,
                             duration=time.monotonic() - started))
        if old_term is not None:
            signal.signal(signal.SIGTERM, old_term)
        if handler is not None:
            root.removeHandler(handler)
            handler.close()
        root.setLevel(previous_level)
        logger.setLevel(previous_logger_level)
