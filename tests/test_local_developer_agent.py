from __future__ import annotations

import pytest

from scripts.run_local_developer_agent import validate


def test_validate_accepts_small_existing_docs_patch() -> None:
    patch = (
        "--- a/docs/LOCAL_DEVELOPER_AGENT_WINDOWS.md\n"
        "+++ b/docs/LOCAL_DEVELOPER_AGENT_WINDOWS.md\n"
        "@@ -1,1 +1,1 @@\n"
        "-# Local HDS Developer Agent (Windows)\n"
        "+# Local HDS Developer Agent for Windows\n"
    )
    assert validate(patch) == ["docs/LOCAL_DEVELOPER_AGENT_WINDOWS.md"]


@pytest.mark.parametrize(
    "patch",
    [
        "--- a/README.md\n+++ b/README.md\n@@ -1 +1 @@\n-a\n+b\n",
        "--- a/docs/LOCAL_DEVELOPER_AGENT_WINDOWS.md\n+++ b/.env\n@@ -1 +1 @@\n-a\n+b\n",
        "--- a/docs/LOCAL_DEVELOPER_AGENT_WINDOWS.md\n+++ b/docs/other.md\n@@ -1 +1 @@\n-a\n+b\n",
        "--- a/docs/LOCAL_DEVELOPER_AGENT_WINDOWS.md\n+++ /dev/null\n@@ -1 +0,0 @@\n-a\n",
    ],
)
def test_validate_rejects_out_of_scope_or_destructive_patch(patch: str) -> None:
    with pytest.raises(ValueError):
        validate(patch)


def test_validate_rejects_path_traversal() -> None:
    patch = (
        "--- a/docs/../.env\n"
        "+++ b/docs/../.env\n"
        "@@ -1 +1 @@\n-a\n+b\n"
    )
    with pytest.raises(ValueError):
        validate(patch)


def test_validate_rejects_new_files() -> None:
    patch = (
        "--- /dev/null\n"
        "+++ b/docs/new-file.md\n"
        "@@ -0,0 +1 @@\n"
        "+new\n"
    )
    with pytest.raises(ValueError):
        validate(patch)
