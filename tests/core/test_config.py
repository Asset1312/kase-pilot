"""Unit tests for kase_pilot.core.config."""

import dataclasses
import os
import subprocess
import sys
from pathlib import Path

import pytest

import kase_pilot.core.config as config_module
from kase_pilot.core.config import Settings, _find_project_root, load_settings
from kase_pilot.core.exceptions import ConfigurationError

PUBLIC_KEY = "TestPublicKey"
PRIVATE_KEY = "TestPrivateKey"
TEST_ENVIRONMENT = {
    "TRADERNET_PUBLIC_KEY": PUBLIC_KEY,
    "TRADERNET_PRIVATE_KEY": PRIVATE_KEY,
}

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
    return Settings(PUBLIC_KEY, PRIVATE_KEY)


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
        s = Settings(PUBLIC_KEY, PRIVATE_KEY)
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


# ---------------------------------------------------------------------------
# load_settings
# ---------------------------------------------------------------------------


class TestLoadSettings:
    def test_config_module_has_no_global_settings(self) -> None:
        assert not hasattr(config_module, "settings")

    def test_returns_settings_instance(self, tmp_path: Path) -> None:
        s = load_settings(project_root=tmp_path, environ=TEST_ENVIRONMENT)
        assert isinstance(s, Settings)

    def test_repeated_calls_return_separate_instances(self, tmp_path: Path) -> None:
        first = load_settings(project_root=tmp_path, environ=TEST_ENVIRONMENT)
        second = load_settings(project_root=tmp_path, environ=TEST_ENVIRONMENT)

        assert first is not second

    def test_explicit_root_is_used(self, tmp_path: Path) -> None:
        s = load_settings(project_root=tmp_path, environ=TEST_ENVIRONMENT)
        assert s.project_root == tmp_path

    def test_find_project_root_not_called_when_root_given(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        called: list[bool] = []
        monkeypatch.setattr(
            config_module,
            "_find_project_root",
            lambda: called.append(True) or tmp_path,
        )
        load_settings(project_root=tmp_path, environ=TEST_ENVIRONMENT)
        assert called == []

    def test_find_project_root_called_when_no_root_given(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        called: list[bool] = []

        def fake_find() -> Path:
            called.append(True)
            return tmp_path

        monkeypatch.setattr(config_module, "_find_project_root", fake_find)
        load_settings(environ=TEST_ENVIRONMENT)
        assert called == [True]

    def test_derived_paths_are_correct(self, tmp_path: Path) -> None:
        s = load_settings(project_root=tmp_path, environ=TEST_ENVIRONMENT)
        assert s.src_dir == tmp_path / "src"
        assert s.data_dir == tmp_path / "data"
        assert s.database_dir == tmp_path / "data" / "database"
        assert s.log_dir == tmp_path / "data" / "logs"
        assert s.backup_dir == tmp_path / "data" / "backup"
        assert s.cache_dir == tmp_path / "data" / "cache"
        assert s.docs_dir == tmp_path / "docs"
        assert s.tests_dir == tmp_path / "tests"

    def test_result_is_immutable(self, tmp_path: Path) -> None:
        s = load_settings(project_root=tmp_path, environ=TEST_ENVIRONMENT)
        with pytest.raises(dataclasses.FrozenInstanceError):
            s.project_root = tmp_path  # type: ignore[misc]

    def test_initvar_not_stored_as_instance_attribute(self, tmp_path: Path) -> None:
        s = load_settings(project_root=tmp_path, environ=TEST_ENVIRONMENT)
        assert "_root" not in vars(s)

    def test_reads_credentials_from_process_environment(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("TRADERNET_PUBLIC_KEY", PUBLIC_KEY)
        monkeypatch.setenv("TRADERNET_PRIVATE_KEY", PRIVATE_KEY)

        settings = load_settings(project_root=tmp_path)

        assert settings.tradernet_public_key == PUBLIC_KEY
        assert settings.tradernet_private_key == PRIVATE_KEY

    def test_preserves_credential_values_exactly(self, tmp_path: Path) -> None:
        environment = {
            "TRADERNET_PUBLIC_KEY": "MiXeD Public Key",
            "TRADERNET_PRIVATE_KEY": "  private key  ",
        }

        settings = load_settings(project_root=tmp_path, environ=environment)

        assert settings.tradernet_public_key == "MiXeD Public Key"
        assert settings.tradernet_private_key == "  private key  "

    @pytest.mark.parametrize("value", [None, ""])
    def test_rejects_missing_or_empty_public_key(
        self, value: str | None, tmp_path: Path
    ) -> None:
        environment = {"TRADERNET_PRIVATE_KEY": PRIVATE_KEY}
        if value is not None:
            environment["TRADERNET_PUBLIC_KEY"] = value

        with pytest.raises(
            ConfigurationError,
            match=r"^Missing required environment variable: TRADERNET_PUBLIC_KEY$",
        ):
            load_settings(project_root=tmp_path, environ=environment)

    @pytest.mark.parametrize("value", [None, ""])
    def test_rejects_missing_or_empty_private_key(
        self, value: str | None, tmp_path: Path
    ) -> None:
        environment = {"TRADERNET_PUBLIC_KEY": PUBLIC_KEY}
        if value is not None:
            environment["TRADERNET_PRIVATE_KEY"] = value

        with pytest.raises(
            ConfigurationError,
            match=r"^Missing required environment variable: TRADERNET_PRIVATE_KEY$",
        ):
            load_settings(project_root=tmp_path, environ=environment)

    def test_validates_public_key_before_private_key(self, tmp_path: Path) -> None:
        with pytest.raises(ConfigurationError, match="TRADERNET_PUBLIC_KEY"):
            load_settings(project_root=tmp_path, environ={})

    def test_repr_and_str_hide_credentials_but_show_paths(self, tmp_path: Path) -> None:
        settings = load_settings(project_root=tmp_path, environ=TEST_ENVIRONMENT)

        for rendered in (repr(settings), str(settings)):
            assert PUBLIC_KEY not in rendered
            assert PRIVATE_KEY not in rendered
            assert repr(tmp_path) in rendered

    def test_repeated_calls_do_not_cache_credentials(self, tmp_path: Path) -> None:
        first = load_settings(
            project_root=tmp_path,
            environ={
                "TRADERNET_PUBLIC_KEY": "first-public",
                "TRADERNET_PRIVATE_KEY": "first-private",
            },
        )
        second = load_settings(
            project_root=tmp_path,
            environ={
                "TRADERNET_PUBLIC_KEY": "second-public",
                "TRADERNET_PRIVATE_KEY": "second-private",
            },
        )

        assert first.tradernet_public_key == "first-public"
        assert second.tradernet_public_key == "second-public"

    def test_import_is_safe_without_credentials_or_tradernet_sdk(self) -> None:
        environment = os.environ.copy()
        environment.pop("TRADERNET_PUBLIC_KEY", None)
        environment.pop("TRADERNET_PRIVATE_KEY", None)
        script = (
            "import builtins\n"
            "original_import = builtins.__import__\n"
            "def guarded_import(name, *args, **kwargs):\n"
            "    if name == 'tradernet' or name.startswith('tradernet.'):\n"
            "        raise AssertionError('config imported tradernet-sdk')\n"
            "    return original_import(name, *args, **kwargs)\n"
            "builtins.__import__ = guarded_import\n"
            "import kase_pilot.core.config\n"
        )

        result = subprocess.run(
            [sys.executable, "-c", script],
            env=environment,
            capture_output=True,
            check=False,
        )

        assert result.returncode == 0
