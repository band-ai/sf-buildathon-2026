"""The mock web a Dossier run starts beside the service, so it never reaches the internet.

`start` returns None for a track with no `web/Dockerfile`. Otherwise the mock
serves the corpus `corpus_dir` picks, the service is given `service_env`, and the suites
get `pytest_args`, which point them at the same corpus.
"""
from __future__ import annotations

import json
import os
import pathlib
import time
import uuid
from dataclasses import dataclass

from harness import docker_driver as dd
from harness.challenges import ROOT, challenge_dir

PORT = 8080
PROVIDERS = ("nimble", "tavily", "kernel", "browserbase")
BROWSERS = ("kernel", "browserbase")   # served beside the search providers, never one
QUESTIONS_TOKEN = "mock-questions-token"  # the bot's question-API token; not a secret
PREVIOUS_TOKEN = "mock-questions-token-previous"   # an upgrade source's, beside it
MODEL_TOKEN = "mock-model-token"          # the bot's model-proxy token; not a secret
# Organizer keys the model proxy forwards with. They reach the mock, never the service.
MODEL_KEYS = ("ANTHROPIC_API_KEY", "FEATHERLESS_API_KEY")
HEALTH = ("import urllib.request as u;"
          f"u.urlopen('http://127.0.0.1:{PORT}/_mock/health', timeout=2).read()")


@dataclass
class MockWeb:  # pylint: disable=too-many-instance-attributes
    """A running mock: `service_url` is where the service reaches it, `test_url` the suites."""
    container: str
    service_url: str
    test_url: str
    token: str = ""
    network: str | None = None
    mode: str = dd.HOST
    owns_network: bool = False
    track: str = "dossier"


def corpus_dir(track: str) -> pathlib.Path:
    """Organizer sealed corpus, else the judges' copy, else the kickoff sample."""
    challenge = ROOT / "challenges" / track
    for found in (challenge / "reference" / "corpus-sealed",
                  ROOT / "harness" / "keys" / f"{track}-corpus"):
        if found.is_dir():
            return found
    return challenge / "web" / "corpus" / "sample"


def _web(track: str, root: pathlib.Path | None) -> pathlib.Path:
    """The track's web/ folder, in `root` when given, else in this tree."""
    return (pathlib.Path(root) / "challenges" / track if root else challenge_dir(track)) / "web"


def config(track: str, root: pathlib.Path | None = None) -> dict:
    """What a track's mock serves, from its `web/mock.json`: the providers, and whether it
    also serves the question API. Without the file: Dossier's five providers, no questions."""
    path = _web(track, root) / "mock.json"
    found = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    return {"providers": tuple(found.get("providers", PROVIDERS)),
            "questions": bool(found.get("questions")), "model": bool(found.get("model"))}


def has_web(track: str, root: pathlib.Path | None = None) -> bool:
    """Whether the track ships a mock web. Decided from what ships: the mock's Dockerfile."""
    return (_web(track, root) / "Dockerfile").is_file()


def start(track: str, *, mode: str, network: str | None) -> MockWeb | None:
    """Build and start the mock. Isolated: on `network`. Host: on a fresh bridge network
    that the service joins too, with the port published on 127.0.0.1 for the host tests."""
    if not has_web(track):
        return None
    image = dd.build_image(challenge_dir(track) / "web", tag=f"df-{track}-mockweb")
    name, token = f"df-web-{uuid.uuid4().hex[:12]}", uuid.uuid4().hex
    args = ["docker", "run", "-d", "--name", name, "-e", f"MOCK_ADMIN_TOKEN={token}",
            "-e", f"QUESTIONS_TOKEN={QUESTIONS_TOKEN}", "-e", f"MODEL_TOKEN={MODEL_TOKEN}",
            "-e", f"QUESTIONS_TOKEN_PREVIOUS={PREVIOUS_TOKEN}",
            "-v", f"{corpus_dir(track)}:/data/corpus:ro"]
    owns = mode == dd.HOST
    port = dd.free_port() if owns else None
    if owns:
        network = f"df-web-net-{uuid.uuid4().hex[:12]}"
        if dd._run(["docker", "network", "create", network], 60).returncode:  # pylint: disable=protected-access
            raise dd.DockerError(f"could not create network {network}")
        args += ["-p", f"127.0.0.1:{port}:{PORT}"]
    model = config(track)["model"]
    if model:
        # Passed by name only, so the values never appear in the command line.
        args += [arg for key in MODEL_KEYS if os.environ.get(key) for arg in ("-e", key)]
        if os.environ.get("MODEL_BUDGET_USD"):
            args += ["-e", "MODEL_BUDGET_USD"]
    args += ["--network", network or dd.INTERNAL_NETWORK, image]
    service_url = f"http://{name}:{PORT}"
    m = MockWeb(name, service_url, f"http://127.0.0.1:{port}" if owns else service_url,
                token, network, mode, owns, track)
    try:  # any exit, a KeyboardInterrupt included, must not leave the mock or its network
        proc = dd._run(args, 120)  # pylint: disable=protected-access
        if proc.returncode:
            raise dd.DockerError(f"docker run failed: {proc.stderr}")
        if model and not owns:
            # The internal network has no route out; the model proxy needs one. The service
            # stays internal-only, so the proxy is its only way to a model.
            proc = dd._run(["docker", "network", "connect", "bridge", name], 60)  # pylint: disable=protected-access
            if proc.returncode:
                raise dd.DockerError(f"could not give the model proxy a route out: {proc.stderr}")
        _wait_healthy(m)
    except BaseException:
        stop(m)
        raise
    return m


def _wait_healthy(m: MockWeb, timeout: float = 30.0) -> None:
    """Poll the mock from inside its own container, which works on an internal network."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not dd.container_running(m.container):
            raise dd.DockerError(f"mock web exited at startup.\n{dd.logs(m.container)}")
        if not dd._run(["docker", "exec", m.container, "python", "-c", HEALTH], 30).returncode:  # pylint: disable=protected-access
            return
        time.sleep(0.25)
    raise dd.DockerError(f"mock web not healthy within {timeout:.0f}s.\n{dd.logs(m.container)}")


def service_env(m: MockWeb, previous: bool = False) -> dict[str, str]:
    """What the service under test is given, or with `previous` an earlier stage's service
    started beside it as an upgrade source. The admin token is never among it."""
    env = {"PORT": str(dd.CONTAINER_PORT)}
    served = config(m.track)
    for name in served["providers"]:
        env[f"{name.upper()}_API_KEY"] = f"mock-{name}-key"
        env[f"{name.upper()}_BASE_URL"] = f"{m.service_url}/{name}"
    if served["questions"]:
        env.update(QUESTIONS_URL=f"{m.service_url}/questions",
                   QUESTIONS_TOKEN=PREVIOUS_TOKEN if previous else QUESTIONS_TOKEN)
    if served["model"]:
        env.update(MODEL_BASE_URL=f"{m.service_url}/model/v1", MODEL_API_KEY=MODEL_TOKEN)
    return env


def pytest_args(m: MockWeb, track: str) -> list[str]:
    """Options the Dossier suites need. In isolated mode the runner sees the repo at /work,
    its working directory, so the corpus is named relative to the repo."""
    corpus = corpus_dir(track)
    shown = corpus.relative_to(ROOT) if m.mode == dd.ISOLATED else corpus
    if config(track)["questions"]:
        return ["--questions-url", f"{m.test_url}/questions", "--questions-admin-token",
                m.token, "--web-corpus", str(shown)]
    return ["--web-url", m.test_url, "--web-admin-token", m.token, "--web-corpus", str(shown)]


def stop(m: MockWeb) -> None:
    """Remove the container, and the network when `start` made it."""
    dd.stop(m.container)
    if m.owns_network:
        dd._run(["docker", "network", "rm", m.network], 60)  # pylint: disable=protected-access
