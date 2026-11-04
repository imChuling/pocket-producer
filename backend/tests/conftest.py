import ast
import importlib.util
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

# Modules whose import needs torch (or safetensors). torch is a research-only
# dependency, absent from requirements.txt and the deployment image, so tests
# that reach these modules skip when it is missing instead of breaking
# collection. Set POCKET_TEST_NO_TORCH=1 to see what CI sees locally.
_TORCH_BACKED = {
    "torch",
    "safetensors",
    "ranking.context_model",
    "ranking.ladder_adapter",
    "ranking.linear_ranker",
    "ranking.deepsets_ranker",
    "ranking.research.capacity",
    "ranking.research.training",
    "ranking.research.offline_eval",
}


def _torch_available() -> bool:
    if os.environ.get("POCKET_TEST_NO_TORCH") == "1":
        return False
    return importlib.util.find_spec("torch") is not None


def _imports_torch_backed_module(path: pathlib.Path) -> bool:
    try:
        tree = ast.parse(path.read_text())
    except (OSError, SyntaxError):
        return False
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            names = [node.module]
        else:
            continue
        if any(name == m or name.startswith(m + ".") for name in names for m in _TORCH_BACKED):
            return True
    return False


def pytest_ignore_collect(collection_path, config):
    path = pathlib.Path(collection_path)
    if path.suffix != ".py" or _torch_available():
        return None
    if _imports_torch_backed_module(path):
        print(f"skipping {path.name}: torch not installed")
        return True
    return None
