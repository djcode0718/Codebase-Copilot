from app.ingestion.repo_naming import derive_repo_name, normalize_clone_source


def test_derive_repo_name_ignores_url_query_and_fragment() -> None:
    source = "https://github.com/org/repo.git?ref=main#readme"
    assert derive_repo_name(source) == "repo"


def test_derive_repo_name_sanitizes_windows_invalid_chars() -> None:
    source = "https://example.com/org/repo:name"
    assert derive_repo_name(source) == "repo-name"


def test_derive_repo_name_handles_windows_reserved_name() -> None:
    source = "https://github.com/org/con.git"
    assert derive_repo_name(source) == "con-repo"


def test_normalize_clone_source_strips_query_and_fragment() -> None:
    source = "https://github.com/org/repo.git?tab=readme#top"
    assert normalize_clone_source(source) == "https://github.com/org/repo.git"


def test_derive_repo_name_handles_windows_reserved_name_with_extension() -> None:
    source = "https://github.com/org/con.txt.git"
    assert derive_repo_name(source) == "con.txt-repo"


def test_derive_repo_name_truncates_very_long_names() -> None:
    long_name = "a" * 240
    source = f"https://github.com/org/{long_name}.git"
    assert len(derive_repo_name(source)) <= 64
