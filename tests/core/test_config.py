"""Unit tests for kase_pilot.core.config."""

import dataclasses
from pathlib import Path

import pytest

import kase_pilot.core.config as config_module
from kase_pilot.core.config import Settings, _find_project_root, settings

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fake_root(tmp_path: Path) -> Path:
    """Return a temporary directory that looks like a project root."""
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'fake'\n")
    return tmp_path


def _make_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Settings:
    """Return a Settings instance whose root is an isolated tmp directory."""
    fake_root = _fake_root(tmp_path)
    monkeypatch.setattr(config_module, "_find_project_root", lambda: fake_root)
    return Settings()


# ---------------------------------------------------------------------------
# Global singleton — one smoke-test only
# ---------------------------------------------------------------------------


class TestGlobalSingleton:
    def test_settings_is_instance_of_settings_class(self) -> None:
        assert isinstance(settings, Settings)


# ---------------------------------------------------------------------------
# _find_project_root
# ---------------------------------------------------------------------------


class TestFindProjectRoot:
    def test_returns_path_containing_pyproject_toml(self) -> None:
        root = _find_project_root()
        assert (root / "pyproject.toml").is_file()

    def test_returns_path_instance(self) -> None:
        assert isinstance(_find_project_root(), Path)

    def test_raises_file_not_found_when_pyproject_toml_missing(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        fake_file = tmp_path / "subdir" / "config.py"
        fake_file.parent.mkdir(parents=True)
        fake_file.touch()
        monkeypatch.setattr(config_module, "__file__", str(fake_file))

        with pytest.raises(FileNotFoundError, match="pyproject.toml was not found"):
            _find_project_root()

    def test_error_message_mentions_kase_pilot(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        fake_file = tmp_path / "config.py"
        fake_file.touch()
        monkeypatch.setattr(config_module, "__file__", str(fake_file))

        with pytest.raises(FileNotFoundError, match="KASE Pilot project root"):
            _find_project_root()


# ---------------------------------------------------------------------------
# Settings — path values (tested on a local instance with a fake root)
# ---------------------------------------------------------------------------


class TestSettingsPathValues:
    """All nine paths are computed correctly from the injected root."""

    def test_project_root(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        fake_root = _fake_root(tmp_path)
        monkeypatch.setattr(config_module, "_find_project_root", lambda: fake_root)
        s = Settings()
        assert s.project_root == fake_root

    def test_src_dir(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        s = _make_settings(monkeypatch, tmp_path)
        assert s.src_dir == s.project_root / "src"

    def test_data_dir(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        s = _make_settings(monkeypatch, tmp_path)
        assert s.data_dir == s.project_root / "data"

    def test_database_dir(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        s = _make_settings(monkeypatch, tmp_path)
        assert s.database_dir == s.data_dir / "database"

    def test_log_dir(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        s = _make_settings(monkeypatch, tmp_path)
        assert s.log_dir == s.data_dir / "logs"

    def test_backup_dir(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        s = _make_settings(monkeypatch, tmp_path)
        assert s.backup_dir == s.data_dir / "backup"

    def test_cache_dir(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        s = _make_settings(monkeypatch, tmp_path)
        assert s.cache_dir == s.data_dir / "cache"

    def test_docs_dir(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        s = _make_settings(monkeypatch, tmp_path)
        assert s.docs_dir == s.project_root / "docs"

    def test_tests_dir(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        s = _make_settings(monkeypatch, tmp_path)
        assert s.tests_dir == s.project_root / "tests"


# ---------------------------------------------------------------------------
# Settings — path types
# ---------------------------------------------------------------------------


class TestSettingsPathTypes:
    """Every attribute must be a pathlib.Path instance."""

    def test_all_attributes_are_path_instances(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        s = _make_settings(monkeypatch, tmp_path)
        for attr in (
            "project_root",
            "src_dir",
            "data_dir",
            "database_dir",
            "log_dir",
            "backup_dir",
            "cache_dir",
            "docs_dir",
            "tests_dir",
        ):
            value = getattr(s, attr)
            assert isinstance(
                value, Path
            ), f"{attr!r} is {type(value).__name__}, not Path"


# ---------------------------------------------------------------------------
# Settings — immutability
# ---------------------------------------------------------------------------


class TestSettingsImmutability:
    """Settings must be a frozen dataclass."""

    def test_assigning_existing_attribute_raises_frozen_instance_error(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        s = _make_settings(monkeypatch, tmp_path)
        with pytest.raises(dataclasses.FrozenInstanceError):
            s.project_root = Path("/tmp")  # type: ignore[misc]

    def test_assigning_new_attribute_raises_frozen_instance_error(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        s = _make_settings(monkeypatch, tmp_path)
        with pytest.raises(dataclasses.FrozenInstanceError):
            s.new_field = Path("/tmp")  # type: ignore[attr-defined]

    def test_deleting_attribute_raises_frozen_instance_error(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        s = _make_settings(monkeypatch, tmp_path)
        with pytest.raises(dataclasses.FrozenInstanceError):
            del s.src_dir  # type: ignore[misc]

    def test_is_dataclass(self) -> None:
        assert dataclasses.is_dataclass(Settings)
