"""Isolate scans with bounded interrupt escalation and child reaping."""
import json
import os
from pathlib import Path
import selectors
import signal
import subprocess
import sys
import tempfile
import time
from .model import Report,Finding,now,tools_available

INTERRUPT_GRACE = .75
TERMINATE_GRACE = .75


def signal_process_group(process, sig):
    try:os.killpg(process.pid,sig)
    except ProcessLookupError:pass


def run_interruptible(mode,target,options,callback,cancel):
    with tempfile.TemporaryFile() as errors:
        process=subprocess.Popen([sys.executable,'-m','modules.scanprocess'],cwd=Path(__file__).resolve().parent.parent,
                                 stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=errors,start_new_session=True)
        result=None;ready=False;abort_started=None;stage=0;buffer=bytearray()
        try:
            process.stdin.write((json.dumps(dict(mode=mode,target=target,options=options))+'\n').encode())
            process.stdin.close()
            os.set_blocking(process.stdout.fileno(),False)
            with selectors.DefaultSelector() as selector:
                selector.register(process.stdout,selectors.EVENT_READ)
                while True:
                    now_mono=time.monotonic()
                    if cancel.is_set() and abort_started is None and process.poll() is None:
                        abort_started=now_mono
                        signal_process_group(process,signal.SIGINT)
                        stage=1
                    elif abort_started is not None and process.poll() is None:
                        elapsed=now_mono-abort_started
                        if stage==1 and elapsed>=INTERRUPT_GRACE:
                            signal_process_group(process,signal.SIGTERM);stage=2
                        elif stage==2 and elapsed>=INTERRUPT_GRACE+TERMINATE_GRACE:
                            signal_process_group(process,signal.SIGKILL);stage=3
                    events=selector.select(.05)
                    for key,_ in events:
                        try:chunk=os.read(key.fd,65536)
                        except BlockingIOError:continue
                        if not chunk:
                            try:selector.unregister(key.fileobj)
                            except (KeyError,ValueError):pass
                            continue
                        buffer.extend(chunk)
                        if len(buffer)>1_000_000:
                            signal_process_group(process,signal.SIGKILL);stage=3
                            process.wait()
                            raise RuntimeError('Scan process output limit exceeded')
                        while b'\n' in buffer:
                            line,_,remaining=buffer.partition(b'\n');buffer=bytearray(remaining)
                            if not line:continue
                            message=json.loads(line)
                            if message['kind']=='ready':ready=True
                            elif message['kind']=='progress':callback(message['count'],message['target'])
                            elif message['kind']=='report':result=message['data']
                    if process.poll() is not None:
                        # Drain any complete final messages after child exit.
                        try:
                            tail=os.read(process.stdout.fileno(),65536)
                            if tail:buffer.extend(tail)
                        except (BlockingIOError,OSError):pass
                        if b'\n' in buffer:
                            continue
                        break
            process.wait()
            if result is None and abort_started is not None:
                report=Report(mode, str(target), list(options.get('categories',[])),
                              options={k:v for k,v in options.items() if k not in ('source_url','update_url')},
                              tools=[])
                report.status='cancelled';report.finished=now()
                report.incomplete_reasons.append('forced_process_termination')
                report.checks.append(dict(target=str(target),category='system',status='not_checked',tool='scanprocess'))
                report.findings.append(Finding('warning','system',str(target),'scan_aborted',
                                                'Worker wurde nach Ablauf der Abbruchfrist beendet.'))
                return report
            if result is None:
                errors.seek(0)
                raise RuntimeError('Scan process failed ('+str(process.returncode)+'): '+errors.read(2000).decode('utf-8','replace'))
            result['findings']=[Finding(**item) for item in result['findings']]
            return Report(**result)
        finally:
            if process.poll() is None:
                signal_process_group(process,signal.SIGTERM)
                try:process.wait(timeout=TERMINATE_GRACE)
                except subprocess.TimeoutExpired:
                    signal_process_group(process,signal.SIGKILL);process.wait()
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
