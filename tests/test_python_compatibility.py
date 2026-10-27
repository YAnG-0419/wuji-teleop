import ast
from pathlib import Path


def test_all_shipped_python_parses_for_foxy_python38():
    root = Path(__file__).parents[1]
    files = []
    for directory in ("hardware", "control", "teleop", "tools", "examples"):
        files.extend((root / directory).rglob("*.py"))
    assert files
    for path in files:
        ast.parse(path.read_text(), filename=str(path), feature_version=8)
