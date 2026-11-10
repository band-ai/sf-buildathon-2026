"""Where a challenge lives. The organizer tree and every export share one layout."""
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent


def challenge_dir(name: str) -> pathlib.Path:
    """The folder holding one challenge's specs, tests and organizer material."""
    return ROOT / "challenges" / name


def service_dir(folder: pathlib.Path | str) -> pathlib.Path:
    """The service in a stage folder, beside artifacts or directly at the root."""
    folder = pathlib.Path(folder)
    if (folder / 'Dockerfile').is_file():
        return folder
    return folder / 'service' if (folder / 'service').is_dir() else folder


def available() -> tuple[str, ...]:
    """Every challenge in this tree. An export holds only its hackathon's and the toy."""
    folder = ROOT / "challenges"
    return tuple(sorted(p.name for p in folder.iterdir()
                        if (p / "spec").is_dir() and (p / "test").is_dir()))


def graded() -> tuple[str, ...]:
    """The challenges a submission can be judged on: all but the practice one."""
    return tuple(name for name in available() if name != "toy")


def asset_files(folder: pathlib.Path) -> list[pathlib.Path]:
    """The files of a public challenge asset folder that ship: source, docs, patches, JSON
    and Dockerfiles, never dotfiles or caches. Both exports and the judging packet use it."""
    return sorted(path for path in folder.rglob('*')
                  if path.is_file() and (path.suffix in ('.py', '.md', '.patch', '.json')
                                         or path.name == 'Dockerfile')
                  and not any(part.startswith('.') or part == '__pycache__'
                              for part in path.relative_to(folder).parts))


def config(name: str, root: pathlib.Path | None = None) -> dict:
    """The organizer data in `challenge.json`: public test shares and validation rows."""
    folder = pathlib.Path(root) / "challenges" / name if root else challenge_dir(name)
    return json.loads((folder / "challenge.json").read_text())
