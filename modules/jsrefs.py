"""Bounded, data-only JavaScript parsing through the system Acorn package."""
import json
import os
from pathlib import Path
import shutil
import selectors
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent.parent
HELPER = ROOT / 'modules' / 'jsparser.cjs'
MAX_SOURCE_BYTES = 1_000_000
MAX_OUTPUT_BYTES = 256_000
PARSER_TIMEOUT = 2.0


class ParserUnavailable(Exception):
    pass


class ParserLimit(Exception):
    pass


def parse(source, mode='auto', cancel=None):
    """Return Acorn diagnostics and only statically certain GET/HEAD references.

    ``mode`` is ``script``, ``module`` or ``auto``. The inspected text is passed
    as JSON data; it is never evaluated, imported or executed.
    """
    node = shutil.which('node')
    if not node:
        raise ParserUnavailable('nodejs')
    raw = source.encode('utf-8') if isinstance(source, str) else bytes(source)
    if len(raw) > MAX_SOURCE_BYTES:
        raise ParserLimit('source_size')
    if cancel is not None and cancel.is_set():
        raise InterruptedError
    payload = json.dumps({'source': raw.decode('utf-8', 'replace'), 'mode': mode}).encode()
    env = os.environ.copy()
    for key in ('NODE_OPTIONS', 'NODE_PATH'):
        env.pop(key, None)
    started = time.monotonic()
    command = [node, '--max-old-space-size=96', str(HELPER)]
    # Linux scan workers may be force-killed after their interrupt grace
    # period. Keep the parser in its own group for local cleanup, while the
    # launcher makes the parser die with its worker if that worker is SIGKILLed.
    if sys.platform.startswith('linux'):
        command = [sys.executable, str(ROOT / 'modules' / 'jsparser_launcher.py'), *command]
    process = subprocess.Popen(command,
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.DEVNULL, start_new_session=True, env=env)
    completed = False
    output = bytearray()
    input_offset = 0
    stdout_open = True
    try:
        os.set_blocking(process.stdin.fileno(), False)
        os.set_blocking(process.stdout.fileno(), False)
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdin, selectors.EVENT_WRITE, 'stdin')
            selector.register(process.stdout, selectors.EVENT_READ, 'stdout')
            while True:
                if cancel is not None and cancel.is_set():
                    raise InterruptedError
                remaining = started + PARSER_TIMEOUT - time.monotonic()
                if remaining <= 0:
                    raise ParserLimit('parser_timeout')
                if process.poll() is not None and input_offset < len(payload):
                    # The parser exited before consuming the complete request.
                    raise RuntimeError('parser_process')
                if process.poll() is not None and not stdout_open:
                    break
                for key, _ in selector.select(min(remaining, 0.05)):
                    if key.data == 'stdin':
                        try:
                            input_offset += os.write(process.stdin.fileno(), payload[input_offset:])
                        except BlockingIOError:
                            continue
                        except BrokenPipeError as exc:
                            raise RuntimeError('parser_process') from exc
                        if input_offset == len(payload):
                            selector.unregister(process.stdin)
                            process.stdin.close()
                    else:
                        try:
                            chunk = os.read(process.stdout.fileno(), 65536)
                        except BlockingIOError:
                            continue
                        if not chunk:
                            selector.unregister(process.stdout)
                            stdout_open = False
                            continue
                        output.extend(chunk)
                        if len(output) > MAX_OUTPUT_BYTES:
                            raise ParserLimit('parser_output')
        if process.returncode:
            raise RuntimeError('parser_process')
        result = json.loads(output)
        completed = True
        return result
    finally:
        process.stdin.close()
        if not completed:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        process.wait()
        process.stdout.close()


def requests_in(text, mode='auto', cancel=None):
    """Compatibility generator yielding (literal URL, source line)."""
    result = parse(text, mode, cancel)
    if result.get('ok'):
        for item in result.get('refs', ()):
            yield item['url'], item['line']
