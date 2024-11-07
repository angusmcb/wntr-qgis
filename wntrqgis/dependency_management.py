from __future__ import annotations

import os
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
            package
            for package in ["pandas", "numpy", "scipy", "networkx", "matplotlib", "geopandas"]
            if find_spec(package) is None
        ]

    @staticmethod
    def _check_wntr() -> str | None:
        if find_spec("wntr") is None:
            return None
        try:
            import wntr
        except ImportError:
            return None
        return wntr.__version__

    @classmethod
    def _unpack_wntr(cls) -> None:
        # Don't let PIP bet installing it twice at same time
        if cls._unpacking_wntr:
            return None
        cls._unpacking_wntr = True

        this_dir = os.path.dirname(os.path.realpath(__file__))
        wheels = os.path.join(this_dir, "wheels/")
        packagedir = os.path.join(this_dir, "packages/")
        Path(packagedir).mkdir(parents=True, exist_ok=True)

        kwargs: dict[str, Any] = {}
        if os.name == "nt":
            kwargs.setdefault("creationflags", subprocess.CREATE_NO_WINDOW)  # type: ignore[attr-defined]

        # python is normally found at sys.executable, but there is an issue on windows qgis so use 'python' instead
        # https://github.com/qgis/QGIS/issues/45646
        subprocess.run(
            [
                "python" if os.name == "nt" else sys.executable,
                "-m",
                "pip",
                "install",
                "--no-index",
                "--upgrade",
                "--force-reinstall",
                "--target=" + packagedir,
                "--no-deps",
                "--find-links=" + wheels,
                "wntr",
            ],
            check=False,
            **kwargs,
        )
