"""Exec shim: apply resource limits, then become the target command.

Used by exec_backend's netns level, where cgroups are unavailable —
setrlimit is inherited across exec and enforced by the kernel.
"""

from __future__ import annotations

import argparse
import os
import resource
import sys


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--as-bytes", type=int, default=0)
    ap.add_argument("--cpu-seconds", type=int, default=0)
    ap.add_argument("--fsize-bytes", type=int, default=0)
    ap.add_argument("argv", nargs=argparse.REMAINDER)
    args = ap.parse_args()

    argv = args.argv
    if argv and argv[0] == "--":
        argv = argv[1:]
    if not argv:
        sys.exit("rlimit_exec: no command given")

    if args.as_bytes:
        resource.setrlimit(resource.RLIMIT_AS, (args.as_bytes, args.as_bytes))
    if args.cpu_seconds:
        resource.setrlimit(resource.RLIMIT_CPU, (args.cpu_seconds, args.cpu_seconds))
    if args.fsize_bytes:
        resource.setrlimit(resource.RLIMIT_FSIZE, (args.fsize_bytes, args.fsize_bytes))

    os.execvp(argv[0], argv)


if __name__ == "__main__":
    main()
