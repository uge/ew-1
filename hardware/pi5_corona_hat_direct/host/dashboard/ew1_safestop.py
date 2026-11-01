#!/usr/bin/env python3
"""ew-1 safe-stop: GPIO24 low -> PWM ch2/ch3 disable -> polarity normal -> GPIO25 low.

  ew1_safestop.py               safe-stop unless ANOTHER process holds the HV lock (used by systemd ExecStopPost)
  ew1_safestop.py --force       safe-stop unconditionally (manual use)
  ew1_safestop.py --watch-stdin dead-man for the dashboard: block until stdin closes (the dashboard
                                exited or was killed, even by SIGKILL) or SIGTERM, then safe-stop
                                unless a process other than the dashboard holds the HV lock.

Uses stage7_ramp.safe_stop() (the same code path as every ramp run). It only ever drives
outputs LOW and disables PWM, so it is always safe to run.
"""
import os
import signal
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))      # ~/ on ew-1, host/ in the repo
import stage7_ramp as R                         # noqa: E402


def lock_holder_pids(path=R.LOCK_PATH):
    """PIDs holding an flock on path, from /proc/locks (does not take the lock)."""
    try:
        st = os.stat(path)
    except FileNotFoundError:
        return []
    want = (os.major(st.st_dev), os.minor(st.st_dev), st.st_ino)
    pids = []
    try:
        with open("/proc/locks") as f:
            for line in f:
                parts = line.split()
                if "->" in parts:          # blocked waiter, not a holder
                    continue
                if len(parts) < 6 or parts[1] != "FLOCK":
                    continue
                try:
                    mj, mn, ino = parts[5].split(":")
                    if (int(mj, 16), int(mn, 16), int(ino)) == want:
                        pids.append(int(parts[4]))
                except ValueError:
                    continue
    except OSError:
        pass
    return pids


def log(m):
    print(f"[ew1_safestop {time.strftime('%H:%M:%S')}] {m}", flush=True)


def conditional_stop(allowed_pids=()):
    others = [p for p in lock_holder_pids() if p not in allowed_pids and p != os.getpid()]
    if others:
        log(f"HV lock held by other process(es) {others}; not touching outputs (they own the safe-stop)")
        return False
    R.safe_stop(log)
    return True


def main():
    args = sys.argv[1:]
    if "--force" in args:
        R.safe_stop(log); return 0
    if "--watch-stdin" in args:
        parent = os.getppid()
        signal.signal(signal.SIGINT, signal.SIG_IGN)     # Ctrl-C belongs to the dashboard
        def on_term(*_):
            log("SIGTERM"); conditional_stop((parent,)); os._exit(0)
        signal.signal(signal.SIGTERM, on_term)
        log(f"dead-man armed for pid {parent}")
        try:
            while sys.stdin.buffer.read(4096):
                pass
        except Exception:
            pass
        log(f"dashboard pid {parent} gone (stdin closed)")
        conditional_stop((parent,))
        return 0
    return 0 if conditional_stop() else 1


if __name__ == "__main__":
    sys.exit(main())
