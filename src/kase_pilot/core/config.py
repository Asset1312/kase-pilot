"""Project path configuration for KASE Pilot."""

import os
from collections.abc import Mapping
from dataclasses import InitVar, dataclass, field
from pathlib import Path

from kase_pilot.core.exceptions import ConfigurationError

_PUBLIC_KEY_ENV = "TRADERNET_PUBLIC_KEY"
_PRIVATE_KEY_ENV = "TRADERNET_PRIVATE_KEY"


_MARKET_DATABASE_NAME = "market.sqlite3"


def _find_project_root() -> Path:
    """Find the source root, falling back to the runtime working directory."""
    config_file = Path(__file__).resolve()

    for directory in config_file.parents:
        if (directory / "pyproject.toml").is_file():
            return directory

    return Path.cwd().resolve()


def _database_dir(project_root: Path) -> Path:
    return project_root / "data" / "database"


def market_database_path(project_root: Path | None = None) -> Path:
    """Return the collected market database path, without needing credentials.

    Commands that only read locally collected data (rebuilding a quote or an
    order book) must not demand broker credentials, so they cannot go through
    ``load_settings``. This shares the same path derivation as ``Settings`` so
    the two cannot drift apart.
    """
    root = project_root if project_root is not None else _find_project_root()
    return _database_dir(root) / _MARKET_DATABASE_NAME


@dataclass(frozen=True)
class Settings:
    """Store immutable paths used throughout the application."""

    tradernet_public_key: str = field(repr=False)
    tradernet_private_key: str = field(repr=False)
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
        object.__setattr__(self, "database_dir", _database_dir(project_root))
        object.__setattr__(self, "log_dir", data_dir / "logs")
        object.__setattr__(self, "backup_dir", data_dir / "backup")
        object.__setattr__(self, "cache_dir", data_dir / "cache")
        object.__setattr__(self, "docs_dir", project_root / "docs")
        object.__setattr__(self, "tests_dir", project_root / "tests")


def load_settings(
    project_root: Path | None = None,
    *,
    environ: Mapping[str, str] | None = None,
) -> Settings:
    """Create and return a configured Settings instance.

    Parameters
    ----------
    project_root:
        Explicit project root. When omitted, ``_find_project_root()`` uses the
        source root for editable installs and the working directory otherwise.
    environ:
        Environment mapping. Defaults to the current process environment.

    Raises
    ------
    ConfigurationError
        If a required Tradernet credential is missing or empty.
    """
    environment = os.environ if environ is None else environ

    public_key = environment.get(_PUBLIC_KEY_ENV)
    if public_key is None or public_key == "":
        raise ConfigurationError(
            f"Missing required environment variable: {_PUBLIC_KEY_ENV}"
        )

    private_key = environment.get(_PRIVATE_KEY_ENV)
    if private_key is None or private_key == "":
        raise ConfigurationError(
            f"Missing required environment variable: {_PRIVATE_KEY_ENV}"
        )

    return Settings(
        tradernet_public_key=public_key,
        tradernet_private_key=private_key,
        _root=project_root,
    )
