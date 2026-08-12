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
        import tree_sitter_language_pack as tslp
        try:
            with open(fp, "rb") as f:
                content = f.read()
            parser = tslp.get_parser("python")
            tree = parser.parse(content)
        except Exception as e:
            logger.warning(f"Tree-sitter Python parse failed for {fp}: {e}")
            return

        def walk(node, current_scope: list):
            is_def = False
            name = ""
            if node.type in ("class_definition", "function_definition"):
                name_node = node.child_by_field_name("name")
                if name_node:
                    name = name_node.text.decode("utf-8", errors="ignore")
                    is_def = True
            
            elif node.type == "assignment" and len(current_scope) == 0:
                left_node = node.child_by_field_name("left")
                if not left_node and node.children:
                    left_node = node.children[0]
                if left_node:
                    def find_identifiers(n):
                        if n.type == "identifier":
                            return [n.text.decode("utf-8", errors="ignore")]
                        ids = []
                        for c in n.children:
                            ids.extend(find_identifiers(c))
                        return ids
                    for name in find_identifiers(left_node):
                        if name and name.isupper():
                            self._add_definition(name, f"{rel}:{name}")

            if is_def and name:
                new_scope = current_scope + [name]
                full_scope = ".".join(new_scope)
                self._add_definition(name, f"{rel}:{full_scope}")
                self._add_definition(rel, f"{rel}:{full_scope}")
                for child in node.children:
                    walk(child, new_scope)
                return

            if node.type == "import_statement":
                for child in node.children:
                    if child.type == "dotted_name":
                        imported_module = child.text.decode("utf-8", errors="ignore")
                        self._add_reference(imported_module, rel)
            elif node.type == "import_from_statement":
                for child in node.children:
                    if child.type in ("dotted_name", "relative_import"):
                        imported_module = child.text.decode("utf-8", errors="ignore")
                        self._add_reference(imported_module, rel)
                        break

            for child in node.children:
                walk(child, current_scope)

        walk(tree.root_node, [])

    def _trace_python_references(self, fp: str, rel: str):
        import tree_sitter_language_pack as tslp
        try:
            with open(fp, "rb") as f:
                content = f.read()
            parser = tslp.get_parser("python")
            tree = parser.parse(content)
        except Exception as e:
            logger.warning(f"Tree-sitter Python parse failed for reference tracing in {fp}: {e}")
            return

        def walk(node, current_scope: str):
            is_def = False
            name = ""
            name_node = None
            if node.type in ("class_definition", "function_definition"):
                name_node = node.child_by_field_name("name")
                if name_node:
                    name = name_node.text.decode("utf-8", errors="ignore")
                    is_def = True
            
            if is_def and name:
                new_scope = f"{current_scope}.{name}" if ":" in current_scope else f"{current_scope}:{name}"
                for child in node.children:
                    if child != name_node:
                        walk(child, new_scope)
                return

            if node.type == "identifier":
                word = node.text.decode("utf-8", errors="ignore")
                if word in self.definitions:
                    for def_loc in self.definitions[word]:
                        if def_loc != current_scope and not def_loc.startswith(current_scope + "."):
                            self._add_reference(word, current_scope)

            for child in node.children:
                walk(child, current_scope)

        walk(tree.root_node, rel)

    def _parse_js_ts_definitions(self, fp: str, rel: str):
        import tree_sitter_language_pack as tslp
        try:
            with open(fp, "rb") as f:
                content = f.read()
            ext = Path(fp).suffix.lower()
            lang = "typescript" if ext in (".ts", ".tsx") else "javascript"
            parser = tslp.get_parser(lang)
            tree = parser.parse(content)
        except Exception as e:
            logger.warning(f"Tree-sitter JS/TS parse failed for {fp}: {e}")
            return

        def walk(node, current_scope: list):
            is_def = False
            name = ""
            if node.type in ("class_declaration", "function_declaration"):
                name_node = node.child_by_field_name("name")
                if name_node:
                    name = name_node.text.decode("utf-8", errors="ignore")
                    is_def = True
            elif node.type == "method_definition":
                name_node = node.child_by_field_name("name")
                if name_node:
                    name = name_node.text.decode("utf-8", errors="ignore")
                    is_def = True
            elif node.type == "variable_declarator":
                val_node = node.child_by_field_name("value")
                if val_node and val_node.type in ("arrow_function", "function_expression"):
                    name_node = node.child_by_field_name("name")
                    if name_node:
                        name = name_node.text.decode("utf-8", errors="ignore")
                        is_def = True
                elif len(current_scope) == 0:
                    name_node = node.child_by_field_name("name")
                    if name_node:
                        def find_js_identifiers(n):
                            if n.type == "identifier":
                                return [n.text.decode("utf-8", errors="ignore")]
                            ids = []
                            for c in n.children:
                                ids.extend(find_js_identifiers(c))
                            return ids
                        for name in find_js_identifiers(name_node):
                            if name and name.isupper():
                                self._add_definition(name, f"{rel}:{name}")

            if is_def and name:
                new_scope = current_scope + [name]
                full_scope = ".".join(new_scope)
                self._add_definition(name, f"{rel}:{full_scope}")
                self._add_definition(rel, f"{rel}:{full_scope}")
                for child in node.children:
                    walk(child, new_scope)
                return

            if node.type == "import_statement":
                for child in node.children:
                    if child.type == "string":
                        import_path = child.text.decode("utf-8", errors="ignore").strip("'\"")
                        self._add_reference(import_path, rel)
                        break
            elif node.type == "call_expression":
                func_node = node.child_by_field_name("function")
                if func_node and func_node.type == "identifier" and func_node.text == b"require":
                    args_node = node.child_by_field_name("arguments")
                    if args_node and args_node.children:
                        for arg in args_node.children:
                            if arg.type == "string":
                                import_path = arg.text.decode("utf-8", errors="ignore").strip("'\"")
                                self._add_reference(import_path, rel)
                                break

            for child in node.children:
                walk(child, current_scope)

        walk(tree.root_node, [])

    def _trace_js_ts_references(self, fp: str, rel: str):
        import tree_sitter_language_pack as tslp
        try:
            with open(fp, "rb") as f:
                content = f.read()
            ext = Path(fp).suffix.lower()
            lang = "typescript" if ext in (".ts", ".tsx") else "javascript"
            parser = tslp.get_parser(lang)
            tree = parser.parse(content)
        except Exception as e:
            logger.warning(f"Tree-sitter JS/TS parse failed for reference tracing in {fp}: {e}")
            return

        def walk(node, current_scope: str):
            is_def = False
            name = ""
            name_node = None
            if node.type in ("class_declaration", "function_declaration"):
                name_node = node.child_by_field_name("name")
                if name_node:
                    name = name_node.text.decode("utf-8", errors="ignore")
                    is_def = True
            elif node.type == "method_definition":
                name_node = node.child_by_field_name("name")
                if name_node:
                    name = name_node.text.decode("utf-8", errors="ignore")
                    is_def = True
            elif node.type == "variable_declarator":
                val_node = node.child_by_field_name("value")
                if val_node and val_node.type in ("arrow_function", "function_expression"):
                    name_node = node.child_by_field_name("name")
                    if name_node:
                        name = name_node.text.decode("utf-8", errors="ignore")
                        is_def = True

            if is_def and name:
                new_scope = f"{current_scope}.{name}" if ":" in current_scope else f"{current_scope}:{name}"
                for child in node.children:
                    if child != name_node:
                        walk(child, new_scope)
                return

            if node.type in ("identifier", "property_identifier"):
                word = node.text.decode("utf-8", errors="ignore")
                if word in self.definitions:
                    for def_loc in self.definitions[word]:
                        if def_loc != current_scope and not def_loc.startswith(current_scope + "."):
                            self._add_reference(word, current_scope)

            for child in node.children:
                walk(child, current_scope)

        walk(tree.root_node, rel)

    def _add_definition(self, symbol: str, location: str):
        self.definitions.setdefault(symbol, []).append(location)
        self.graph.setdefault(symbol, set())

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
