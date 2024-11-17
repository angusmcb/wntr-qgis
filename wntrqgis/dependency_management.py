from __future__ import annotations

import os
import platform
import subprocess
import sys
from importlib import invalidate_caches
from importlib.util import find_spec
from pathlib import Path
from typing import Any


class WqDependencyManagement:
    _dependencies_available = False
    _wntr__availalble_version: str | None = None
    _unpacking_wntr = False

    @classmethod
    def ensure_wntr(cls):
        if not cls._dependencies_available:
            missing_deps = cls._check_dependencies()
            if len(missing_deps):
                msg = f"Missing necessary python packages {*missing_deps,}. Please see help for how to fix this"
                raise ModuleNotFoundError(msg)

            cls._dependencies_available = True

        if not cls._wntr__availalble_version:
            cls._wntr__availalble_version = cls._check_wntr()

        if not cls._wntr__availalble_version:
            cls._unpack_wntr()
            invalidate_caches()
            import wntr

            cls._wntr__availalble_version = wntr.__version__

        return cls._wntr__availalble_version

    @staticmethod
    def _check_dependencies():
        return [
            package for package in ["pandas", "numpy", "scipy", "networkx", "matplotlib"] if find_spec(package) is None
        ]

    @staticmethod
    def _check_wntr() -> str | None:
        invalidate_caches()
        if find_spec("wntr") is None:
            return None
        try:
            import wntr
        except ImportError:
            return None
        return wntr.__version__

    @classmethod
    def _unpack_wntr(cls) -> None:
        # Try not to let PIP install it twice at same time
        if cls._unpacking_wntr:
            return None
        cls._unpacking_wntr = True

        kwargs: dict[str, Any] = {}
        if os.name == "nt":
            kwargs.setdefault("creationflags", subprocess.CREATE_NO_WINDOW)  # type: ignore[attr-defined]

        subprocess.run(
            [
                cls._python_command(),
                "-m",
                "pip",
                "install",
                "--upgrade",
                "--force-reinstall",
                "--target=" + cls.package_directory(),
                "--no-deps",
                "--find-links=" + cls.wheels_directory(),
                "wntr",
            ],
            check=False,
            **kwargs,
        )

    @classmethod
    def package_directory(cls):
        major, minor, _ = platform.python_version_tuple()
        packages_path = Path(__file__).parent / "packages" / (major + minor)
        packages_path.mkdir(parents=True, exist_ok=True)
        return str(packages_path.resolve())

    @classmethod
    def wheels_directory(cls):
        wheels_path = Path(__file__).parent / "wheels"
        return str(wheels_path.resolve())

    @classmethod
    def _python_command(cls):
        # python is normally found at sys.executable, but there is an issue on windows qgis so use 'python' instead
        # https://github.com/qgis/QGIS/issues/45646
        return "python" if os.name == "nt" else sys.executable
