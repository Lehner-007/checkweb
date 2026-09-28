"""Edit the active log without replacing the file held by logging handlers."""
from contextlib import ExitStack
from pathlib import Path
import logging
import os

class LogChangedError(Exception):
    pass

def read_log(path):
    try:return Path(path).read_bytes()
    except FileNotFoundError:return b''

def save_log(path,text,expected):
    path=Path(path)
    # Serialize against this application's logging and keep the open inode intact.
    with ExitStack() as stack:
        loggers=[logging.getLogger()]+[v for v in logging.Logger.manager.loggerDict.values() if isinstance(v,logging.Logger)]
        handlers={h for logger in loggers for h in logger.handlers if isinstance(h,logging.FileHandler) and Path(h.baseFilename)==path.resolve()}
        for handler in sorted(handlers,key=id):
            handler.acquire();stack.callback(handler.release);handler.flush()
        if read_log(path)!=expected:raise LogChangedError()
        path.parent.mkdir(parents=True,exist_ok=True)
        data=text.encode('utf-8')
        with path.open('wb') as stream:
            stream.write(data);stream.flush();os.fsync(stream.fileno())
        return data
