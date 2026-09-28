"""Isolate scans without a timeout so blocked network calls can be cancelled."""
import json
import os
from pathlib import Path
import selectors
import signal
import subprocess
import sys
import tempfile
from .model import Report,Finding,now


def run_interruptible(mode,target,options,callback,cancel):
    with tempfile.TemporaryFile() as errors:
        process=subprocess.Popen([sys.executable,'-m','modules.scanprocess'],cwd=Path(__file__).resolve().parent.parent,
                                 stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=errors,text=True,start_new_session=True)
        result=None;ready=False;interrupted=False
        try:
            process.stdin.write(json.dumps(dict(mode=mode,target=target,options=options))+'\n')
            process.stdin.close()
            with selectors.DefaultSelector() as selector:
                selector.register(process.stdout,selectors.EVENT_READ)
                while True:
                    if ready and cancel.is_set() and not interrupted and process.poll() is None:
                        try:process.send_signal(signal.SIGINT)
                        except ProcessLookupError:pass
                        interrupted=True
                    if not selector.select(.05):
                        if process.poll() is not None:break
                        continue
                    line=process.stdout.readline()
                    if not line:break
                    message=json.loads(line)
                    if message['kind']=='ready':ready=True
                    elif message['kind']=='progress':callback(message['count'],message['target'])
                    elif message['kind']=='report':result=message['data']
            code=process.wait()
            if result is None:
                errors.seek(0)
                raise RuntimeError('Scan process failed ('+str(code)+'): '+errors.read(2000).decode('utf-8','replace'))
            result['findings']=[Finding(**item) for item in result['findings']]
            return Report(**result)
        finally:
            if process.poll() is None:
                process.terminate()
                try:process.wait(timeout=3)
                except subprocess.TimeoutExpired:process.kill();process.wait()
            process.stdout.close()
            if not process.stdin.closed:process.stdin.close()


def main():
    from .engine import Scanner,Cancelled
    job=json.loads(sys.stdin.readline())
    def send(kind,**data):print(json.dumps(dict(kind=kind,**data)),flush=True)
    scanner=Scanner(job['mode'],job['target'],job['options'],lambda n,t:send('progress',count=n,target=t))
    def interrupt(*_):
        scanner.cancel.set()
        raise Cancelled()
    signal.signal(signal.SIGINT,interrupt)
    try:
        send('ready')
        report=scanner.run()
    except Cancelled:
        # Cancellation immediately before run() still returns a valid partial report.
        report=scanner.report;report.status='cancelled';report.finished=now();scanner.session.close()
    send('report',data=report.data())

if __name__=='__main__':main()
