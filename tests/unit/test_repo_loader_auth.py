from __future__ import annotations

import pytest

pytest.importorskip("git")

from app.ingestion import repo_loader
from app.ingestion.repo_naming import derive_repo_name, normalize_clone_source


def test_build_authenticated_url_injects_github_token(monkeypatch) -> None:
    monkeypatch.setenv("GIT_AUTH_TOKEN", "abc123")
    monkeypatch.setenv("GITHUB_TOKEN", "abc123")
    url = repo_loader._build_authenticated_url("https://github.com/org/repo.git")
    assert url.startswith("https://x-access-token:abc123@github.com/")


def test_build_authenticated_url_keeps_non_github_url(monkeypatch) -> None:
    monkeypatch.setenv("GIT_AUTH_TOKEN", "abc123")
    monkeypatch.setenv("GITHUB_TOKEN", "abc123")
    source = "https://gitlab.com/org/repo.git"
    assert repo_loader._build_authenticated_url(source) == source


def test_clone_repository_maps_auth_errors(monkeypatch, tmp_path) -> None:
    def fake_clone(*_args, **_kwargs):
        raise repo_loader.git.exc.GitCommandError("clone", 128, stderr="fatal: could not read Username for 'https://github.com': terminal prompts disabled")

    monkeypatch.setattr(repo_loader.git.Repo, "clone_from", staticmethod(fake_clone))

    with pytest.raises(ValueError) as exc:
        repo_loader._clone_repository("https://github.com/org/private-repo.git", str(tmp_path / "repo"))

    assert "authentication failed" in str(exc.value).lower()


def test_clone_repository_public_repo_prefers_anonymous(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("GIT_AUTH_TOKEN", "abc123")
    monkeypatch.setenv("GITHUB_TOKEN", "abc123")
    called_sources = []

    def fake_clone(source, *_args, **_kwargs):
        called_sources.append(source)

    monkeypatch.setattr(repo_loader.git.Repo, "clone_from", staticmethod(fake_clone))

    repo_loader._clone_repository("https://github.com/org/public-repo.git", str(tmp_path / "repo"))

    assert called_sources == ["https://github.com/org/public-repo.git"]


def test_clone_repository_retries_with_token_after_auth_failure(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("GIT_AUTH_TOKEN", "abc123")
    monkeypatch.setenv("GITHUB_TOKEN", "abc123")
    called_sources = []

    def fake_clone(source, *_args, **_kwargs):
        called_sources.append(source)
        if len(called_sources) == 1:
            raise repo_loader.git.exc.GitCommandError(
                "clone",
                128,
                stderr="fatal: could not read Username for 'https://github.com': terminal prompts disabled",
            )

    monkeypatch.setattr(repo_loader.git.Repo, "clone_from", staticmethod(fake_clone))

    repo_loader._clone_repository("https://github.com/org/private-repo.git", str(tmp_path / "repo"))

    assert called_sources[0] == "https://github.com/org/private-repo.git"
    assert called_sources[1].startswith("https://x-access-token:abc123@github.com/")


def test_normalize_clone_source_strips_query_and_fragment() -> None:
    source = "https://github.com/org/repo.git?tab=readme#top"
    assert normalize_clone_source(source) == "https://github.com/org/repo.git"


def test_derive_repo_name_guards_windows_reserved_with_extension() -> None:
    source = "https://github.com/org/con.txt.git"
    assert derive_repo_name(source) == "con.txt-repo"



