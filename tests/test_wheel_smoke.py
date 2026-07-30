"""Operational smoke tests for an installed KASE Pilot wheel."""

import subprocess
import sys
import venv
from pathlib import Path


def test_installed_wheel_loads_settings_outside_source_checkout(
    tmp_path: Path,
) -> None:
    wheel_directory = tmp_path / "dist"
    build_python = getattr(sys, "_base_executable", sys.executable)
    subprocess.run(
        [
            build_python,
            "-m",
            "build",
            "--wheel",
            "--no-isolation",
            "--outdir",
            str(wheel_directory),
        ],
        check=True,
    )
    wheel = next(wheel_directory.glob("kase_pilot-*.whl"))

    environment_directory = tmp_path / "venv"
    venv.EnvBuilder(with_pip=True).create(environment_directory)
    python = (
        environment_directory / "Scripts" / "python.exe"
        if sys.platform == "win32"
        else environment_directory / "bin" / "python"
    )
    subprocess.run(
        [
            str(python),
            "-m",
            "pip",
            "install",
            "--no-deps",
            "--no-index",
            str(wheel),
        ],
        check=True,
    )

    runtime_directory = tmp_path / "runtime"
    runtime_directory.mkdir()
    script = (
        "from pathlib import Path\n"
        "from kase_pilot.core.config import load_settings\n"
        "settings = load_settings(environ={"
        "'TRADERNET_PUBLIC_KEY': 'public', "
        "'TRADERNET_PRIVATE_KEY': 'private'"
        "})\n"
        "assert settings.project_root == Path.cwd().resolve()\n"
    )
    subprocess.run([str(python), "-c", script], cwd=runtime_directory, check=True)
