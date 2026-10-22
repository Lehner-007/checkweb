"""Exec the Acorn parser with Linux parent-death cleanup for scan workers."""
import ctypes
import os
import signal
import sys


def main():
    if len(sys.argv) < 2:
        return 2
    parent_pid = os.getppid()
    libc = ctypes.CDLL(None, use_errno=True)
    # PR_SET_PDEATHSIG ensures a hard-killed scan worker cannot orphan Node.
    if libc.prctl(1, signal.SIGKILL, 0, 0, 0) != 0:
        return 3
    if os.getppid() != parent_pid:
        return 4
    executable, *arguments = sys.argv[1:]
    os.execve(executable, [executable, *arguments], os.environ)
    return 5


if __name__ == '__main__':
    raise SystemExit(main())
