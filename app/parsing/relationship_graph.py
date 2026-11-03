import os
import re
import json
import uuid
from pathlib import Path
from typing import List, Dict, Set, Any, Tuple, Optional
from app.utils.logger import get_logger

logger = get_logger(__name__)


def validate_relationship_graph_file(file_path: str) -> bool:
    """
    Validate that a relationship graph file exists, is non-empty,
    and contains valid JSON representing a dict mapping string symbols to lists.
    """
    if not file_path or not os.path.isfile(file_path):
        return False
    try:
        if os.path.getsize(file_path) < 2:
            return False
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return False
        for k, v in data.items():
            if not isinstance(k, str) or not isinstance(v, list):
                return False
        return True
    except Exception as e:
        logger.debug(f"Relationship graph validation failed for {file_path}: {e}")
        return False


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
            elif ext == ".ipynb":
                self._parse_notebook_definitions(fp, rel)
            elif ext in [".js", ".jsx", ".ts", ".tsx"]:
                self._parse_js_ts_definitions(fp, rel)

        # Second pass: trace references/calls
        for fp, rel in rel_files:
            ext = Path(fp).suffix.lower()
            if ext == ".py":
                self._trace_python_references(fp, rel)
            elif ext == ".ipynb":
                self._trace_notebook_references(fp, rel)
            elif ext in [".js", ".jsx", ".ts", ".tsx"]:
                self._trace_js_ts_references(fp, rel)

        # Convert sets to sorted lists for JSON serialization
        serialized_graph = {}
        for key, val in self.graph.items():
            serialized_graph[key] = sorted(list(val))
        return serialized_graph

    def build_graph_atomic(
        self,
        file_paths: List[str],
        target_dir: str,
        target_filename: str = "relationship_graph.json",
    ) -> Tuple[Dict[str, List[str]], str]:
        """
        Atomically build, serialize, validate, and replace relationship_graph.json:
        1. Computes the relationship graph in memory.
        2. Serializes to a staging temp file (relationship_graph.json.tmp_{uuid}).
        3. Validates the serialized temp file (non-empty, valid JSON, dict mapping str->list).
        4. Atomically replaces target file using os.replace.
        5. If generation, serialization, or validation fails:
           - Staging temp file is deleted.
           - Existing target file is left completely intact.
           - Raises exception to signal failure to caller.
        """
        os.makedirs(target_dir, exist_ok=True)
        temp_path = os.path.join(target_dir, f"{target_filename}.tmp_{uuid.uuid4().hex[:8]}")
        final_path = os.path.join(target_dir, target_filename)

        try:
            graph = self.build_graph(file_paths)
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(graph, f, indent=2)

            if not validate_relationship_graph_file(temp_path):
                raise ValueError(f"Serialized relationship graph failed validation at {temp_path}")

            os.replace(temp_path, final_path)
            logger.info(f"Atomically replaced relationship graph at {final_path} ({len(graph)} symbols)")
            return graph, final_path

        except Exception as e:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception:
                    pass
            logger.error(f"Atomic relationship graph generation failed: {e}")
            raise

    def _walk_python_ast_definitions(self, root_node, scope_prefix: str, file_rel: str):
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
                    for ident in find_identifiers(left_node):
                        if ident and ident.isupper():
                            self._add_definition(ident, f"{scope_prefix}:{ident}")
                            if scope_prefix != file_rel:
                                self._add_definition(ident, f"{file_rel}:{ident}")

            if is_def and name:
                new_scope = current_scope + [name]
                full_scope = ".".join(new_scope)
                self._add_definition(name, f"{scope_prefix}:{full_scope}")
                self._add_definition(file_rel, f"{scope_prefix}:{full_scope}")
                if scope_prefix != file_rel:
                    self._add_definition(scope_prefix, f"{scope_prefix}:{full_scope}")
                for child in node.children:
                    walk(child, new_scope)
                return

            if node.type == "import_statement":
                for child in node.children:
                    if child.type == "dotted_name":
                        imported_module = child.text.decode("utf-8", errors="ignore")
                        self._add_reference(imported_module, scope_prefix)
                        if scope_prefix != file_rel:
                            self._add_reference(imported_module, file_rel)
                    elif child.type == "aliased_import":
                        name_node = child.child_by_field_name("name")
                        alias_node = child.child_by_field_name("alias")
                        mod_name = name_node.text.decode("utf-8", errors="ignore") if name_node else child.text.decode("utf-8", errors="ignore")
                        self._add_reference(mod_name, scope_prefix)
                        if scope_prefix != file_rel:
                            self._add_reference(mod_name, file_rel)
                        if alias_node:
                            alias_name = alias_node.text.decode("utf-8", errors="ignore")
                            self._add_definition(alias_name, f"{scope_prefix}:{alias_name}")
            elif node.type == "import_from_statement":
                module_node = node.child_by_field_name("module_name")
                if not module_node:
                    for c in node.children:
                        if c.type in ("dotted_name", "relative_import"):
                            module_node = c
                            break
                if module_node:
                    imported_module = module_node.text.decode("utf-8", errors="ignore")
                    self._add_reference(imported_module, scope_prefix)
                    if scope_prefix != file_rel:
                        self._add_reference(imported_module, file_rel)

                after_import = False
                for child in node.children:
                    if child.type == "import":
                        after_import = True
                        continue
                    if after_import:
                        if child.type in ("dotted_name", "identifier"):
                            sym = child.text.decode("utf-8", errors="ignore")
                            self._add_reference(sym, scope_prefix)
                            if scope_prefix != file_rel:
                                self._add_reference(sym, file_rel)
                            self._add_definition(sym, f"{scope_prefix}:{sym}")
                        elif child.type == "aliased_import":
                            sym_name_node = child.child_by_field_name("name")
                            alias_node = child.child_by_field_name("alias")
                            sym = sym_name_node.text.decode("utf-8", errors="ignore") if sym_name_node else child.text.decode("utf-8", errors="ignore")
                            self._add_reference(sym, scope_prefix)
                            if scope_prefix != file_rel:
                                self._add_reference(sym, file_rel)
                            self._add_definition(sym, f"{scope_prefix}:{sym}")
                            if alias_node:
                                alias_name = alias_node.text.decode("utf-8", errors="ignore")
                                self._add_definition(alias_name, f"{scope_prefix}:{alias_name}")

            for child in node.children:
                walk(child, current_scope)

        walk(root_node, [])

    def _walk_python_ast_references(self, root_node, scope_prefix: str, file_rel: str):
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

            if node.type in ("identifier", "property_identifier"):
                word = node.text.decode("utf-8", errors="ignore")
                if word in self.definitions:
                    for def_loc in self.definitions[word]:
                        if def_loc != current_scope and not def_loc.startswith(current_scope + "."):
                            self._add_reference(word, current_scope)
                            if current_scope != file_rel:
                                self._add_reference(word, file_rel)

            for child in node.children:
                walk(child, current_scope)

        walk(root_node, scope_prefix)

    def _parse_python_definitions(self, fp: str, rel: str):
        import tree_sitter_language_pack as tslp
        try:
            with open(fp, "rb") as f:
                content = f.read()
            parser = tslp.get_parser("python")
            tree = parser.parse(content)
            self._walk_python_ast_definitions(tree.root_node, rel, rel)
        except Exception as e:
            logger.warning(f"Tree-sitter Python parse failed for {fp}: {e}")

    def _trace_python_references(self, fp: str, rel: str):
        import tree_sitter_language_pack as tslp
        try:
            with open(fp, "rb") as f:
                content = f.read()
            parser = tslp.get_parser("python")
            tree = parser.parse(content)
            self._walk_python_ast_references(tree.root_node, rel, rel)
        except Exception as e:
            logger.warning(f"Tree-sitter Python parse failed for reference tracing in {fp}: {e}")

    def _parse_notebook_definitions(self, fp: str, rel: str):
        from app.parsing.notebook_parser import parse_notebook
        import tree_sitter_language_pack as tslp
        try:
            with open(fp, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            cells = parse_notebook(content, rel)
            parser = tslp.get_parser("python")
            for cell in cells:
                if cell.cell_type != "code" or not cell.clean_code.strip():
                    continue
                cell_scope = f"{rel}[cell_{cell.cell_index}]"
                tree = parser.parse(cell.clean_code.encode("utf-8"))
                self._walk_python_ast_definitions(tree.root_node, cell_scope, rel)
        except Exception as e:
            logger.warning(f"Failed to parse notebook definitions in {fp}: {e}")

    def _trace_notebook_references(self, fp: str, rel: str):
        from app.parsing.notebook_parser import parse_notebook
        import tree_sitter_language_pack as tslp
        try:
            with open(fp, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            cells = parse_notebook(content, rel)
            parser = tslp.get_parser("python")
            for cell in cells:
                if cell.cell_type != "code" or not cell.clean_code.strip():
                    continue
                cell_scope = f"{rel}[cell_{cell.cell_index}]"
                tree = parser.parse(cell.clean_code.encode("utf-8"))
                self._walk_python_ast_references(tree.root_node, cell_scope, rel)
        except Exception as e:
            logger.warning(f"Failed to trace notebook references in {fp}: {e}")

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
