import os
import tempfile
import json
from pathlib import Path
from app.parsing.relationship_graph import RelationshipGraphBuilder
from app.retrieval.query_router import (
    classify_query,
    QueryMode,
    _is_relationship_query,
    extract_relationship_target,
)


def test_relationship_query_detection():
    # True relationship queries
    assert _is_relationship_query("what calls load_documents?") is True
    assert _is_relationship_query("who uses CodeSplitter") is True
    assert _is_relationship_query("what depends on prompts.py") is True
    assert _is_relationship_query("what would break if I deleted qa_service?") is True
    assert _is_relationship_query("where is load_documents called") is True
    assert _is_relationship_query("what imports app.parsing.code_parser") is True
    assert _is_relationship_query("What functions call classify_query?") is True
    assert _is_relationship_query("What would break if I deleted app/retrieval/retriever.py?") is True
    
    # Verify classify_query output
    assert classify_query("What functions call classify_query?") == QueryMode.RELATIONSHIP
    assert classify_query("What would break if I deleted app/retrieval/retriever.py?") == QueryMode.RELATIONSHIP
    
    # False relationship queries
    assert _is_relationship_query("how does load_documents work?") is False
    assert _is_relationship_query("show me where prompts.py is") is False


def test_relationship_target_extraction():
    assert extract_relationship_target("what calls load_documents?") == "load_documents"
    assert extract_relationship_target("who uses 'CodeSplitter'") == "CodeSplitter"
    assert extract_relationship_target('what depends on "prompts.py"') == "prompts.py"
    assert extract_relationship_target("what would break if I deleted qa_service") == "qa_service"
    assert extract_relationship_target("where is load_documents called?") == "load_documents"
    assert extract_relationship_target("what imports app.parsing.code_parser") == "app.parsing.code_parser"
    assert extract_relationship_target("What functions call classify_query?") == "classify_query"
    assert extract_relationship_target("What would break if I deleted app/retrieval/retriever.py?") == "app/retrieval/retriever.py"


def test_relationship_graph_builder():
    with tempfile.TemporaryDirectory() as tmp_dir:
        # Create a mock python file with decorators, multiline signatures, and nested classes
        py_file_content = """
import os
from math import sqrt
from another_module import helper_func

@some_decorator
class TargetClass:
    def method_one(self):
        print("Hello")

    class NestedClass:
        def nested_method(self):
            pass

def multiline_func(
    arg_one,
    arg_two
):
    obj = TargetClass()
    obj.method_one()
    helper_func()
"""
        py_file_path = os.path.join(tmp_dir, "app.py")
        with open(py_file_path, "w", encoding="utf-8") as f:
            f.write(py_file_content)

        # Create mock JS file
        js_file_content = """
import { multiline_func } from './app.py';

class ClientClass {
    run() {
        multiline_func();
    }
}
"""
        js_file_path = os.path.join(tmp_dir, "client.js")
        with open(js_file_path, "w", encoding="utf-8") as f:
            f.write(js_file_content)

        # Build graph
        builder = RelationshipGraphBuilder(tmp_dir)
        graph = builder.build_graph([py_file_path, js_file_path])
        
        # TargetClass should have "app.py:multiline_func" as referrer
        assert "app.py:multiline_func" in graph.get("TargetClass", [])
        
        # NestedClass should be defined
        assert any("NestedClass" in loc for loc in builder.definitions.get("NestedClass", []))
        assert any("nested_method" in loc for loc in builder.definitions.get("nested_method", []))
        
        # multiline_func is called in client.js:ClientClass.run
        assert "client.js:ClientClass.run" in graph.get("multiline_func", [])
        
        # client.js imports app.py, so app.py should have client.js as referrer
        assert "client.js" in graph.get("app.py", [])
