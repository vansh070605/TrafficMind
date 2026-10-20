"""SUMO Environment and Process Utilities.

Provides robust auto-detection of SUMO installation on Windows/Linux,
path configuration, binary resolution, and safe TraCI cleanup.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
from typing import Optional


def find_sumo_home() -> Optional[Path]:
    """Find and return SUMO_HOME directory, checking environment and common paths."""
    # 1. Direct env variable
    if "SUMO_HOME" in os.environ and os.environ["SUMO_HOME"]:
        candidate = Path(os.environ["SUMO_HOME"])
        if candidate.exists() and (candidate / "bin").exists():
            return candidate

    # 2. Check Windows common installation locations
    common_windows_paths = [
        Path(r"C:\Program Files (x86)\SUMO"),
        Path(r"C:\Program Files\SUMO"),
        Path(os.path.expandvars(r"%LOCALAPPDATA%\Programs\SUMO")),
    ]
    for p in common_windows_paths:
        if p.exists() and (p / "bin").exists():
            return p

    # 3. Check if sumo executable is already in PATH
    sumo_in_path = shutil.which("sumo") or shutil.which("sumo.exe")
    if sumo_in_path:
        bin_dir = Path(sumo_in_path).resolve().parent
        if bin_dir.name.lower() == "bin":
            return bin_dir.parent

    return None


def setup_sumo_environment() -> Path:
    """Ensure SUMO_HOME is configured and tools are added to sys.path.

    Raises:
        FileNotFoundError: If SUMO is not found with actionable instructions.
    """
    sumo_home = find_sumo_home()
    if sumo_home is None:
        raise FileNotFoundError(
            "SUMO installation was not detected.\n"
            "Please ensure Eclipse SUMO is installed:\n"
            "  - Windows: Run `winget install EclipseFoundation.SUMO`\n"
            "  - Or download installer from: https://sumo.dlr.de/docs/Downloads.php\n"
            "  - Set SUMO_HOME environment variable to your SUMO directory."
        )

    sumo_home_str = str(sumo_home.resolve())
    os.environ["SUMO_HOME"] = sumo_home_str

    bin_dir = str((sumo_home / "bin").resolve())
    if bin_dir not in os.environ.get("PATH", ""):
        os.environ["PATH"] = bin_dir + os.pathsep + os.environ.get("PATH", "")

    tools_dir = str((sumo_home / "tools").resolve())
    if tools_dir not in sys.path and (sumo_home / "tools").exists():
        sys.path.append(tools_dir)

    return sumo_home


def get_sumo_binary(gui: bool = False) -> str:
    """Return the absolute path or command name for sumo or sumo-gui executable."""
    setup_sumo_environment()
    sumo_home = find_sumo_home()
    bin_name = "sumo-gui.exe" if sys.platform == "win32" and gui else ("sumo.exe" if sys.platform == "win32" else ("sumo-gui" if gui else "sumo"))

    if sumo_home:
        binary_path = sumo_home / "bin" / bin_name
        if binary_path.exists():
            return str(binary_path.resolve())

    # Fallback to which
    which_name = "sumo-gui" if gui else "sumo"
    found = shutil.which(which_name)
    if found:
        return found

    raise FileNotFoundError(f"Could not find executable '{bin_name}'. Make sure SUMO is installed correctly.")


def get_netconvert_binary() -> str:
    """Return the path to netconvert executable."""
    setup_sumo_environment()
    sumo_home = find_sumo_home()
    bin_name = "netconvert.exe" if sys.platform == "win32" else "netconvert"

    if sumo_home:
        binary_path = sumo_home / "bin" / bin_name
        if binary_path.exists():
            return str(binary_path.resolve())

    found = shutil.which("netconvert")
    if found:
        return found

    raise FileNotFoundError("Could not find executable 'netconvert'.")


def close_traci_safely() -> None:
    """Safely check and close any active TraCI connections to avoid socket leaks."""
    try:
        import traci
        if traci.isLoaded():
            try:
                traci.close()
            except Exception:
                pass
    except Exception:
        pass
