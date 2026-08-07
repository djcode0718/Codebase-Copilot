from __future__ import annotations

import pytest

pytest.importorskip("git")

from app.ingestion import repo_loader


def test_build_authenticated_url_injects_github_token(monkeypatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "abc123")
    url = repo_loader._build_authenticated_url("https://github.com/org/repo.git")
    assert url.startswith("https://x-access-token:abc123@github.com/")


def test_build_authenticated_url_keeps_non_github_url(monkeypatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "abc123")
    source = "https://gitlab.com/org/repo.git"
    assert repo_loader._build_authenticated_url(source) == source


def test_clone_repository_maps_auth_errors(monkeypatch, tmp_path) -> None:
    class FakeGitError(Exception):
        pass

    def fake_clone(*_args, **_kwargs):
        raise repo_loader.git.exc.GitCommandError("clone", 128, stderr="fatal: could not read Username for 'https://github.com': terminal prompts disabled")

    monkeypatch.setattr(repo_loader.git.Repo, "clone_from", staticmethod(fake_clone))

    with pytest.raises(ValueError) as exc:
        repo_loader._clone_repository("https://github.com/org/private-repo.git", str(tmp_path / "repo"))

    assert "authentication failed" in str(exc.value).lower()
