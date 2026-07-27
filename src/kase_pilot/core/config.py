"""Project path configuration for KASE Pilot."""

from dataclasses import InitVar, dataclass, field
from pathlib import Path


def _find_project_root() -> Path:
    """Find the project root directory containing pyproject.toml."""
    config_file = Path(__file__).resolve()

    for directory in config_file.parents:
        if (directory / "pyproject.toml").is_file():
            return directory

    raise FileNotFoundError(
        "Cannot determine the KASE Pilot project root: " "pyproject.toml was not found."
    )


@dataclass(frozen=True)
class Settings:
    """Store immutable paths used throughout the application."""

    project_root: Path = field(init=False)
    src_dir: Path = field(init=False)
    data_dir: Path = field(init=False)
    database_dir: Path = field(init=False)
    log_dir: Path = field(init=False)
    backup_dir: Path = field(init=False)
    cache_dir: Path = field(init=False)
    docs_dir: Path = field(init=False)
    tests_dir: Path = field(init=False)
    _root: InitVar[Path | None] = None

    def __post_init__(self, _root: Path | None) -> None:
        """Calculate project paths after dataclass initialization."""
        project_root = _root if _root is not None else _find_project_root()
        data_dir = project_root / "data"

        object.__setattr__(self, "project_root", project_root)
        object.__setattr__(self, "src_dir", project_root / "src")
        object.__setattr__(self, "data_dir", data_dir)
        object.__setattr__(self, "database_dir", data_dir / "database")
        object.__setattr__(self, "log_dir", data_dir / "logs")
        object.__setattr__(self, "backup_dir", data_dir / "backup")
        object.__setattr__(self, "cache_dir", data_dir / "cache")
        object.__setattr__(self, "docs_dir", project_root / "docs")
        object.__setattr__(self, "tests_dir", project_root / "tests")


def load_settings(project_root: Path | None = None) -> Settings:
    """Create and return a configured Settings instance.

    Parameters
    ----------
    project_root:
        Explicit project root.  When omitted, ``_find_project_root()``
        locates the directory containing ``pyproject.toml``.
    """
    return Settings(_root=project_root)


settings = load_settings()
