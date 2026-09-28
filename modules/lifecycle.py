"""Timestamped application lifecycle, independent of scan diagnostics."""
import logging
from logging.handlers import RotatingFileHandler
import os
import signal
import threading
import time
from .model import VERSION, config_dir


def execute_logged(operation, mode):
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
        handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s',
                                              datefmt='%Y-%m-%d %H:%M:%S%z'))
        root.addHandler(handler)
    except OSError:
        # Logging must not prevent the application from running.
        if not root.handlers:
            logging.basicConfig(level=logging.WARNING)
    started = time.monotonic()
    pid = os.getpid()
    code = 1
    reason = 'unerwarteter Fehler'
    old_term = None
    received_signal = None

    def terminate(signum, frame):
        nonlocal received_signal
        received_signal = signal.Signals(signum).name
        raise SystemExit(128 + signum)

    if threading.current_thread() is threading.main_thread():
        old_term = signal.signal(signal.SIGTERM, terminate)
    logger.info('Programm gestartet | Version=%s | PID=%s | Modus=%s', VERSION, pid, mode)
    try:
        code = operation()
        code = 0 if code is None else code
        reason = {0: 'normal beendet', 1: 'Prüfung mit Fehlerbefunden',
                  2: 'Fehler oder unvollständige Prüfung', 130: 'Benutzerabbruch (Strg+C)'}.get(code, 'Exit-Code zurückgegeben')
        return code
    except KeyboardInterrupt:
        code = 130
        reason = 'Benutzerabbruch (Strg+C)'
        return code
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else (0 if exc.code is None else 1)
        reason = 'Signal ' + received_signal if received_signal else 'SystemExit'
        raise
    except Exception as exc:
        reason = 'unbehandelte Ausnahme: ' + type(exc).__name__
        raise
    finally:
        logger.info('Programm beendet | Version=%s | PID=%s | Modus=%s | Grund=%s | Exit-Code=%s | Laufzeit=%.3fs',
                    VERSION, pid, mode, reason, code, time.monotonic() - started)
        if old_term is not None:
            signal.signal(signal.SIGTERM, old_term)
        if handler is not None:
            root.removeHandler(handler)
            handler.close()
        root.setLevel(previous_level)
        logger.setLevel(previous_logger_level)
