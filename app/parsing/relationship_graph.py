import os
import re
import json
from pathlib import Path
from typing import List, Dict, Set, Any
from app.utils.logger import get_logger

logger = get_logger(__name__)


class RelationshipGraphBuilder:
    def __init__(self, repo_path: str):
        self.repo_path = repo_path
        # Definitions map: symbol_name -> list of "file:scope" where defined
        self.definitions: Dict[str, List[str]] = {}
        # Adjacency map: symbol_or_file -> list of referencing "file:scope" or "file"
        self.graph: Dict[str, Set[str]] = {}

    def build_graph(self, file_paths: List[str]) -> Dict[str, List[str]]:
        """
        Builds the relationship graph and returns it as a serialized adjacency list.
        Only processes Python (.py), Javascript (.js, .jsx), and TypeScript (.ts, .tsx) files.
        """
        logger.info(f"Building relationship graph over {len(file_paths)} files...")
        
        # Posix relative paths
        rel_files = []
        for fp in file_paths:
            try:
                rel = Path(os.path.relpath(fp, self.repo_path)).as_posix()
                rel_files.append((fp, rel))
            except Exception:
                continue

        # First pass: collect all definitions and imports
        for fp, rel in rel_files:
            ext = Path(fp).suffix.lower()
            if ext == ".py":
                self._parse_python_definitions(fp, rel)
            elif ext in [".js", ".jsx", ".ts", ".tsx"]:
                self._parse_js_ts_definitions(fp, rel)

        # Second pass: trace references/calls
        for fp, rel in rel_files:
            ext = Path(fp).suffix.lower()
            if ext == ".py":
                self._trace_python_references(fp, rel)
            elif ext in [".js", ".jsx", ".ts", ".tsx"]:
                self._trace_js_ts_references(fp, rel)

        # Convert sets to sorted lists for JSON serialization
        serialized_graph = {}
        for key, val in self.graph.items():
            serialized_graph[key] = sorted(list(val))
        return serialized_graph

    def _parse_python_definitions(self, fp: str, rel: str):
        try:
            with open(fp, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
        except Exception:
            return

        scope_stack = []  # items: (indent_level, name)
        in_signature = False
        for line in lines:
            stripped = line.lstrip()
            if not stripped or stripped.startswith("#"):
                continue

            indent = len(line) - len(stripped)

            # Pop scope stack if indentation is less than or equal to top of stack,
            # but only if we are not currently parsing a multiline signature.
            if not in_signature:
                while scope_stack and scope_stack[-1][0] >= indent:
                    scope_stack.pop()
            else:
                # We are inside a signature, check if it terminates on this line
                stripped_no_comment = re.sub(r"#.*$", "", line).strip()
                if stripped_no_comment.endswith(":"):
                    in_signature = False

            # Match class or function definition
            class_match = re.match(r"class\s+([a-zA-Z0-9_]+)", stripped)
            def_match = re.match(r"def\s+([a-zA-Z0-9_]+)", stripped)

            if class_match:
                name = class_match.group(1)
                scope_stack.append((indent, name))
                full_scope_name = ".".join([s[1] for s in scope_stack])
                self._add_definition(name, f"{rel}:{full_scope_name}")
                # File references itself
                self._add_definition(rel, f"{rel}:{full_scope_name}")

                # If this is a multiline signature, mark in_signature
                stripped_no_comment = re.sub(r"#.*$", "", line).strip()
                if not stripped_no_comment.endswith(":"):
                    in_signature = True
            elif def_match:
                name = def_match.group(1)
                scope_stack.append((indent, name))
                full_scope_name = ".".join([s[1] for s in scope_stack])
                self._add_definition(name, f"{rel}:{full_scope_name}")
                # File references itself
                self._add_definition(rel, f"{rel}:{full_scope_name}")

                # If this is a multiline signature, mark in_signature
                stripped_no_comment = re.sub(r"#.*$", "", line).strip()
                if not stripped_no_comment.endswith(":"):
                    in_signature = True

            # Also match imports
            import_match = re.match(r"import\s+([a-zA-Z0-9_\.]+)", stripped)
            from_import_match = re.match(r"from\s+([a-zA-Z0-9_\.]+)\s+import", stripped)
            if import_match:
                imported_module = import_match.group(1)
                self._add_reference(imported_module, rel)
            elif from_import_match:
                imported_module = from_import_match.group(1)
                self._add_reference(imported_module, rel)

    def _trace_python_references(self, fp: str, rel: str):
        try:
            with open(fp, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
        except Exception:
            return

        scope_stack = []
        in_signature = False
        for line in lines:
            stripped = line.lstrip()
            if not stripped or stripped.startswith("#"):
                continue

            indent = len(line) - len(stripped)
            if not in_signature:
                while scope_stack and scope_stack[-1][0] >= indent:
                    scope_stack.pop()
            else:
                # We are inside a signature, check if it terminates on this line
                stripped_no_comment = re.sub(r"#.*$", "", line).strip()
                if stripped_no_comment.endswith(":"):
                    in_signature = False

            # Determine current scope
            current_scope = f"{rel}:" + ".".join([s[1] for s in scope_stack]) if scope_stack else rel

            class_match = re.match(r"class\s+([a-zA-Z0-9_]+)", stripped)
            def_match = re.match(r"def\s+([a-zA-Z0-9_]+)", stripped)
            if class_match:
                name = class_match.group(1)
                scope_stack.append((indent, name))
                stripped_no_comment = re.sub(r"#.*$", "", line).strip()
                if not stripped_no_comment.endswith(":"):
                    in_signature = True
                continue
            elif def_match:
                name = def_match.group(1)
                scope_stack.append((indent, name))
                stripped_no_comment = re.sub(r"#.*$", "", line).strip()
                if not stripped_no_comment.endswith(":"):
                    in_signature = True
                continue

            # Find all potential symbol references (words)
            words = re.findall(r"\b([a-zA-Z0-9_]+)\b", stripped)
            for word in words:
                # Reference tracking is scoped to symbols defined within this repository.
                # Third-party/imported library symbols (e.g. LlamaIndex classes) are not tracked
                # and will correctly return no references.
                if word in self.definitions:
                    # Ignore referencing yourself
                    for def_loc in self.definitions[word]:
                        if def_loc != current_scope and not def_loc.startswith(current_scope + "."):
                            self._add_reference(word, current_scope)

    def _parse_js_ts_definitions(self, fp: str, rel: str):
        try:
            with open(fp, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
        except Exception:
            return

        scope_stack = []  # items: (brace_depth, name)
        brace_depth = 0
        for line in lines:
            brace_depth += line.count("{")
            brace_depth -= line.count("}")

            while scope_stack and scope_stack[-1][0] > brace_depth:
                scope_stack.pop()

            stripped = line.strip()
            if not stripped or stripped.startswith("//") or stripped.startswith("/*"):
                continue

            # Match class or function definitions
            class_match = re.search(r"\bclass\s+([a-zA-Z0-9_]+)", stripped)
            func_match = re.search(r"\bfunction\s+([a-zA-Z0-9_]+)", stripped)
            const_func_match = re.search(r"\bconst\s+([a-zA-Z0-9_]+)\s*=\s*(?:\([^)]*\)|[a-zA-Z0-9_]+)\s*=>", stripped)
            method_match = re.search(r"\b(?!class\b|function\b|if\b|for\b|while\b|switch\b|catch\b)(?:async\s+)?([a-zA-Z0-9_]+)\s*\([^)]*\)\s*\{", stripped)

            if class_match:
                name = class_match.group(1)
                scope_stack.append((brace_depth, name))
                full_scope_name = ".".join([s[1] for s in scope_stack])
                self._add_definition(name, f"{rel}:{full_scope_name}")
                self._add_definition(rel, f"{rel}:{full_scope_name}")
            elif func_match:
                name = func_match.group(1)
                scope_stack.append((brace_depth, name))
                full_scope_name = ".".join([s[1] for s in scope_stack])
                self._add_definition(name, f"{rel}:{full_scope_name}")
                self._add_definition(rel, f"{rel}:{full_scope_name}")
            elif const_func_match:
                name = const_func_match.group(1)
                scope_stack.append((brace_depth, name))
                full_scope_name = ".".join([s[1] for s in scope_stack])
                self._add_definition(name, f"{rel}:{full_scope_name}")
                self._add_definition(rel, f"{rel}:{full_scope_name}")
            elif method_match:
                name = method_match.group(1)
                scope_stack.append((brace_depth, name))
                full_scope_name = ".".join([s[1] for s in scope_stack])
                self._add_definition(name, f"{rel}:{full_scope_name}")
                self._add_definition(rel, f"{rel}:{full_scope_name}")

            # Match imports
            import_match = re.search(r"\bimport\s+.*\s+from\s+['\"]([^'\"]+)['\"]", stripped)
            require_match = re.search(r"\brequire\s*\(\s*['\"]([^'\"]+)['\"]\s*\)", stripped)
            if import_match:
                imported = import_match.group(1)
                self._add_reference(imported, rel)
            elif require_match:
                imported = require_match.group(1)
                self._add_reference(imported, rel)

    def _trace_js_ts_references(self, fp: str, rel: str):
        try:
            with open(fp, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
        except Exception:
            return

        scope_stack = []
        brace_depth = 0
        for line in lines:
            brace_depth += line.count("{")
            brace_depth -= line.count("}")

            while scope_stack and scope_stack[-1][0] > brace_depth:
                scope_stack.pop()

            current_scope = f"{rel}:" + ".".join([s[1] for s in scope_stack]) if scope_stack else rel

            stripped = line.strip()
            if not stripped or stripped.startswith("//") or stripped.startswith("/*"):
                continue

            class_match = re.search(r"\bclass\s+([a-zA-Z0-9_]+)", stripped)
            func_match = re.search(r"\bfunction\s+([a-zA-Z0-9_]+)", stripped)
            const_func_match = re.search(r"\bconst\s+([a-zA-Z0-9_]+)\s*=\s*(?:\([^)]*\)|[a-zA-Z0-9_]+)\s*=>", stripped)
            method_match = re.search(r"\b(?!class\b|function\b|if\b|for\b|while\b|switch\b|catch\b)(?:async\s+)?([a-zA-Z0-9_]+)\s*\([^)]*\)\s*\{", stripped)
            if class_match:
                scope_stack.append((brace_depth, class_match.group(1)))
                continue
            elif func_match:
                scope_stack.append((brace_depth, func_match.group(1)))
                continue
            elif const_func_match:
                scope_stack.append((brace_depth, const_func_match.group(1)))
                continue
            elif method_match:
                scope_stack.append((brace_depth, method_match.group(1)))
                continue

            words = re.findall(r"\b([a-zA-Z0-9_]+)\b", stripped)
            for word in words:
                if word in self.definitions:
                    for def_loc in self.definitions[word]:
                        if def_loc != current_scope and not def_loc.startswith(current_scope + "."):
                            self._add_reference(word, current_scope)

    def _add_definition(self, symbol: str, location: str):
        self.definitions.setdefault(symbol, []).append(location)

    def _add_reference(self, key: str, referrer: str):
        self.graph.setdefault(key, set()).add(referrer)
        if "." in key:
            parts = key.split(".")
            self.graph.setdefault(parts[-1], set()).add(referrer)
            slashed = key.replace(".", "/")
            self.graph.setdefault(slashed + ".py", set()).add(referrer)
            self.graph.setdefault(parts[-1] + ".py", set()).add(referrer)
        if "/" in key:
            base = key.split("/")[-1]
            self.graph.setdefault(base, set()).add(referrer)
            self.graph.setdefault(base + ".js", set()).add(referrer)
            self.graph.setdefault(base + ".ts", set()).add(referrer)
            self.graph.setdefault(base + ".jsx", set()).add(referrer)
            self.graph.setdefault(base + ".tsx", set()).add(referrer)
