import os
import subprocess
import sys
from importlib.util import find_spec
from pathlib import Path
from typing import Any


class WqDependencyManagemet:
    @staticmethod
    def add_packages_to_path():
        this_dir = os.path.dirname(os.path.realpath(__file__))
        path = os.path.join(this_dir, "packages")
        sys.path.append(path)

    @staticmethod
    def check_dependencies():
        return [
            package
            for package in ["pandas", "numpy", "scipy", "networkx", "matplotlib", "geopandas"]
            if find_spec(package) is None
        ]

    @staticmethod
    def check_wntr():
        if find_spec("wntr") is None:
            return None
        try:
            import wntr
        except ImportError:
            return None
        return wntr.__version__

    @staticmethod
    def install_wntr() -> bool:
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
        try:
            import wntr  # noqa F401 finally, this is the newly installed wntr
        except ImportError:
            return False
        return True
