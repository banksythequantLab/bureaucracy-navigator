import os

os.environ["BN_MODEL_CACHE_DIR"] = ".cache/test-model"
from packages.agents import cache  # noqa: E402


def test_cached_calls_once():
    calls = []

    def fn():
        calls.append(1)
        return "hola"

    assert cache.cached(fn, "phrase", "m", "es", "f1", "label") == "hola"
    assert cache.cached(fn, "phrase", "m", "es", "f1", "label") == "hola"
    assert len(calls) == 1
    assert cache.get("phrase", "m", "es", "f2", "label") is None
