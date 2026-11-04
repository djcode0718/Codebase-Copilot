"""
context_builder.py
──────────────────
Builds a single "Codebase Context Document" at index time.

This document dynamically captures:
  - Project identity & purpose from section-aware README extraction
  - Inferred tech stack & dependencies from package manifests
    (pyproject.toml, setup.py, requirements.txt, Pipfile, package.json, Cargo.toml, go.mod)
  - Key entry points and module/directory structure
  - Notebook workflows & imported libraries (from notebook_parser)
  - Core components and cross-file relationships (from relationship_graph)

Zero LLM calls are made during profiling (fast, deterministic, zero rate limits).
Hardcoded templates and static descriptions of CodeBase-Copilot are completely removed.
"""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from llama_index.core import Document

from app.config import INDEX_DIR
from app.utils.logger import get_logger

logger = get_logger(__name__)

# File extensions that hint at the tech stack
TECH_STACK_MAP = {
    ".py":           "Python",
    ".js":           "JavaScript",
    ".ts":           "TypeScript",
    ".jsx":          "React",
    ".tsx":          "React/TypeScript",
    ".java":         "Java",
    ".go":           "Go",
    ".rs":           "Rust",
    ".cpp":          "C++",
    ".c":            "C",
    ".cs":           "C#",
    ".rb":           "Ruby",
    ".php":          "PHP",
    ".html":         "HTML",
    ".css":          "CSS",
    ".sh":           "Shell",
    ".dockerfile":   "Docker",
    ".yaml":         "YAML/Config",
    ".yml":          "YAML/Config",
    ".toml":         "TOML/Config",
    ".md":           "Documentation",
    ".ipynb":        "Jupyter Notebook",
}

ENTRYPOINT_NAMES = {
    "main.py", "app.py", "cli.py", "run.py", "server.py", "__main__.py",
    "wsgi.py", "asgi.py", "index.js", "index.ts", "server.js", "server.ts",
    "main.go", "main.rs", "app.ts", "app.js",
}

# Approved character budgets
BUDGET_OVERVIEW = 2000
BUDGET_ARCHITECTURE = 3000
BUDGET_PIPELINE = 2500
BUDGET_DEPENDENCIES = 1500
BUDGET_TOTAL_DOC = 9000


def _parse_toml_content(content: str) -> dict:
    """Parse TOML content using tomli or tomllib if available, falling back to empty dict."""
    try:
        import tomllib
        return tomllib.loads(content)
    except Exception:
        pass
    try:
        import tomli
        return tomli.loads(content)
    except Exception:
        pass
    return {}


def _clean_dep_name(raw: str) -> str:
    """Normalize a dependency string to extract just the package name."""
    cleaned = raw.strip().strip("'\"")
    # Strip comments and environment markers
    cleaned = re.split(r"[;#]", cleaned)[0].strip()
    # Strip version specifiers like ==, >=, <=, ~=, !=, <, >
    cleaned = re.split(r"[><=~!]", cleaned)[0].strip()
    # Strip extras like package[extra]
    cleaned = re.sub(r"\[.*?\]", "", cleaned).strip()
    return cleaned


def extract_manifest_dependencies(repo_path: str, file_paths: Optional[List[str]] = None) -> Dict[str, List[str]]:
    """
    Extract declared dependencies from supported package manifests:
    - pyproject.toml
    - setup.py / setup.cfg
    - requirements.txt (and requirements-*.txt)
    - Pipfile
    - package.json
    - Cargo.toml
    - go.mod
    """
    manifest_deps: Dict[str, List[str]] = {}

    # Gather relative file basenames available in repo
    available_files: Dict[str, str] = {}
    if file_paths:
        for fp in file_paths:
            try:
                rel = Path(os.path.relpath(fp, repo_path)).as_posix()
                available_files[os.path.basename(fp).lower()] = fp
                available_files[rel.lower()] = fp
            except Exception:
                continue

    def _read_file_text(target_name: str) -> Optional[str]:
        # Try available_files map first, then direct disk path
        target_lower = target_name.lower()
        if target_lower in available_files:
            try:
                with open(available_files[target_lower], "r", encoding="utf-8", errors="ignore") as f:
                    return f.read()
            except Exception:
                pass
        disk_path = os.path.join(repo_path, target_name)
        if os.path.isfile(disk_path):
            try:
                with open(disk_path, "r", encoding="utf-8", errors="ignore") as f:
                    return f.read()
            except Exception:
                pass
        return None

    # 1. package.json
    pkg_json_text = _read_file_text("package.json")
    if pkg_json_text:
        try:
            pkg_data = json.loads(pkg_json_text)
            deps = []
            for k in ("dependencies", "devDependencies", "peerDependencies"):
                val = pkg_data.get(k)
                if isinstance(val, dict):
                    deps.extend(list(val.keys()))
            if deps:
                manifest_deps["package.json"] = sorted(list(dict.fromkeys(deps)))
        except Exception as e:
            logger.debug(f"Failed to parse package.json dependencies: {e}")

    # 2. requirements.txt / requirements-*.txt
    req_names = [f for f in available_files.keys() if f.startswith("requirements") and f.endswith(".txt")] or ["requirements.txt"]
    for req_name in req_names:
        req_text = _read_file_text(req_name)
        if req_text:
            req_deps = []
            for line in req_text.splitlines():
                line = line.strip()
                if not line or line.startswith("#") or line.startswith("-"):
                    continue
                pkg = _clean_dep_name(line)
                if pkg and re.match(r"^[a-zA-Z0-9_\-\.]+$", pkg):
                    req_deps.append(pkg)
            if req_deps:
                manifest_deps[req_name] = sorted(list(dict.fromkeys(req_deps)))

    # 3. pyproject.toml
    pyproject_text = _read_file_text("pyproject.toml")
    if pyproject_text:
        try:
            parsed = _parse_toml_content(pyproject_text)
            pyproject_deps = []
            # PEP 621 dependencies
            project_deps = parsed.get("project", {}).get("dependencies", [])
            if isinstance(project_deps, list):
                for dep in project_deps:
                    p = _clean_dep_name(str(dep))
                    if p:
                        pyproject_deps.append(p)
            # Poetry dependencies
            poetry_deps = parsed.get("tool", {}).get("poetry", {}).get("dependencies", {})
            if isinstance(poetry_deps, dict):
                for dep in poetry_deps.keys():
                    if dep.lower() != "python":
                        pyproject_deps.append(dep)
            if pyproject_deps:
                manifest_deps["pyproject.toml"] = sorted(list(dict.fromkeys(pyproject_deps)))
        except Exception as e:
            logger.debug(f"Failed to parse pyproject.toml: {e}")

    # 4. setup.py / setup.cfg
    setup_text = _read_file_text("setup.py") or _read_file_text("setup.cfg")
    if setup_text:
        setup_deps = []
        install_reqs_match = re.search(r"install_requires\s*=\s*\[(.*?)\]", setup_text, re.DOTALL)
        if install_reqs_match:
            raw_items = re.findall(r"['\"]([^'\"]+)['\"]", install_reqs_match.group(1))
            for item in raw_items:
                p = _clean_dep_name(item)
                if p:
                    setup_deps.append(p)
        if setup_deps:
            manifest_deps["setup.py"] = sorted(list(dict.fromkeys(setup_deps)))

    # 5. Pipfile
    pipfile_text = _read_file_text("Pipfile")
    if pipfile_text:
        try:
            parsed = _parse_toml_content(pipfile_text)
            pip_deps = []
            for section in ("packages", "dev-packages"):
                pkgs = parsed.get(section, {})
                if isinstance(pkgs, dict):
                    pip_deps.extend(list(pkgs.keys()))
            if pip_deps:
                manifest_deps["Pipfile"] = sorted(list(dict.fromkeys(pip_deps)))
        except Exception as e:
            logger.debug(f"Failed to parse Pipfile: {e}")

    # 6. Cargo.toml
    cargo_text = _read_file_text("Cargo.toml")
    if cargo_text:
        try:
            parsed = _parse_toml_content(cargo_text)
            cargo_deps = []
            for sec in ("dependencies", "dev-dependencies", "build-dependencies"):
                pkgs = parsed.get(sec, {})
                if isinstance(pkgs, dict):
                    cargo_deps.extend(list(pkgs.keys()))
            if cargo_deps:
                manifest_deps["Cargo.toml"] = sorted(list(dict.fromkeys(cargo_deps)))
        except Exception as e:
            logger.debug(f"Failed to parse Cargo.toml: {e}")

    # 7. go.mod
    gomod_text = _read_file_text("go.mod")
    if gomod_text:
        go_deps = []
        # require ( ... ) block
        block_match = re.search(r"require\s*\((.*?)\)", gomod_text, re.DOTALL)
        if block_match:
            for line in block_match.group(1).splitlines():
                parts = line.strip().split()
                if parts and not parts[0].startswith("//"):
                    go_deps.append(parts[0])
        # single line require
        for line in gomod_text.splitlines():
            line = line.strip()
            if line.startswith("require ") and not line.endswith("("):
                parts = line.split()
                if len(parts) >= 2:
                    go_deps.append(parts[1])
        if go_deps:
            manifest_deps["go.mod"] = sorted(list(dict.fromkeys(go_deps)))

    return manifest_deps


def _clean_markdown_badges_and_links(text: str) -> str:
    """Remove HTML badges, CI images, and image markdown links."""
    # Remove markdown images [![badge](url)](url) and ![img](url)
    cleaned = re.sub(r"\[!\[.*?\]\(.*?\)\]\(.*?\)", "", text)
    cleaned = re.sub(r"!\[.*?\]\(.*?\)", "", cleaned)
    # Remove HTML <img> tags
    cleaned = re.sub(r"<img\b[^>]*>", "", cleaned, flags=re.IGNORECASE)
    # Remove HTML comments
    cleaned = re.sub(r"<!--.*?-->", "", cleaned, flags=re.DOTALL)
    # Collapse multiple blank lines
    return re.sub(r"\n{3,}", "\n\n", cleaned).strip()


def extract_section_aware_readme(repo_path: str, file_paths: Optional[List[str]] = None) -> Dict[str, str]:
    """
    Parses Markdown by headings (#, ##, ###) and prioritizes key sections:
    - overview: Overview / Description / About
    - architecture: Architecture / System Design / Components
    - pipeline: Workflows / Pipeline / Usage / Dataset / Model
    Discards badges, licenses, and changelogs. Respects character budgets.
    """
    sections = {
        "overview": "",
        "architecture": "",
        "pipeline": "",
    }

    # Locate primary README file
    readme_candidates = [
        "readme.md", "readme.rst", "readme.txt", "readme",
        "docs/index.md", "docs/readme.md",
    ]
    readme_path = None
    if file_paths:
        for fp in file_paths:
            try:
                rel = Path(os.path.relpath(fp, repo_path)).as_posix().lower()
                if rel in readme_candidates or os.path.basename(rel) == "readme.md":
                    readme_path = fp
                    break
            except Exception:
                continue

    if not readme_path:
        for c in readme_candidates:
            p = os.path.join(repo_path, c)
            if os.path.isfile(p):
                readme_path = p
                break

    if not readme_path or not os.path.isfile(readme_path):
        return sections

    try:
        with open(readme_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
    except Exception as e:
        logger.warning(f"Could not read README at {readme_path}: {e}")
        return sections

    cleaned_content = _clean_markdown_badges_and_links(content)
    if not cleaned_content:
        return sections

    # Split markdown by top-level or second-level headings
    heading_re = re.compile(r"^(#{1,3}\s+.+)$", re.MULTILINE)
    splits = heading_re.split(cleaned_content)

    # First segment before any heading is typically the introductory overview
    intro = splits[0].strip() if splits else ""
    if intro:
        sections["overview"] = intro[:BUDGET_OVERVIEW]

    excluded_headings = {
        "license", "licence", "changelog", "history", "contributing",
        "code of conduct", "authors", "acknowledgements", "acknowledgments",
        "badges", "version", "releases",
    }

    arch_keywords = {"architecture", "design", "system", "components", "structure", "overview", "modules"}
    pipe_keywords = {"pipeline", "workflow", "model", "training", "evaluation", "usage", "features", "dataset", "getting started"}

    for idx in range(1, len(splits), 2):
        heading_line = splits[idx].strip()
        body = splits[idx + 1].strip() if idx + 1 < len(splits) else ""

        clean_heading = re.sub(r"^#{1,3}\s+", "", heading_line).strip()
        h_lower = clean_heading.lower()

        if any(ex in h_lower for ex in excluded_headings):
            continue

        entry_text = f"### {clean_heading}\n{body}\n"

        if any(kw in h_lower for kw in arch_keywords):
            if len(sections["architecture"]) + len(entry_text) <= BUDGET_ARCHITECTURE:
                sections["architecture"] += entry_text + "\n"
        elif any(kw in h_lower for kw in pipe_keywords):
            if len(sections["pipeline"]) + len(entry_text) <= BUDGET_PIPELINE:
                sections["pipeline"] += entry_text + "\n"
        elif not sections["overview"] or len(sections["overview"]) < 500:
            if len(sections["overview"]) + len(entry_text) <= BUDGET_OVERVIEW:
                sections["overview"] += entry_text + "\n"

    # Clean and cap all sections
    for k, budget in [("overview", BUDGET_OVERVIEW), ("architecture", BUDGET_ARCHITECTURE), ("pipeline", BUDGET_PIPELINE)]:
        text = sections[k].strip()
        if len(text) > budget:
            # Truncate at last clean newline or sentence
            cut = text[:budget]
            last_nl = cut.rfind("\n")
            if last_nl > budget * 0.7:
                text = cut[:last_nl]
            else:
                text = cut
        sections[k] = text.strip()

    return sections


def _extract_functions_and_classes(content: str, ext: str) -> dict:
    """Extract top-level function and class names from source code."""
    result = {"functions": [], "classes": []}

    if ext == ".py":
        result["functions"] = re.findall(r"^def\s+([a-zA-Z0-9_]+)", content, re.MULTILINE)
        result["classes"]   = re.findall(r"^class\s+([a-zA-Z0-9_]+)", content, re.MULTILINE)
    elif ext in (".js", ".ts", ".jsx", ".tsx"):
        result["functions"] = re.findall(r"(?:function\s+|const\s+|let\s+)([a-zA-Z0-9_]+)\s*[=\(]", content)
        result["classes"]   = re.findall(r"^class\s+([a-zA-Z0-9_]+)", content, re.MULTILINE)

    result["functions"] = result["functions"][:15]
    result["classes"]   = result["classes"][:8]
    return result


def _extract_notebook_pipeline_summaries(repo_path: str, file_paths: List[str]) -> List[str]:
    """Inspect Jupyter Notebooks (.ipynb) using notebook_parser to extract workflow steps and key imports."""
    from app.parsing.notebook_parser import parse_notebook

    notebook_summaries: List[str] = []
    nb_files = [fp for fp in file_paths if Path(fp).suffix.lower() == ".ipynb"]
    nb_files.sort(key=lambda p: os.path.basename(p))

    for nb_path in nb_files[:8]:
        try:
            with open(nb_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            rel = Path(os.path.relpath(nb_path, repo_path)).as_posix()
            cells = parse_notebook(content, rel)
            if not cells:
                continue

            headings = []
            imports = set()
            for cell in cells:
                if cell.cell_type == "markdown":
                    for line in cell.source.splitlines():
                        line_s = line.strip()
                        if line_s.startswith("#"):
                            h = re.sub(r"^#{1,3}\s+", "", line_s).strip()
                            if h and len(h) < 60:
                                headings.append(h)
                elif cell.cell_type == "code":
                    for imp in re.findall(r"(?:import|from)\s+([a-zA-Z0-9_]+)", cell.clean_code):
                        if imp not in ("os", "sys", "time", "json", "math", "re"):
                            imports.add(imp)

            summary_parts = [f"### Notebook: {rel}"]
            if headings:
                summary_parts.append(f"Workflow Steps: {' -> '.join(headings[:5])}")
            if imports:
                summary_parts.append(f"Libraries Used: {', '.join(sorted(list(imports))[:8])}")

            notebook_summaries.append("\n".join(summary_parts))
        except Exception as e:
            logger.debug(f"Notebook inspection failed for {nb_path}: {e}")

    return notebook_summaries


def _detect_entrypoints(repo_path: str, file_paths: List[str]) -> List[str]:
    """Detect entry point files in the repository."""
    entrypoints = []
    for fp in file_paths:
        base = os.path.basename(fp).lower()
        if base in ENTRYPOINT_NAMES:
            try:
                rel = Path(os.path.relpath(fp, repo_path)).as_posix()
                entrypoints.append(rel)
            except Exception:
                pass
    return sorted(entrypoints)


def _extract_directory_structure(repo_path: str, file_paths: List[str]) -> str:
    """Group repository files into top-level modules/directories with file counts."""
    dir_counts: Dict[str, int] = {}
    for fp in file_paths:
        try:
            rel = Path(os.path.relpath(fp, repo_path)).as_posix()
            parts = rel.split("/")
            top = parts[0] if len(parts) > 1 else "<root>"
            dir_counts[top] = dir_counts.get(top, 0) + 1
        except Exception:
            continue

    lines = []
    for d, cnt in sorted(dir_counts.items(), key=lambda x: -x[1]):
        lines.append(f"  - {d}/ ({cnt} files)")
    return "\n".join(lines)


def _extract_graph_summary(
    index_name: str,
    graph: Optional[dict] = None,
) -> str:
    """Summarize top referenced symbols from relationship graph."""
    if graph is None:
        graph_path = os.path.join(INDEX_DIR, index_name, "relationship_graph.json")
        if os.path.isfile(graph_path):
            try:
                with open(graph_path, "r", encoding="utf-8") as gf:
                    graph = json.load(gf)
            except Exception:
                graph = None

    if not graph or not isinstance(graph, dict):
        return "No static call or reference graph available."

    # Identify symbols with the most referrers
    scored_symbols = []
    for sym, refs in graph.items():
        if isinstance(refs, list) and len(refs) > 0:
            # Exclude standard library or trivial tokens
            if len(sym) >= 3 and not sym.startswith("_"):
                scored_symbols.append((sym, len(refs)))

    scored_symbols.sort(key=lambda x: -x[1])
    top_symbols = scored_symbols[:12]
    if not top_symbols:
        return "No high-connectivity symbols identified in call graph."

    lines = [f"- `{sym}` (referenced by {cnt} files/scopes)" for sym, cnt in top_symbols]
    return "Top referenced cross-file symbols & modules:\n" + "\n".join(lines)


def build_codebase_context(
    file_paths: List[str],
    repo_path: str,
    index_name: str,
    graph_summary: Optional[dict] = None,
) -> Document:
    """
    Build a single Document capturing the dynamic repository architecture.
    Saved to disk so it is not rebuilt on every restart.
    Injected into the node list before indexing so it is embedded alongside regular code chunks.

    Structure of the dynamic context:
      PROJECT IDENTITY & PURPOSE (from README section-aware extraction)
      INFERRED TECH STACK & DEPENDENCIES (from manifests + extensions)
      ARCHITECTURE & SYSTEM DESIGN (from README or structural modules)
      KEY ENTRY POINTS & MODULE STRUCTURE
      CORE COMPONENTS & NOTEBOOK WORKFLOWS
      CROSS-FILE & INTER-MODULE RELATIONSHIPS (from relationship graph)

    Zero hardcoded templates. Zero LLM calls.
    Returns a LlamaIndex Document ready for embedding.
    """
    cache_path = os.path.join(INDEX_DIR, index_name, "codebase_context.txt")
    os.makedirs(os.path.dirname(cache_path), exist_ok=True)

    start = time.time()
    repo_name = os.path.basename(os.path.normpath(repo_path))
    logger.info(f"Building dynamic codebase context document for '{repo_name}' ({len(file_paths)} files)...")

    # 1. Tech stack detection
    extensions_found: Dict[str, int] = {}
    for fp in file_paths:
        ext = Path(fp).suffix.lower()
        if ext in TECH_STACK_MAP:
            lang = TECH_STACK_MAP[ext]
            extensions_found[lang] = extensions_found.get(lang, 0) + 1

    tech_stack_langs = ", ".join(
        f"{lang} ({count} files)"
        for lang, count in sorted(extensions_found.items(), key=lambda x: -x[1])
    )

    # 2. Manifest dependencies
    manifests = extract_manifest_dependencies(repo_path, file_paths)
    manifest_lines = []
    dep_count = 0
    for m_file, deps in manifests.items():
        if deps and dep_count < 25:
            sample = deps[:15]
            manifest_lines.append(f"- **{m_file}**: {', '.join(sample)}{' ...' if len(deps) > 15 else ''}")
            dep_count += len(sample)

    dep_summary_text = "\n".join(manifest_lines) if manifest_lines else "No package manifests detected."

    # 3. Section-aware README extraction
    readme_sections = extract_section_aware_readme(repo_path, file_paths)
    overview_text = readme_sections.get("overview") or f"{repo_name} codebase containing {len(file_paths)} indexed files."
    architecture_text = readme_sections.get("architecture") or "No explicit architecture section defined in README."
    pipeline_text = readme_sections.get("pipeline") or ""

    # 4. Entrypoints & Directory Structure
    entrypoints = _detect_entrypoints(repo_path, file_paths)
    entrypoints_text = ", ".join(f"`{e}`" for e in entrypoints) if entrypoints else "None identified."
    dir_structure_text = _extract_directory_structure(repo_path, file_paths)

    # 5. Notebook Workflows
    notebook_workflows = _extract_notebook_pipeline_summaries(repo_path, file_paths)
    notebooks_text = "\n\n".join(notebook_workflows) if notebook_workflows else ""

    # 6. Per-file symbol summary (up to 20 important files)
    file_summaries = []

    def _file_priority(fp: str) -> int:
        name = os.path.basename(fp).lower()
        if "readme" in name: return 0
        if name in ENTRYPOINT_NAMES: return 1
        if "app" in name or "model" in name or "service" in name: return 2
        return 3

    sorted_files = sorted(file_paths, key=_file_priority)
    for fp in sorted_files[:20]:
        try:
            with open(fp, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except Exception:
            continue

        if not content.strip() or len(content) < 40:
            continue

        rel_path = Path(os.path.relpath(fp, repo_path)).as_posix()
        ext = Path(fp).suffix.lower()
        symbols = _extract_functions_and_classes(content, ext)

        preview = " ".join(content[:140].split())
        entry = f"### `{rel_path}`\n{preview}"
        if symbols["classes"]:
            entry += f"\nClasses: {', '.join(symbols['classes'])}"
        if symbols["functions"]:
            entry += f"\nFunctions: {', '.join(symbols['functions'])}"
        file_summaries.append(entry)

    top_files_text = "\n\n".join(file_summaries)

    # 7. Relationship Graph Summary
    graph_text = _extract_graph_summary(index_name, graph_summary)

    # ── Assemble dynamic document ────────────────────────────────────────────
    sections_assembled = [
        f"# Codebase Architectural Overview: {repo_name}",
        f"\n## Project Identity & Purpose\n{overview_text}",
        f"\n## Inferred Tech Stack & Dependencies\n- **Languages**: {tech_stack_langs}\n- **Manifest Dependencies**:\n{dep_summary_text}",
    ]

    if architecture_text and architecture_text != "No explicit architecture section defined in README.":
        sections_assembled.append(f"\n## Architecture & System Design\n{architecture_text}")

    if pipeline_text:
        sections_assembled.append(f"\n## Pipeline & Usage Workflows\n{pipeline_text}")

    sections_assembled.append(
        f"\n## Key Entry Points & Module Structure\n- **Entry Points**: {entrypoints_text}\n- **Module Hierarchy**:\n{dir_structure_text}"
    )

    if notebooks_text:
        sections_assembled.append(f"\n## Notebook Workflows & Pipelines\n{notebooks_text}")

    sections_assembled.append(f"\n## Key File Summaries & Exported Symbols\n{top_files_text}")
    sections_assembled.append(f"\n## Cross-File & Inter-Module Relationships\n{graph_text}")
    sections_assembled.append(
        "\n## Retrieval Note\n"
        "This document provides a high-level architectural view of the entire codebase.\n"
        "It is used to answer broad questions about architecture, limitations,\n"
        "design patterns, improvement suggestions, and how components interact."
    )

    full_context_text = "\n".join(sections_assembled)

    # Bound overall document size to budget
    if len(full_context_text) > BUDGET_TOTAL_DOC:
        full_context_text = full_context_text[:BUDGET_TOTAL_DOC] + "\n\n... [Architectural overview capped at budget]"

    # Cache to disk
    with open(cache_path, "w", encoding="utf-8") as f:
        f.write(full_context_text)

    logger.info(f"Dynamic codebase context document built in {time.time() - start:.2f}s (len={len(full_context_text)})")

    return Document(
        text=full_context_text,
        metadata={
            "file_name": "_codebase_context",
            "path": "_codebase_context",
            "doc_type": "architectural_summary",
        },
        excluded_embed_metadata_keys=["doc_type"],
    )