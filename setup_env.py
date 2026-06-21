"""Create a Python 3.12 VideoLingo-Freelancer environment with uv.

This bootstrapper can be launched by any recent system Python. It installs uv
when needed, creates ``.venv``, and runs ``install.py`` with that environment's
interpreter so pip and Streamlit never drift across Python installations.
"""

import argparse
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path


PYTHON_VERSION = "3.12"
VENV_DIR = ".venv"
SCRIPT_DIR = Path(__file__).resolve().parent


def run(command, **kwargs):
    """Run a command while showing the exact argv used."""
    print("  > " + " ".join(str(part) for part in command))
    return subprocess.run(command, check=True, **kwargs)


def is_uv_installed():
    return shutil.which("uv") is not None


def _add_uv_to_path():
    home = Path.home()
    local_app_data = Path(os.environ.get("LOCALAPPDATA", home))
    candidates = (
        home / ".local" / "bin",
        home / ".cargo" / "bin",
        local_app_data / "uv" / "bin",
        local_app_data / "Programs" / "uv",
    )
    executable = "uv.exe" if platform.system() == "Windows" else "uv"
    for directory in candidates:
        if (directory / executable).is_file():
            os.environ["PATH"] = str(directory) + os.pathsep + os.environ.get("PATH", "")
            return


def _install_uv_windows():
    methods = (
        (
            "winget",
            [
                "winget",
                "install",
                "astral-sh.uv",
                "--accept-package-agreements",
                "--accept-source-agreements",
            ],
        ),
        ("pip", [sys.executable, "-m", "pip", "install", "uv"]),
        (
            "PowerShell",
            [
                "powershell",
                "-ExecutionPolicy",
                "ByPass",
                "-c",
                "irm https://astral.sh/uv/install.ps1 | iex",
            ],
        ),
    )
    for name, command in methods:
        try:
            print(f"  Trying {name}...")
            run(command)
            _add_uv_to_path()
            if is_uv_installed():
                return
        except (FileNotFoundError, subprocess.CalledProcessError):
            continue


def install_uv():
    if is_uv_installed():
        version = subprocess.run(
            ["uv", "--version"], capture_output=True, text=True, check=False
        ).stdout.strip()
        print(f"  uv is already installed: {version}")
        return

    print("\n[1/3] Installing uv...")
    if platform.system() == "Windows":
        _install_uv_windows()
    else:
        try:
            run([sys.executable, "-m", "pip", "install", "uv"])
        except subprocess.CalledProcessError:
            run(["sh", "-c", "curl -LsSf https://astral.sh/uv/install.sh | sh"])
        _add_uv_to_path()

    if not is_uv_installed():
        raise SystemExit(
            "uv was installed but is not on PATH. Restart the terminal and rerun "
            "this command, or install uv from https://docs.astral.sh/uv/."
        )


def _venv_python(venv_path):
    if platform.system() == "Windows":
        return venv_path / "Scripts" / "python.exe"
    return venv_path / "bin" / "python"


def create_venv():
    print(f"\n[2/3] Creating environment with Python {PYTHON_VERSION}...")
    venv_path = SCRIPT_DIR / VENV_DIR
    python_exe = _venv_python(venv_path)
    if python_exe.is_file():
        result = subprocess.run(
            [str(python_exe), "--version"], capture_output=True, text=True, check=False
        )
        if result.stdout.strip().startswith(f"Python {PYTHON_VERSION}."):
            print(f"  Reusing {venv_path}: {result.stdout.strip()}")
            return python_exe
        print("  Existing .venv uses another Python version; replacing it.")
        shutil.rmtree(venv_path)

    run(
        ["uv", "venv", "--seed", "--python", PYTHON_VERSION, VENV_DIR],
        cwd=SCRIPT_DIR,
    )
    python_exe = _venv_python(venv_path)
    if not python_exe.is_file():
        raise SystemExit("Failed to create .venv with Python 3.12.")
    return python_exe


def run_install(python_exe, no_launch=False):
    print("\n[3/3] Installing VideoLingo-Freelancer...")
    command = [str(python_exe), str(SCRIPT_DIR / "install.py")]
    if no_launch:
        command.append("--no-launch")
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    venv_bin = python_exe.parent
    env["PATH"] = str(venv_bin) + os.pathsep + env.get("PATH", "")
    run(command, cwd=SCRIPT_DIR, env=env)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Create a Python 3.12 uv environment and install VideoLingo-Freelancer."
    )
    parser.add_argument(
        "--skip-install",
        action="store_true",
        help="Create or validate .venv without running install.py.",
    )
    parser.add_argument(
        "--no-launch",
        action="store_true",
        help="Install dependencies but do not start Streamlit afterward.",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    print("=" * 64)
    print(" VideoLingo-Freelancer setup (uv + Python 3.12)")
    print("=" * 64)
    install_uv()
    python_exe = create_venv()
    if not args.skip_install:
        run_install(python_exe, no_launch=args.no_launch)
    print("\nSetup complete.")
    print(f"Start later with: {python_exe} -m streamlit run st.py")


if __name__ == "__main__":
    main()
