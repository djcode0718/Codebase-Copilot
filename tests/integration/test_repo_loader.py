import os
import shutil

import pytest

pytestmark = pytest.mark.slow
pytest.importorskip("git")

from app.ingestion import repo_loader


def test_is_valid_url():
    assert repo_loader.is_valid_url("https://github.com/org/repo")
    assert not repo_loader.is_valid_url("not-a-url")


def test_rmtree_with_retry_handles_transient_permission_error(tmp_path, monkeypatch):
    target = tmp_path / "repo"
    target.mkdir()
    (target / "a.txt").write_text("x")

    real_rmtree = shutil.rmtree
    calls = {"count": 0}

    def flaky_rmtree(path, onerror=None):
        calls["count"] += 1
        if calls["count"] < 3:
            raise PermissionError("transient lock")
        return real_rmtree(path, onerror=onerror)

    monkeypatch.setattr(repo_loader.shutil, "rmtree", flaky_rmtree)
    monkeypatch.setattr(repo_loader.time, "sleep", lambda _: None)

    repo_loader._rmtree_with_retry(str(target), attempts=4, base_delay_s=0.01)

    assert calls["count"] == 3
    assert not target.exists()


def test_remove_existing_repo_dir_uses_move_aside_on_direct_failure(tmp_path, monkeypatch):
    target = tmp_path / "repo"
    target.mkdir()
    (target / "data.txt").write_text("x")

    def fail_direct_then_succeed(path, attempts=8, base_delay_s=0.12):
        if os.path.normcase(os.path.abspath(path)) == os.path.normcase(os.path.abspath(str(target))):
            raise PermissionError("locked")
        if os.path.exists(path):
            shutil.rmtree(path)

    monkeypatch.setattr(repo_loader, "_rmtree_with_retry", fail_direct_then_succeed)

    repo_loader._remove_existing_repo_dir(str(target))

    assert not target.exists()


def test_load_repository_clones_into_clean_target(tmp_path, monkeypatch):
    monkeypatch.setattr(repo_loader, "REPOS_DIR", str(tmp_path))

    existing = tmp_path / "demo"
    existing.mkdir()
    (existing / "old.txt").write_text("old")

    def fake_clone_from(source, target_dir, **_kwargs):
        os.makedirs(target_dir, exist_ok=True)
        with open(os.path.join(target_dir, "new.txt"), "w", encoding="utf-8") as f:
            f.write(source)

    monkeypatch.setattr(repo_loader.git.Repo, "clone_from", staticmethod(fake_clone_from))

    target = repo_loader.load_repository("https://github.com/example/demo")

    assert os.path.normcase(target) == os.path.normcase(str(existing))
    assert os.path.exists(os.path.join(target, "new.txt"))
    assert not os.path.exists(os.path.join(target, "old.txt"))


def test_load_repository_normalizes_url_before_clone(tmp_path, monkeypatch):
    monkeypatch.setattr(repo_loader, "REPOS_DIR", str(tmp_path))
    captured = {}

    def fake_clone_from(source, target_dir, **_kwargs):
        captured["source"] = source
        os.makedirs(target_dir, exist_ok=True)

    monkeypatch.setattr(repo_loader.git.Repo, "clone_from", staticmethod(fake_clone_from))

    target = repo_loader.load_repository("https://github.com/example/demo.git?tab=readme#top")

    assert os.path.normcase(target) == os.path.normcase(str(tmp_path / "demo"))
    assert captured["source"] == "https://github.com/example/demo.git"


def test_load_repository_retries_stage_promotion_after_permission_error(tmp_path, monkeypatch):
    monkeypatch.setattr(repo_loader, "REPOS_DIR", str(tmp_path))

    def fake_clone_from(source, target_dir, **_kwargs):
        os.makedirs(target_dir, exist_ok=True)
        with open(os.path.join(target_dir, "new.txt"), "w", encoding="utf-8") as f:
            f.write(source)

    monkeypatch.setattr(repo_loader.git.Repo, "clone_from", staticmethod(fake_clone_from))

    real_replace = os.replace
    calls = {"count": 0}

    def flaky_replace(src, dst):
        src_name = os.path.basename(src)
        if ".clone-" in src_name:
            calls["count"] += 1
            if calls["count"] < 3:
                raise PermissionError("transient rename lock")
        return real_replace(src, dst)

    monkeypatch.setattr(repo_loader.os, "replace", flaky_replace)
    monkeypatch.setattr(repo_loader.time, "sleep", lambda _: None)

    target = repo_loader.load_repository("https://github.com/example/demo")

    assert os.path.normcase(target) == os.path.normcase(str(tmp_path / "demo"))
    assert calls["count"] == 3
    assert os.path.exists(os.path.join(target, "new.txt"))
