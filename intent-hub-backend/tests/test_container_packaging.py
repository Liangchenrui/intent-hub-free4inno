from pathlib import Path, PurePosixPath


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def test_backend_image_excludes_runtime_data_and_secrets() -> None:
    ignore = (REPOSITORY_ROOT / "intent-hub-backend/.dockerignore").read_text(
        encoding="utf-8"
    )

    assert ".env" in ignore
    patterns = tuple(
        line.strip()
        for line in ignore.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )
    assert "data/*" in patterns
    assert "!data/settings.example.json" in patterns
    assert patterns.index("data/*") < patterns.index("!data/settings.example.json")

    def is_included(path: str) -> bool:
        ignored = False
        for pattern in patterns:
            negated = pattern.startswith("!")
            candidate = pattern.removeprefix("!")
            if PurePosixPath(path).match(candidate):
                ignored = not negated
        return not ignored

    known_runtime_files = (
        "data/agents.json",
        "data/diagnostics_cache.json",
        "data/default_route.txt",
        "data/settings.json",
        "data/agents.db",
        "data/agents.db-wal",
        "data/agents.db-shm",
        "data/sync_state.db",
        "data/future-runtime-file.db",
    )
    for runtime_file in known_runtime_files:
        assert is_included(runtime_file) is False
    assert is_included("data/settings.example.json") is True


def test_frontend_image_excludes_local_environment_and_build_state() -> None:
    ignore = (REPOSITORY_ROOT / "intent-hub-frontend/.dockerignore").read_text(
        encoding="utf-8"
    )

    assert ".env*" in ignore
    assert "node_modules" in ignore
    assert "dist" in ignore
