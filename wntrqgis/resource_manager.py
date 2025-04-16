from pathlib import Path


def _inp_path(example_name: str) -> str:
    return str(Path(__file__).resolve().parent / "resources" / "examples" / (example_name + ".inp"))


examples = {
    "KY1": _inp_path("ky1"),
    "KY10": _inp_path("ky10"),
    "VALVES": _inp_path("valves"),
}
