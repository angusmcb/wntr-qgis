import os
import subprocess
import sys
from pathlib import Path


def checkDependencies():
    missing_deps = []
    try:
        import pandas
    except ImportError:
        missing_deps.append("pandas")
    try:
        import numpy
    except ImportError:
        missing_deps.append("numpy")
    try:
        import scipy
    except ImportError:
        missing_deps.append("scipy")
    try:
        import networkx
    except ImportError:
        missing_deps.append("networkx")
    try:
        import matplotlib
    except ImportError:
        missing_deps.append("matplotlib")
    try:
        import geopandas
    except ImportError:
        missing_deps.append("geopandas")

    if len(missing_deps) == 0:
        try:
            import wntr  # this would be a system-installed wntr
        except ImportError:
            try:
                this_dir = os.path.dirname(os.path.realpath(__file__))
                path = os.path.join(this_dir, "packages")
                Path(path).mkdir(parents=True, exist_ok=True)
                sys.path.append(path)
                import wntr  # this would be a previously plugin installed wntr
            except ImportError:
                this_dir = os.path.dirname(os.path.realpath(__file__))
                wheels = os.path.join(this_dir, "wheels/")
                packagedir = os.path.join(this_dir, "packages/")
                kwargs = {}
                if os.name == "nt":
                    kwargs.setdefault("creationflags", subprocess.CREATE_NO_WINDOW)

                subprocess.run(
                    [
                        "python" if os.name == "nt" else sys.executable,
                        "-m",
                        "pip",
                        "install",
                        "--no-index",
                        "--upgrade",
                        "--target=" + packagedir,
                        "--no-deps",
                        "--find-links=" + wheels,
                        "wntr",
                    ],
                    check=False,
                    **kwargs,
                )
                try:
                    import wntr  # finally, this is the newly installed wntr
                except ImportError:
                    missing_deps.append("wntr")
    return missing_deps


def _python_command():
    # python is normally found at sys.executable, but there is an issue on windows qgis so use 'python' instead
    # https://github.com/qgis/QGIS/issues/45646
    return "python" if os.name == "nt" else sys.executable
