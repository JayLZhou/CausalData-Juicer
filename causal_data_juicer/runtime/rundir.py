"""Run directories the engine is allowed to clear, and nothing else.

Several entry points used to `shutil.rmtree(out)` whatever path the user
passed — `--out /home/me/thesis` would have deleted the thesis. Every
run-directory (re)creation now goes through :func:`prepare_run_dir`:

- a directory the engine created carries a ``.cdj-managed`` marker with its
  run id; only marked directories are ever cleared;
- clearing means an atomic move into a sibling ``.cdj-trash/`` (recoverable),
  not deletion;
- ``/``, the user's home, any symlink, and any unmarked existing directory
  are refused with instructions — there is no force flag that bypasses the
  marker or the path checks.
"""
from __future__ import annotations

import json
import os
import shutil
import uuid
from pathlib import Path

MARKER = ".cdj-managed"


class UnmanagedDirectoryError(RuntimeError):
    """Refusing to clear a directory the engine did not create."""


def _refuse_dangerous(path: Path) -> None:
    resolved = Path(os.path.realpath(path))
    if resolved == Path("/") or resolved == Path.home().resolve():
        raise UnmanagedDirectoryError(f"refusing to operate on {resolved}")
    if path.is_symlink():
        raise UnmanagedDirectoryError(f"refusing to operate through a symlink: {path}")


def prepare_run_dir(out: Path) -> Path:
    """Return a fresh, marked run directory at ``out``.

    If ``out`` exists it must carry the marker; it is then moved to
    ``.cdj-trash/<name>-<runid>`` next to it. An existing unmarked
    directory raises :class:`UnmanagedDirectoryError`.
    """
    out = Path(out)
    _refuse_dangerous(out)
    if out.exists():
        if not out.is_dir():
            raise UnmanagedDirectoryError(f"not a directory: {out}")
        marker = out / MARKER
        if not marker.is_file():
            raise UnmanagedDirectoryError(
                f"{out} exists but has no {MARKER} marker — it was not created "
                f"by this engine, so it will not be cleared. Choose another "
                f"--out or move the directory yourself.")
        old_id = json.loads(marker.read_text()).get("run_id", "unknown")
        trash = out.parent / ".cdj-trash"
        trash.mkdir(exist_ok=True)
        shutil.move(str(out), str(trash / f"{out.name}-{old_id}"))
    run_id = uuid.uuid4().hex[:12]
    out.mkdir(parents=True)
    (out / MARKER).write_text(json.dumps({"run_id": run_id}))
    return out
