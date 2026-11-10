"""Restarts a check asks for. The test runner has no Docker access in isolated mode, so a
check writes `restart-<id>.request` into the control folder and waits for
`restart-<id>.done`; the harness process watches the folder and restarts the service's
container: Docker's stop and start, or, for a track in KILLED, SIGKILL and start, so the
service gets no time to shut down. The done file holds "ok" or the error."""
from __future__ import annotations

import pathlib
import threading
import time

from harness import docker_driver as dd

POLL_SECONDS = 0.5
RESTART_TIMEOUT = 120
KILLED = ("dossier",)  # tracks whose checks ask for restarts that kill the service


def request(folder: pathlib.Path | str, timeout: float = RESTART_TIMEOUT) -> None:
    """From a check: ask for a restart and wait until it is done. Raises on failure."""
    folder = pathlib.Path(folder)
    ident = f"{time.time_ns()}"
    (folder / f"restart-{ident}.request").write_text("", encoding="utf-8")
    done = folder / f"restart-{ident}.done"
    deadline = time.monotonic() + timeout
    while not done.exists():
        if time.monotonic() > deadline:
            raise TimeoutError(f"the harness did not restart the service in {timeout:.0f}s")
        time.sleep(POLL_SECONDS)
    answer = done.read_text(encoding="utf-8")
    if answer != "ok":
        raise RuntimeError(f"restart failed: {answer}")


class Restarter:
    """While open, restart `container` whenever a request appears in `folder`, stopping it
    with `signal` when given."""

    def __init__(self, folder: pathlib.Path, container: str, signal: str | None = None):
        self.folder, self.container = folder, container
        self.command = ["docker", "restart", *(["--signal", signal] if signal else []),
                        container]
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._watch, daemon=True)

    def __enter__(self) -> "Restarter":
        self.folder.mkdir(parents=True, exist_ok=True)
        self._thread.start()
        return self

    def __exit__(self, *_exc) -> None:
        self._stop.set()
        self._thread.join(timeout=5)

    def _watch(self) -> None:
        while not self._stop.is_set():
            for asked in sorted(self.folder.glob("restart-*.request")):
                try:
                    proc = dd._run(self.command, RESTART_TIMEOUT)  # pylint: disable=protected-access
                    answer = "ok" if proc.returncode == 0 else proc.stderr.strip() or "failed"
                except dd.DockerError as exc:
                    answer = str(exc)
                asked.unlink()
                # Renamed into place so a polling check never reads a half-written answer.
                partial = asked.with_suffix(".partial")
                partial.write_text(answer, encoding="utf-8")
                partial.replace(asked.with_suffix(".done"))
            self._stop.wait(POLL_SECONDS)


def attach(stack, folder: pathlib.Path, container: str, track: str,
           seen_as: str | None = None) -> list:
    """Restart `container` on request while `stack` is open, as `track` asks. Returns the
    pytest option that names the folder as the checks see it: `seen_as` when they run in
    another filesystem."""
    stack.enter_context(Restarter(folder, container, "KILL" if track in KILLED else None))
    return ["--control-dir", seen_as or str(folder)]
