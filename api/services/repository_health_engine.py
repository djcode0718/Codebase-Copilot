"""
api/services/repository_health_engine.py
---------------------------------------
Explainable repository health intelligence engine.

The engine scans repository files, runs category analyzers, computes a dynamic
weighted score, attaches evidence for every deduction, and emits prioritized
recommendations.
"""

from __future__ import annotations

import json
import ast
import math
import os
import re
import statistics
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from app.utils.logger import get_logger


logger = get_logger(__name__)


def _resolve_repos_dir() -> str:
    # Lazy import avoids eager config dependency at module import time.
    from app.config import get_repos_dir

    return get_repos_dir()


CATEGORY_ORDER: List[str] = [
    "Architecture",
    "Security",
    "Testing",
    "Documentation",
    "Performance",
    "Maintainability",
    "Technical Debt",
    "Dependencies",
    "Code Quality",
    "Scalability",
    "Observability",
    "Developer Experience",
]


SEVERITY_MULTIPLIER = {
    "low": 0.8,
    "medium": 1.2,
    "high": 1.8,
    "critical": 2.5,
}


@dataclass
class RepoFile:
    path: str
    rel_path: str
    ext: str
    content: str
    lines: int


@dataclass
class Finding:
    id: str
    category: str
    finding_type: str
    severity: str
    title: str
    details: str
    evidence: Dict[str, Any] = field(default_factory=dict)
    recommendation: Optional[str] = None
    affected_files: List[str] = field(default_factory=list)
    affected_modules: List[str] = field(default_factory=list)
    expected_score_gain: int = 0


@dataclass
class CategoryResult:
    category: str
    score: int
    explanation: str
    findings: List[Finding]
    affected_files: List[str]
    affected_modules: List[str]
    confidence: float
    trend: int = 0


@dataclass
class Snapshot:
    repo_id: str
    repo_name: str
    repo_path: str
    files: List[RepoFile]
    language_counts: Counter
    framework_signals: Counter
    module_counts: Counter


class BaseAnalyzer:
    category: str = "Base"

    def analyze(self, snapshot: Snapshot) -> CategoryResult:
        raise NotImplementedError

    def _score_from_findings(self, findings: Sequence[Finding], signal_count: int) -> int:
        if signal_count <= 0:
            return 50
        risk = 0.0
        positives = 0
        for finding in findings:
            if finding.finding_type == "problem":
                risk += SEVERITY_MULTIPLIER.get(finding.severity, 1.0)
            else:
                positives += 1

        risk_density = risk / max(1.0, math.log1p(signal_count))
        positive_boost = positives / max(1.0, math.sqrt(signal_count))
        score = 100.0 * math.exp(-risk_density / max(0.5, math.log1p(signal_count)))
        score = min(100.0, score + (positive_boost * 5.0))
        return int(max(0, min(100, round(score))))


class ArchitectureAnalyzer(BaseAnalyzer):
    category = "Architecture"

    def analyze(self, snapshot: Snapshot) -> CategoryResult:
        findings: List[Finding] = []
        py_files = [f for f in snapshot.files if f.ext == ".py"]
        ts_files = [f for f in snapshot.files if f.ext in {".ts", ".tsx", ".js", ".jsx"}]
        code_files = py_files + ts_files

        import_graph: Dict[str, List[str]] = defaultdict(list)
        for f in code_files:
            module = f.rel_path.replace("\\", "/")
            for match in re.findall(r"^\s*(?:from\s+([\w\.]+)\s+import|import\s+([\w\.]+))", f.content, flags=re.MULTILINE):
                dep = (match[0] or match[1]).replace(".", "/")
                import_graph[module].append(dep)
            for match in re.findall(r"from\s+['\"](\.?[^'\"]+)['\"]", f.content):
                if match.startswith("."):
                    dep = os.path.normpath(os.path.join(os.path.dirname(module), match)).replace("\\", "/")
                    import_graph[module].append(dep)

        cycles = self._detect_cycles(import_graph)
        for cycle in cycles[:5]:
            findings.append(Finding(
                id=str(uuid.uuid4()),
                category=self.category,
                finding_type="problem",
                severity="medium",
                title="Circular dependency detected",
                details=f"Dependency cycle found: {' -> '.join(cycle)}",
                evidence={"cycle": cycle},
                recommendation="Break the cycle by extracting shared interfaces or moving orchestration into a higher layer.",
                affected_files=[c for c in cycle if c.endswith((".py", ".ts", ".tsx", ".js", ".jsx"))],
                affected_modules=[c.split('/')[0] for c in cycle if '/' in c],
                expected_score_gain=3,
            ))

        dir_counts = Counter([f.rel_path.split("/")[0] for f in code_files if "/" in f.rel_path])
        for module, count in dir_counts.items():
            if count >= max(8, int(statistics.median(dir_counts.values() or [1]) * 2.4)):
                findings.append(Finding(
                    id=str(uuid.uuid4()),
                    category=self.category,
                    finding_type="problem",
                    severity="low",
                    title="High module coupling hotspot",
                    details=f"Module '{module}' contains {count} code files, suggesting tight internal coupling.",
                    evidence={"module": module, "file_count": count},
                    recommendation="Split this module by domain boundaries and move cross-cutting logic into shared utilities.",
                    affected_files=[f.rel_path for f in code_files if f.rel_path.startswith(f"{module}/")][:10],
                    affected_modules=[module],
                    expected_score_gain=2,
                ))

        if len(dir_counts) >= 4:
            findings.append(Finding(
                id=str(uuid.uuid4()),
                category=self.category,
                finding_type="positive",
                severity="low",
                title="Modular folder structure",
                details=f"Repository uses {len(dir_counts)} top-level code modules, which supports boundary separation.",
                evidence={"modules": list(dir_counts.keys())[:12]},
            ))

        signal_count = len(code_files) + len(import_graph) + len(dir_counts)
        score = self._score_from_findings(findings, signal_count)
        explanation = (
            "Architecture score reflects dependency direction, cycle detection, and module boundary cohesion. "
            f"Scanned {len(code_files)} code files across {len(dir_counts)} modules."
        )
        return CategoryResult(
            category=self.category,
            score=score,
            explanation=explanation,
            findings=findings,
            affected_files=sorted({p for f in findings for p in f.affected_files})[:30],
            affected_modules=sorted({m for f in findings for m in f.affected_modules})[:20],
            confidence=min(1.0, math.log1p(len(code_files)) / 6.0),
        )

    def _detect_cycles(self, graph: Dict[str, List[str]]) -> List[List[str]]:
        """DFS cycle detection using *exact* key lookup.

        The import graph keys are relative file paths such as
        ``api/services/supabase_service.py``.  Deps produced by the regex are
        module-style identifiers converted to slash notation, e.g.
        ``supabase`` or ``api/services``.  We resolve each dep to a graph key
        only when there is a genuine path match, avoiding the false-positive
        self-cycles that substring matching would produce
        (e.g. dep ``supabase`` being found inside the key
        ``api/services/supabase_service.py``).
        """
        # Build a lookup: canonical dep string → graph key
        # Try: dep, dep + ".py", dep + "/index.ts", dep + "/index.js"
        _key_set = set(graph.keys())

        def _resolve_dep(dep: str) -> Optional[str]:
            """Resolve a dep string to an exact graph key, or return None."""
            for candidate in (dep, dep + ".py", dep + ".ts", dep + ".tsx",
                              dep + "/index.ts", dep + "/index.js"):
                if candidate in _key_set:
                    return candidate
            return None

        cycles: List[List[str]] = []
        visiting: Dict[str, int] = {}
        stack: List[str] = []

        def dfs(node: str) -> None:
            visiting[node] = 1
            stack.append(node)
            for dep in graph.get(node, []):
                target = _resolve_dep(dep)
                if not target:
                    continue
                state = visiting.get(target, 0)
                if state == 0:
                    dfs(target)
                elif state == 1 and target in stack:
                    idx = stack.index(target)
                    cycle = stack[idx:] + [target]
                    if cycle not in cycles:
                        cycles.append(cycle)
            stack.pop()
            visiting[node] = 2

        for node in list(graph.keys()):
            if visiting.get(node, 0) == 0:
                dfs(node)
        return cycles


class SecurityAnalyzer(BaseAnalyzer):
    category = "Security"

    SECRET_PATTERNS = [
        (r"(?i)(api[_-]?key|secret|token|password)\s*=\s*['\"][^'\"]{10,}['\"]", "Possible hardcoded secret"),
        (r"AKIA[0-9A-Z]{16}", "Possible AWS key"),
    ]

    def analyze(self, snapshot: Snapshot) -> CategoryResult:
        findings: List[Finding] = []
        endpoint_files = [f for f in snapshot.files if "/routers/" in f.rel_path.replace("\\", "/") and f.ext == ".py"]

        _source_exts = {".py", ".js", ".ts", ".tsx", ".jsx", ".rb", ".go", ".java", ".cs", ".php"}
        for f in snapshot.files:
            if f.ext not in _source_exts:
                continue
            for pattern, label in self.SECRET_PATTERNS:
                if re.search(pattern, f.content):
                    findings.append(Finding(
                        id=str(uuid.uuid4()),
                        category=self.category,
                        finding_type="problem",
                        severity="high",
                        title=label,
                        details=f"Potential secret pattern matched in {f.rel_path}.",
                        evidence={"pattern": pattern},
                        recommendation="Move secrets to environment variables and rotate exposed credentials.",
                        affected_files=[f.rel_path],
                        affected_modules=[f.rel_path.split('/')[0]],
                        expected_score_gain=5,
                    ))

            if re.search(r"logger\.(?:info|debug)\([^\n]*(password|token|secret)", f.content, flags=re.IGNORECASE):
                findings.append(Finding(
                    id=str(uuid.uuid4()),
                    category=self.category,
                    finding_type="problem",
                    severity="medium",
                    title="Sensitive data in logs",
                    details=f"Logging statement in {f.rel_path} appears to include credentials or tokens.",
                    evidence={"file": f.rel_path},
                    recommendation="Mask secrets before logging and avoid emitting auth material.",
                    affected_files=[f.rel_path],
                    affected_modules=[f.rel_path.split('/')[0]],
                    expected_score_gain=3,
                ))

        public_endpoints = []
        for f in endpoint_files:
            blocks = re.findall(r"@router\.(?:get|post|put|delete|patch)\([^\)]*\)\s*\n\s*async\s+def\s+([\w_]+)\((.*?)\):", f.content, flags=re.DOTALL)
            for fn_name, signature in blocks:
                if "Depends(get_current_user)" not in signature and "get_current_user" not in signature:
                    public_endpoints.append((f.rel_path, fn_name))

        for rel_path, fn_name in public_endpoints[:10]:
            findings.append(Finding(
                id=str(uuid.uuid4()),
                category=self.category,
                finding_type="problem",
                severity="high",
                title="Endpoint missing authentication guard",
                details=f"Endpoint '{fn_name}' in {rel_path} does not declare user dependency checks.",
                evidence={"endpoint": fn_name},
                recommendation="Require authentication/authorization dependency for non-public endpoints.",
                affected_files=[rel_path],
                affected_modules=[rel_path.split('/')[0]],
                expected_score_gain=4,
            ))

        if not public_endpoints:
            findings.append(Finding(
                id=str(uuid.uuid4()),
                category=self.category,
                finding_type="positive",
                severity="low",
                title="Protected API signatures",
                details="No unauthenticated endpoints were detected in scanned router signatures.",
                evidence={"router_files": len(endpoint_files)},
            ))

        signal_count = len(snapshot.files) + len(endpoint_files)
        score = self._score_from_findings(findings, signal_count)
        explanation = (
            "Security score is based on authentication guards, hardcoded secret detection, "
            "and sensitive logging patterns."
        )
        return CategoryResult(
            category=self.category,
            score=score,
            explanation=explanation,
            findings=findings,
            affected_files=sorted({p for f in findings for p in f.affected_files})[:30],
            affected_modules=sorted({m for f in findings for m in f.affected_modules})[:20],
            confidence=min(1.0, math.log1p(signal_count) / 6.0),
        )


class TestingAnalyzer(BaseAnalyzer):
    category = "Testing"

    def analyze(self, snapshot: Snapshot) -> CategoryResult:
        findings: List[Finding] = []
        test_files = [f for f in snapshot.files if "/test" in f.rel_path.lower() or f.rel_path.lower().startswith("tests/")]
        prod_files = [f for f in snapshot.files if f.ext in {".py", ".ts", ".tsx", ".js", ".jsx"} and "test" not in f.rel_path.lower()]

        if prod_files:
            coverage_ratio = len(test_files) / len(prod_files)
            if coverage_ratio < 0.25:
                findings.append(Finding(
                    id=str(uuid.uuid4()),
                    category=self.category,
                    finding_type="problem",
                    severity="high",
                    title="Low test-to-code coverage proxy",
                    details=f"Detected {len(test_files)} test files for {len(prod_files)} production files (ratio {coverage_ratio:.2f}).",
                    evidence={"test_files": len(test_files), "production_files": len(prod_files), "ratio": round(coverage_ratio, 3)},
                    recommendation="Prioritize tests for critical modules and increase negative-case coverage.",
                    affected_files=[f.rel_path for f in prod_files[:10]],
                    affected_modules=[f.rel_path.split('/')[0] for f in prod_files[:10]],
                    expected_score_gain=6,
                ))

        missing_test_targets = []
        test_names = " ".join([f.rel_path.lower() for f in test_files])
        test_content_signals = " ".join((f.content.lower()[:10_000] for f in test_files))
        test_signals = f"{test_names} {test_content_signals}"
        generic_tokens = {
            "api",
            "app",
            "services",
            "service",
            "routers",
            "router",
            "models",
            "utils",
            "common",
        }

        def _is_module_mapped(rel_path: str, stem: str) -> bool:
            if stem in test_signals:
                return True

            tokens: List[str] = []
            cleaned_stem = stem.replace("_service", "")
            if cleaned_stem and cleaned_stem != stem:
                tokens.append(cleaned_stem)
            tokens.extend([p for p in cleaned_stem.split("_") if len(p) >= 5])

            parts = [p for p in rel_path.lower().split("/") if p]
            tokens.extend([p for p in parts if len(p) >= 5 and p not in generic_tokens])

            deduped = sorted(set(t for t in tokens if t not in generic_tokens))
            return any(token in test_signals for token in deduped)

        for f in prod_files[:400]:
            rel_path = f.rel_path.replace("\\", "/")
            # Skip frontend UI files (covered by browser/e2e tests, not naming convention)
            if "frontend/" in rel_path:
                continue
            # Skip root-level standalone scripts (debug, evaluation helpers)
            if "/" not in rel_path:
                continue
            # Skip migration scripts
            if "migration" in rel_path.lower() or "/migrations/" in rel_path:
                continue
            stem = os.path.splitext(os.path.basename(f.rel_path))[0].lower()
            # Skip package markers and private modules
            if stem.startswith("__") or len(stem) <= 4:
                continue
            if not _is_module_mapped(rel_path, stem):
                missing_test_targets.append(f.rel_path)

        if missing_test_targets:
            findings.append(Finding(
                id=str(uuid.uuid4()),
                category=self.category,
                finding_type="problem",
                severity="medium",
                title="Production modules without mapped tests",
                details=f"{len(missing_test_targets)} files appear to have no corresponding tests by naming convention.",
                evidence={"count": len(missing_test_targets)},
                recommendation="Add unit tests for uncovered modules and integration tests for API/service boundaries.",
                affected_files=missing_test_targets[:20],
                affected_modules=[p.split('/')[0] for p in missing_test_targets[:20] if '/' in p],
                expected_score_gain=5,
            ))

        negative_signal = 0
        for f in test_files:
            if re.search(r"(invalid|error|raises|exception|negative)", f.content, flags=re.IGNORECASE):
                negative_signal += 1

        if negative_signal:
            findings.append(Finding(
                id=str(uuid.uuid4()),
                category=self.category,
                finding_type="positive",
                severity="low",
                title="Negative-path tests detected",
                details=f"{negative_signal} test files include negative/error-path assertions.",
                evidence={"negative_test_files": negative_signal},
            ))

        signal_count = len(prod_files) + len(test_files)
        score = self._score_from_findings(findings, signal_count)
        logger.info(
            "TestingAnalyzer score=%s prod_files=%s test_files=%s missing_targets=%s negative_tests=%s",
            score,
            len(prod_files),
            len(test_files),
            len(missing_test_targets),
            negative_signal,
        )
        explanation = "Testing score estimates structural test coverage and resilience checks using repository test artifacts."
        return CategoryResult(
            category=self.category,
            score=score,
            explanation=explanation,
            findings=findings,
            affected_files=sorted({p for f in findings for p in f.affected_files})[:30],
            affected_modules=sorted({m for f in findings for m in f.affected_modules if m})[:20],
            confidence=min(1.0, math.log1p(len(prod_files) + len(test_files)) / 6.0),
        )


class DocumentationAnalyzer(BaseAnalyzer):
    category = "Documentation"

    def analyze(self, snapshot: Snapshot) -> CategoryResult:
        findings: List[Finding] = []
        docs = [f for f in snapshot.files if f.ext in {".md", ".rst", ".txt"}]
        readme = next((f for f in docs if os.path.basename(f.rel_path).lower().startswith("readme")), None)

        if not readme:
            findings.append(Finding(
                id=str(uuid.uuid4()),
                category=self.category,
                finding_type="problem",
                severity="high",
                title="README missing",
                details="No README file was detected at repository root.",
                recommendation="Add a README with setup, architecture overview, and key workflows.",
                expected_score_gain=8,
            ))
        else:
            if readme.lines < 40:
                findings.append(Finding(
                    id=str(uuid.uuid4()),
                    category=self.category,
                    finding_type="problem",
                    severity="medium",
                    title="README lacks depth",
                    details=f"README has {readme.lines} lines; onboarding and architecture details may be incomplete.",
                    evidence={"readme": readme.rel_path, "lines": readme.lines},
                    recommendation="Expand README with architecture map, local run steps, and troubleshooting.",
                    affected_files=[readme.rel_path],
                    expected_score_gain=4,
                ))
            else:
                findings.append(Finding(
                    id=str(uuid.uuid4()),
                    category=self.category,
                    finding_type="positive",
                    severity="low",
                    title="Comprehensive README present",
                    details=f"README has {readme.lines} lines, indicating substantial onboarding content.",
                    evidence={"readme": readme.rel_path, "lines": readme.lines},
                ))

        if not any("quick_start" in f.rel_path.lower() or "installation" in f.rel_path.lower() for f in docs):
            findings.append(Finding(
                id=str(uuid.uuid4()),
                category=self.category,
                finding_type="problem",
                severity="medium",
                title="Setup documentation gap",
                details="No dedicated quick-start or installation guide was detected.",
                recommendation="Add reproducible setup steps for developers and CI environments.",
                affected_files=[f.rel_path for f in docs[:8]],
                expected_score_gain=3,
            ))

        signal_count = len(snapshot.files) + len(docs)
        score = self._score_from_findings(findings, signal_count)
        explanation = "Documentation score evaluates discoverability of setup guides, README depth, and supporting docs."
        return CategoryResult(
            category=self.category,
            score=score,
            explanation=explanation,
            findings=findings,
            affected_files=sorted({p for f in findings for p in f.affected_files})[:30],
            affected_modules=sorted({p.split('/')[0] for p in {a for f in findings for a in f.affected_files} if '/' in p})[:20],
            confidence=min(1.0, math.log1p(len(docs) + 1) / 5.0),
        )


class PerformanceAnalyzer(BaseAnalyzer):
    category = "Performance"

    def analyze(self, snapshot: Snapshot) -> CategoryResult:
        findings: List[Finding] = []
        for f in snapshot.files:
            if f.ext not in {".py", ".ts", ".tsx", ".js", ".jsx"}:
                continue
            if re.search(r"for\s+.*:\s*\n\s*.*(?:select\(|query\(|execute\()", f.content, flags=re.IGNORECASE):
                findings.append(Finding(
                    id=str(uuid.uuid4()),
                    category=self.category,
                    finding_type="problem",
                    severity="high",
                    title="Potential N+1 query pattern",
                    details=f"Loop + query pattern detected in {f.rel_path}.",
                    recommendation="Batch query access and prefetch data outside loops.",
                    affected_files=[f.rel_path],
                    affected_modules=[f.rel_path.split('/')[0]],
                    expected_score_gain=5,
                ))
            blocking_hits = self._detect_blocking_calls_in_async_scope(f)
            if blocking_hits:
                findings.append(Finding(
                    id=str(uuid.uuid4()),
                    category=self.category,
                    finding_type="problem",
                    severity="medium",
                    title="Blocking call in async context",
                    details=(
                        f"Blocking I/O pattern detected in async flow in {f.rel_path}: "
                        f"{', '.join(blocking_hits[:3])}."
                    ),
                    recommendation="Replace blocking calls with non-blocking alternatives and async clients.",
                    affected_files=[f.rel_path],
                    affected_modules=[f.rel_path.split('/')[0]],
                    expected_score_gain=4,
                ))

        caching_signals = sum(
            1 for f in snapshot.files
            if re.search(r"(lru_cache|redis|cache|memoize)", f.content, flags=re.IGNORECASE)
        )
        if caching_signals:
            findings.append(Finding(
                id=str(uuid.uuid4()),
                category=self.category,
                finding_type="positive",
                severity="low",
                title="Caching strategy signals detected",
                details=f"{caching_signals} files mention caching constructs.",
                evidence={"caching_signals": caching_signals},
            ))

        signal_count = len(snapshot.files) + caching_signals
        score = self._score_from_findings(findings, signal_count)
        logger.info(
            "PerformanceAnalyzer score=%s findings=%s caching_signals=%s",
            score,
            len(findings),
            caching_signals,
        )
        explanation = "Performance score checks for N+1 risk patterns, blocking async calls, and caching signals."
        return CategoryResult(
            category=self.category,
            score=score,
            explanation=explanation,
            findings=findings,
            affected_files=sorted({p for f in findings for p in f.affected_files})[:30],
            affected_modules=sorted({m for f in findings for m in f.affected_modules})[:20],
            confidence=min(1.0, math.log1p(signal_count) / 6.0),
        )

    def _detect_blocking_calls_in_async_scope(self, repo_file: RepoFile) -> List[str]:
        if repo_file.ext != ".py" or "async def" not in repo_file.content:
            return []

        try:
            tree = ast.parse(repo_file.content)
        except Exception:
            return []

        hits: List[str] = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.AsyncFunctionDef):
                continue
            for sub_node in ast.walk(node):
                if not isinstance(sub_node, ast.Call):
                    continue
                func = sub_node.func
                if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
                    qualifier = f"{func.value.id}.{func.attr}"
                    if qualifier == "time.sleep":
                        hits.append(f"{node.name}:time.sleep")
                    elif func.value.id == "requests" and func.attr in {"get", "post", "put", "delete"}:
                        hits.append(f"{node.name}:requests.{func.attr}")
        return sorted(set(hits))


class MaintainabilityAnalyzer(BaseAnalyzer):
    category = "Maintainability"

    def analyze(self, snapshot: Snapshot) -> CategoryResult:
        findings: List[Finding] = []
        code_files = [f for f in snapshot.files if f.ext in {".py", ".ts", ".tsx", ".js", ".jsx"}]

        duplicated_blocks: Dict[str, List[str]] = defaultdict(list)
        for f in code_files:
            lines = [ln.strip() for ln in f.content.splitlines() if ln.strip() and not ln.strip().startswith(("#", "//"))]
            for i in range(0, max(0, len(lines) - 6), 3):
                block = "\n".join(lines[i:i + 6])
                if len(block) > 120:
                    # Skip blocks that are primarily import declarations (shared by design)
                    first_line = lines[i] if lines[i:] else ""
                    if first_line.startswith(("from ", "import ", "from api", "from app")):
                        continue
                    duplicated_blocks[block].append(f.rel_path)

        duplicate_hits = [(block, files) for block, files in duplicated_blocks.items() if len(set(files)) > 1]
        if duplicate_hits:
            block, files = duplicate_hits[0]
            findings.append(Finding(
                id=str(uuid.uuid4()),
                category=self.category,
                finding_type="problem",
                severity="medium",
                title="Duplicate logic detected",
                details=f"Near-identical code block appears in {len(set(files))} files.",
                evidence={"snippet": block[:200]},
                recommendation="Extract shared utility/helper to remove duplicate logic.",
                affected_files=sorted(set(files))[:20],
                affected_modules=[p.split('/')[0] for p in sorted(set(files))[:20] if '/' in p],
                expected_score_gain=4,
            ))

        long_functions = []
        _fn_pattern = re.compile(
            r"\s*("
            r"def\s|async\s+def\s"           # Python
            r"|function\s+\w"                 # plain JS/TS function
            r"|async\s+function\s+\w"         # async JS/TS function
            r"|export\s+(?:default\s+)?(?:async\s+)?function\s+\w"  # exported TS/JS
            r"|class\s+\w"                    # class definitions reset the tracker
            r")"
        )
        for f in code_files:
            # Frontend component files (TSX/JSX) naturally have larger render
            # functions; use a relaxed threshold to avoid false positives.
            is_frontend_component = f.ext in {".tsx", ".jsx"}
            threshold = 200 if is_frontend_component else 120
            lines = f.content.splitlines()
            start = None
            for idx, line in enumerate(lines):
                if _fn_pattern.match(line):
                    start = idx
                if start is not None and idx - start > threshold and line.strip() == "":
                    long_functions.append((f.rel_path, idx - start))
                    start = None

        for rel_path, span in long_functions[:8]:
            findings.append(Finding(
                id=str(uuid.uuid4()),
                category=self.category,
                finding_type="problem",
                severity="medium",
                title="Long function detected",
                details=f"Function-like block in {rel_path} spans approximately {span} lines.",
                recommendation="Split long methods into smaller units with single responsibilities.",
                affected_files=[rel_path],
                affected_modules=[rel_path.split('/')[0]],
                expected_score_gain=3,
            ))

        signal_count = len(code_files) + len(duplicate_hits) + len(long_functions)
        score = self._score_from_findings(findings, signal_count)
        explanation = "Maintainability score evaluates duplication hotspots and oversized function complexity risk."
        return CategoryResult(
            category=self.category,
            score=score,
            explanation=explanation,
            findings=findings,
            affected_files=sorted({p for f in findings for p in f.affected_files})[:30],
            affected_modules=sorted({m for f in findings for m in f.affected_modules})[:20],
            confidence=min(1.0, math.log1p(len(code_files) + 1) / 6.0),
        )


class TechnicalDebtAnalyzer(BaseAnalyzer):
    category = "Technical Debt"

    def analyze(self, snapshot: Snapshot) -> CategoryResult:
        findings: List[Finding] = []
        debt_markers = []
        legacy_markers = []

        for f in snapshot.files:
            # Skip framework/analysis files that contain detection patterns as string literals
            if "repository_health_engine" in f.rel_path:
                continue
            # Only detect debt markers inside actual code comments (# or //)
            marker_hits = re.findall(
                r"(?:^|(?<=\n))\s*(?:#|//)[^\n]*(TODO|FIXME|HACK|DEPRECATED|LEGACY)\b",
                f.content,
                flags=re.IGNORECASE,
            )
            if marker_hits:
                debt_markers.append((f.rel_path, len(marker_hits)))
            # Only flag legacy/deprecated references that appear in comments
            if re.search(
                r"(?:#|//)[^\n]*(deprecated|legacy|temporary\s+workaround)",
                f.content,
                flags=re.IGNORECASE,
            ):
                legacy_markers.append(f.rel_path)

        if debt_markers:
            total_markers = sum(c for _, c in debt_markers)
            findings.append(Finding(
                id=str(uuid.uuid4()),
                category=self.category,
                finding_type="problem",
                severity="medium",
                title="Debt markers present",
                details=f"Detected {total_markers} TODO/FIXME/HACK-style markers.",
                evidence={"top_files": debt_markers[:10]},
                recommendation="Convert top debt markers into tracked issues with owners and due dates.",
                affected_files=[p for p, _ in debt_markers[:20]],
                affected_modules=[p.split('/')[0] for p, _ in debt_markers[:20] if '/' in p],
                expected_score_gain=4,
            ))

        if legacy_markers:
            findings.append(Finding(
                id=str(uuid.uuid4()),
                category=self.category,
                finding_type="problem",
                severity="low",
                title="Legacy pattern references detected",
                details=f"{len(legacy_markers)} files reference deprecated or legacy implementation paths.",
                recommendation="Plan progressive modernization for legacy call paths.",
                affected_files=legacy_markers[:20],
                affected_modules=[p.split('/')[0] for p in legacy_markers[:20] if '/' in p],
                expected_score_gain=2,
            ))

        signal_count = len(snapshot.files) + len(debt_markers) + len(legacy_markers)
        score = self._score_from_findings(findings, signal_count)
        explanation = "Technical debt score tracks explicit debt markers, legacy references, and cleanup backlog signals."
        return CategoryResult(
            category=self.category,
            score=score,
            explanation=explanation,
            findings=findings,
            affected_files=sorted({p for f in findings for p in f.affected_files})[:30],
            affected_modules=sorted({m for f in findings for m in f.affected_modules})[:20],
            confidence=min(1.0, math.log1p(signal_count) / 6.0),
        )


class DependencyAnalyzer(BaseAnalyzer):
    category = "Dependencies"

    def analyze(self, snapshot: Snapshot) -> CategoryResult:
        findings: List[Finding] = []
        dep_files = [f for f in snapshot.files if os.path.basename(f.rel_path) in {"requirements.txt", "package.json", "poetry.lock", "Pipfile", "Pipfile.lock"}]

        packages = set()
        pinned_versions = 0
        unpinned_versions = 0
        for f in dep_files:
            if f.rel_path.endswith("package.json"):
                try:
                    payload = json.loads(f.content)
                    for section in ("dependencies", "devDependencies"):
                        for name, version in (payload.get(section) or {}).items():
                            packages.add(name)
                            if isinstance(version, str) and re.search(r"\d", version):
                                pinned_versions += 1
                            else:
                                unpinned_versions += 1
                except Exception:
                    pass
            else:
                for line in f.content.splitlines():
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    pkg = re.split(r"[<>=~!]", line)[0].strip()
                    packages.add(pkg)
                    if re.search(r"(==|>=|~=|\^|\d+\.\d+)", line):
                        pinned_versions += 1
                    else:
                        unpinned_versions += 1

        if unpinned_versions > max(0, pinned_versions // 2):
            findings.append(Finding(
                id=str(uuid.uuid4()),
                category=self.category,
                finding_type="problem",
                severity="medium",
                title="Unpinned dependency versions",
                details=f"Detected {unpinned_versions} unpinned dependency declarations.",
                recommendation="Pin dependency ranges for deterministic builds and safer upgrades.",
                affected_files=[f.rel_path for f in dep_files],
                expected_score_gain=3,
            ))

        if packages:
            findings.append(Finding(
                id=str(uuid.uuid4()),
                category=self.category,
                finding_type="positive",
                severity="low",
                title="Dependency manifests detected",
                details=f"Detected {len(packages)} package declarations across dependency manifests.",
                evidence={"packages": len(packages)},
            ))

        signal_count = len(dep_files) + len(packages)
        score = self._score_from_findings(findings, signal_count)
        explanation = "Dependency score reflects dependency manifest hygiene and version pinning discipline."
        return CategoryResult(
            category=self.category,
            score=score,
            explanation=explanation,
            findings=findings,
            affected_files=sorted({p for f in findings for p in f.affected_files})[:30],
            affected_modules=sorted({p.split('/')[0] for p in {a for f in findings for a in f.affected_files} if '/' in p})[:20],
            confidence=min(1.0, math.log1p(signal_count + 1) / 6.0),
        )


class CodeQualityAnalyzer(BaseAnalyzer):
    category = "Code Quality"

    def analyze(self, snapshot: Snapshot) -> CategoryResult:
        findings: List[Finding] = []
        config_files = {os.path.basename(f.rel_path).lower() for f in snapshot.files}
        lint_signals = {
            name for name in config_files
            if name in {"pyproject.toml", "ruff.toml", ".eslintrc", ".eslintrc.js", ".eslintrc.json", "eslint.config.mjs"}
        }

        if not lint_signals:
            findings.append(Finding(
                id=str(uuid.uuid4()),
                category=self.category,
                finding_type="problem",
                severity="medium",
                title="Lint configuration missing",
                details="No standard lint configuration files were detected.",
                recommendation="Introduce linting/formatting standards and enforce them in CI.",
                expected_score_gain=4,
            ))
        else:
            findings.append(Finding(
                id=str(uuid.uuid4()),
                category=self.category,
                finding_type="positive",
                severity="low",
                title="Linting standards detected",
                details=f"Detected lint config files: {', '.join(sorted(lint_signals))}.",
                evidence={"configs": sorted(lint_signals)},
            ))

        signal_count = len(snapshot.files) + len(lint_signals)
        score = self._score_from_findings(findings, signal_count)
        explanation = "Code quality score uses lint/format policy signals and consistency scaffolding indicators."
        return CategoryResult(
            category=self.category,
            score=score,
            explanation=explanation,
            findings=findings,
            affected_files=sorted({p for f in findings for p in f.affected_files})[:30],
            affected_modules=sorted({m for f in findings for m in f.affected_modules})[:20],
            confidence=min(1.0, math.log1p(signal_count) / 6.0),
        )


class ScalabilityAnalyzer(BaseAnalyzer):
    category = "Scalability"

    def analyze(self, snapshot: Snapshot) -> CategoryResult:
        findings: List[Finding] = []
        async_files = [f for f in snapshot.files if "async def" in f.content]
        queue_signals = [f.rel_path for f in snapshot.files if re.search(r"(celery|rq|kafka|sqs|pubsub|worker)", f.content, flags=re.IGNORECASE)]

        if len(async_files) < max(1, len([f for f in snapshot.files if f.ext == ".py"]) // 10):
            findings.append(Finding(
                id=str(uuid.uuid4()),
                category=self.category,
                finding_type="problem",
                severity="low",
                title="Limited async scalability patterns",
                details="Few asynchronous service handlers were detected for backend workloads.",
                recommendation="Adopt async I/O for latency-critical endpoints and external API calls.",
                affected_files=[f.rel_path for f in snapshot.files if f.ext == ".py"][:10],
                expected_score_gain=2,
            ))

        if queue_signals:
            findings.append(Finding(
                id=str(uuid.uuid4()),
                category=self.category,
                finding_type="positive",
                severity="low",
                title="Background processing signals",
                details=f"Detected queue/worker patterns in {len(queue_signals)} files.",
                evidence={"queue_files": queue_signals[:12]},
            ))

        signal_count = len(snapshot.files) + len(async_files) + len(queue_signals)
        score = self._score_from_findings(findings, signal_count)
        explanation = "Scalability score measures async readiness and workload decoupling patterns."
        return CategoryResult(
            category=self.category,
            score=score,
            explanation=explanation,
            findings=findings,
            affected_files=sorted({p for f in findings for p in f.affected_files})[:30],
            affected_modules=sorted({m for f in findings for m in f.affected_modules})[:20],
            confidence=min(1.0, math.log1p(signal_count) / 6.0),
        )


class ObservabilityAnalyzer(BaseAnalyzer):
    category = "Observability"

    def analyze(self, snapshot: Snapshot) -> CategoryResult:
        findings: List[Finding] = []

        log_files = [f for f in snapshot.files if re.search(r"logger\.|logging\.", f.content)]
        metrics_files = [f for f in snapshot.files if re.search(r"prometheus|metrics|opentelemetry|trace", f.content, flags=re.IGNORECASE)]
        health_endpoints = [f for f in snapshot.files if "/health" in f.content and "@app.get" in f.content]

        if not log_files:
            findings.append(Finding(
                id=str(uuid.uuid4()),
                category=self.category,
                finding_type="problem",
                severity="high",
                title="Insufficient logging coverage",
                details="No structured logging calls were detected in scanned source files.",
                recommendation="Add structured logs with request IDs and error context across service boundaries.",
                expected_score_gain=6,
            ))

        if not metrics_files:
            findings.append(Finding(
                id=str(uuid.uuid4()),
                category=self.category,
                finding_type="problem",
                severity="medium",
                title="Metrics/tracing gap",
                details="No metrics or tracing instrumentation patterns were detected.",
                recommendation="Integrate metrics and distributed tracing for production diagnostics.",
                expected_score_gain=4,
            ))

        if health_endpoints:
            findings.append(Finding(
                id=str(uuid.uuid4()),
                category=self.category,
                finding_type="positive",
                severity="low",
                title="Health check endpoints detected",
                details=f"Detected {len(health_endpoints)} health-check endpoint definitions.",
                evidence={"files": [f.rel_path for f in health_endpoints[:6]]},
            ))

        signal_count = len(snapshot.files) + len(log_files) + len(metrics_files)
        score = self._score_from_findings(findings, signal_count)
        explanation = "Observability score evaluates logging, health-check, and telemetry instrumentation coverage."
        return CategoryResult(
            category=self.category,
            score=score,
            explanation=explanation,
            findings=findings,
            affected_files=sorted({p for f in findings for p in f.affected_files})[:30],
            affected_modules=sorted({m for f in findings for m in f.affected_modules})[:20],
            confidence=min(1.0, math.log1p(signal_count) / 6.0),
        )


class DeveloperExperienceAnalyzer(BaseAnalyzer):
    category = "Developer Experience"

    def analyze(self, snapshot: Snapshot) -> CategoryResult:
        findings: List[Finding] = []
        root_files = {os.path.basename(f.rel_path).lower(): f for f in snapshot.files if "/" not in f.rel_path}

        onboarding = [name for name in root_files.keys() if any(k in name for k in ["readme", "quick_start", "installation", "contributing"])]
        run_scripts = [name for name in root_files.keys() if name.startswith("run") or name.startswith("start")]

        if not onboarding:
            findings.append(Finding(
                id=str(uuid.uuid4()),
                category=self.category,
                finding_type="problem",
                severity="high",
                title="Onboarding docs missing",
                details="No root-level onboarding documentation was detected.",
                recommendation="Provide README + quick start with environment setup and troubleshooting.",
                expected_score_gain=6,
            ))
        else:
            findings.append(Finding(
                id=str(uuid.uuid4()),
                category=self.category,
                finding_type="positive",
                severity="low",
                title="Onboarding artifacts detected",
                details=f"Detected onboarding docs: {', '.join(sorted(onboarding)[:6])}.",
            ))

        if len(run_scripts) < 1:
            findings.append(Finding(
                id=str(uuid.uuid4()),
                category=self.category,
                finding_type="problem",
                severity="medium",
                title="Developer run scripts are sparse",
                details="No obvious run/start scripts were detected at the repository root.",
                recommendation="Add reproducible local run scripts for backend/frontend/test workflows.",
                expected_score_gain=3,
            ))

        signal_count = len(snapshot.files) + len(onboarding) + len(run_scripts)
        score = self._score_from_findings(findings, signal_count)
        explanation = "Developer experience score reflects onboarding quality and local workflow ergonomics."
        return CategoryResult(
            category=self.category,
            score=score,
            explanation=explanation,
            findings=findings,
            affected_files=sorted({p for f in findings for p in f.affected_files})[:30],
            affected_modules=sorted({m for f in findings for m in f.affected_modules})[:20],
            confidence=min(1.0, math.log1p(signal_count) / 6.0),
        )


class RecommendationEngine:
    def generate(self, category_results: Sequence[CategoryResult]) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        for result in category_results:
            for finding in result.findings:
                if finding.finding_type != "problem" or not finding.recommendation:
                    continue
                affected_scale = max(1, len(finding.affected_files) + len(finding.affected_modules))
                impact_score = round((SEVERITY_MULTIPLIER.get(finding.severity, 1.0) * (1 + math.log1p(affected_scale))) * max(1.0, finding.expected_score_gain / 2), 2)
                confidence = round(min(0.99, max(0.25, result.confidence * (0.7 + min(0.3, len(finding.affected_files) / 20.0)))), 2)
                items.append({
                    "category": result.category,
                    "title": finding.title,
                    "description": finding.recommendation,
                    "severity": finding.severity,
                    "impact": self._impact_label(impact_score),
                    "expected_score_gain": max(1, finding.expected_score_gain),
                    "impact_score": impact_score,
                    "confidence": confidence,
                    "confidence_basis": "repository_evidence",
                    "explanation": finding.details,
                    "evidence": finding.evidence or {},
                    "affected_files": finding.affected_files[:12],
                    "affected_symbols": self._affected_symbols(finding.evidence),
                    "suggested_solution": finding.recommendation,
                    "dependencies": [],
                    "risk": self._risk_from_severity(finding.severity),
                    "current_status": "OPEN",
                    "dismissed_reason": None,
                    "action_items": self._action_items_for_finding(finding),
                    "actions": self._actions_for_finding(result.category, finding),
                    "estimated_effort": self._estimate_effort(finding),
                })

        items.sort(key=lambda x: (x["impact_score"], x["expected_score_gain"]), reverse=True)
        ranked = []
        for i, item in enumerate(items[:10], start=1):
            ranked.append({"rank": i, **item})
        return ranked

    def _impact_label(self, impact_score: float) -> str:
        if impact_score >= 12:
            return "high"
        if impact_score >= 6:
            return "medium"
        return "low"

    def _risk_from_severity(self, severity: str) -> str:
        if severity in {"critical", "high"}:
            return "high"
        if severity == "medium":
            return "medium"
        return "low"

    def _affected_symbols(self, evidence: Dict[str, Any]) -> List[str]:
        symbols = evidence.get("symbols") if isinstance(evidence, dict) else None
        if isinstance(symbols, list):
            return [str(item) for item in symbols[:12] if str(item).strip()]
        return []

    def _estimate_effort(self, finding: Finding) -> str:
        size = len(finding.affected_files)
        if finding.severity == "critical" or size > 12:
            return "1-2 days"
        if finding.severity == "high" or size > 6:
            return "4-8 hours"
        if finding.severity == "medium":
            return "2-4 hours"
        return "1-2 hours"

    def _action_items_for_finding(self, finding: Finding) -> List[str]:
        base = [finding.recommendation or "Address finding."]
        if finding.affected_files:
            base.append(f"Start with: {', '.join(finding.affected_files[:3])}")
        if finding.affected_modules:
            base.append(f"Coordinate changes across modules: {', '.join(sorted(set(finding.affected_modules))[:3])}")
        return base[:3]

    def _actions_for_finding(self, category: str, finding: Finding) -> List[str]:
        actions = [
            "explain",
            "open_evidence",
            "review",
            "generate_fix",
            "generate_tests",
            "show_diff",
            "run_tests",
            "reanalyze",
            "ignore",
        ]
        if (category or "").lower() == "dependencies":
            return [
                "explain",
                "open_evidence",
                "dependency_risk",
                "security",
                "upgrade_impact",
                "license",
                "generate_upgrade_plan",
                "review",
                "ignore",
            ]
        if any(path.lower().endswith(("test.py", "_test.py", ".spec.ts", ".test.ts", ".test.tsx")) for path in finding.affected_files):
            return [
                "explain",
                "coverage",
                "missing_cases",
                "generate_tests",
                "run_tests",
                "review",
                "open_ai_chat",
            ]
        return actions


class TrendAnalyzer:
    def apply_category_trends(
        self,
        current: Sequence[CategoryResult],
        previous_scores: Optional[Dict[str, int]],
    ) -> Tuple[List[CategoryResult], int, List[str], List[str]]:
        improved: List[str] = []
        declining: List[str] = []
        total_delta = 0

        if not previous_scores:
            return list(current), 0, improved, declining

        updated = []
        for result in current:
            previous = previous_scores.get(result.category)
            trend = result.score - previous if previous is not None else 0
            total_delta += trend
            result.trend = trend
            if trend > 0:
                improved.append(result.category)
            elif trend < 0:
                declining.append(result.category)
            updated.append(result)
        return updated, int(round(total_delta / max(1, len(current)))), improved, declining


class RepositoryHealthEngine:
    def __init__(self, repos_dir: Optional[str] = None) -> None:
        self._repos_dir = repos_dir or _resolve_repos_dir()
        self.analyzers: List[BaseAnalyzer] = [
            ArchitectureAnalyzer(),
            SecurityAnalyzer(),
            TestingAnalyzer(),
            DocumentationAnalyzer(),
            PerformanceAnalyzer(),
            MaintainabilityAnalyzer(),
            TechnicalDebtAnalyzer(),
            DependencyAnalyzer(),
            CodeQualityAnalyzer(),
            ScalabilityAnalyzer(),
            ObservabilityAnalyzer(),
            DeveloperExperienceAnalyzer(),
        ]
        self.recommendation_engine = RecommendationEngine()
        self.trend_analyzer = TrendAnalyzer()

    def run(
        self,
        repo: Dict[str, Any],
        previous_scores: Optional[Dict[str, int]] = None,
        previous_findings: Optional[Iterable[str]] = None,
        previous_overall_score: Optional[int] = None,
    ) -> Dict[str, Any]:
        snapshot = self._build_snapshot(repo)
        category_results = [analyzer.analyze(snapshot) for analyzer in self.analyzers]
        category_results, trend_delta, improved, declining = self.trend_analyzer.apply_category_trends(
            category_results,
            previous_scores,
        )
        overall_score = self._aggregate_score(category_results)
        if previous_overall_score is not None:
            trend_delta = overall_score - int(previous_overall_score)
        elif previous_scores:
            previous_overall = int(round(sum(previous_scores.values()) / max(1, len(previous_scores))))
            trend_delta = overall_score - previous_overall
        grade = self._grade_for_score(overall_score)
        status = self._status_for_score(overall_score)
        recommendations = self.recommendation_engine.generate(category_results)

        findings = [finding for res in category_results for finding in res.findings]
        finding_titles = {f.title for f in findings if f.finding_type == "problem"}
        previous_finding_titles = set(previous_findings or [])

        top_level = {
            "repository_health": overall_score,
            "grade": grade,
            "status": status,
            "trend": trend_delta,
            "last_analysis": datetime.now(timezone.utc),
            "repository_size": self._classify_size(snapshot),
            "language_detection": [k for k, _ in snapshot.language_counts.most_common(5)],
            "framework_detection": [k for k, _ in snapshot.framework_signals.most_common(5)],
        }

        report = self._build_report(overall_score, category_results, findings, recommendations)

        analyzed_at = datetime.now(timezone.utc)
        branch = str(repo.get("active_branch") or repo.get("default_branch") or "unknown")
        commit_sha = str(repo.get("active_commit_sha") or "unknown")

        return {
            "top_level": top_level,
            "categories": [
                self._serialize_category(
                    c,
                    analysis_timestamp=analyzed_at,
                    branch=branch,
                    commit_sha=commit_sha,
                )
                for c in category_results
            ],
            "findings": [self._serialize_finding(f) for f in findings],
            "recommendations": recommendations,
            "executive_summary": report["executive_summary"],
            "strengths": report["strengths"],
            "weaknesses": report["weaknesses"],
            "critical_risks": report["critical_risks"],
            "architecture_risks": report["architecture_risks"],
            "security_risks": report["security_risks"],
            "performance_risks": report["performance_risks"],
            "recommended_sprint": report["recommended_sprint"],
            "improved_categories": improved,
            "declining_categories": declining,
            "new_risks": sorted(finding_titles - previous_finding_titles)[:20],
            "resolved_risks": sorted(previous_finding_titles - finding_titles)[:20],
            "benchmark": self._benchmark(snapshot, category_results, overall_score),
        }

    def _build_snapshot(self, repo: Dict[str, Any]) -> Snapshot:
        index_name = repo.get("index_name") or repo.get("name") or "repo"
        repo_path = os.path.join(self._repos_dir, index_name)
        files: List[RepoFile] = []

        language_counts: Counter = Counter()
        module_counts: Counter = Counter()
        framework_signals: Counter = Counter()

        for root, dirs, filenames in os.walk(repo_path):
            dirs[:] = [d for d in dirs if d not in {".git", "node_modules", "venv", "__pycache__", "dist", "build", ".next"}]
            for filename in filenames:
                full_path = os.path.join(root, filename)
                rel_path = os.path.relpath(full_path, repo_path).replace("\\", "/")
                ext = os.path.splitext(filename)[1].lower()
                if ext in {".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".zip", ".db", ".sqlite", ".mp4", ".mov"}:
                    continue
                try:
                    if os.path.getsize(full_path) > 300_000:
                        continue
                    with open(full_path, "r", encoding="utf-8", errors="ignore") as fh:
                        content = fh.read()
                except Exception:
                    continue

                lines = content.count("\n") + (1 if content else 0)
                files.append(RepoFile(path=full_path, rel_path=rel_path, ext=ext, content=content, lines=lines))

                language = self._detect_language_from_ext(ext)
                if language:
                    language_counts[language] += 1
                top_module = rel_path.split("/")[0] if "/" in rel_path else "root"
                module_counts[top_module] += 1
                for fw in self._detect_framework_signals(content, filename):
                    framework_signals[fw] += 1

        return Snapshot(
            repo_id=repo.get("id", ""),
            repo_name=repo.get("name", "repo"),
            repo_path=repo_path,
            files=files,
            language_counts=language_counts,
            framework_signals=framework_signals,
            module_counts=module_counts,
        )

    def _aggregate_score(self, categories: Sequence[CategoryResult]) -> int:
        if not categories:
            return 0

        weighted_sum = 0.0
        weight_total = 0.0
        for c in categories:
            # Dynamic category weighting based on confidence and evidence volume.
            evidence_volume = len(c.findings) + len(c.affected_files) + len(c.affected_modules)
            weight = max(0.5, c.confidence + math.log1p(evidence_volume))
            weighted_sum += c.score * weight
            weight_total += weight

        return int(round(weighted_sum / max(1e-6, weight_total)))

    def _grade_for_score(self, score: int) -> str:
        if score >= 90:
            return "A"
        if score >= 80:
            return "B"
        if score >= 70:
            return "C"
        if score >= 60:
            return "D"
        return "F"

    def _status_for_score(self, score: int) -> str:
        if score >= 90:
            return "Excellent"
        if score >= 80:
            return "Strong"
        if score >= 70:
            return "Fair"
        if score >= 60:
            return "Needs Attention"
        return "At Risk"

    def _classify_size(self, snapshot: Snapshot) -> str:
        total_files = len(snapshot.files)
        if total_files >= 450:
            return "Large"
        if total_files >= 140:
            return "Medium"
        return "Small"

    def _benchmark(self, snapshot: Snapshot, categories: Sequence[CategoryResult], overall_score: int) -> Dict[str, Any]:
        category_values = [c.score for c in categories]
        baseline = int(round(sum(category_values) / max(1, len(category_values))))
        language_modifier = int(round(min(6.0, math.log1p(sum(snapshot.language_counts.values())))))
        size_modifier = {"Small": 2, "Medium": 0, "Large": -2}[self._classify_size(snapshot)]
        best_practice_score = max(0, min(100, baseline + language_modifier + size_modifier))
        delta = overall_score - best_practice_score
        return {
            "best_practice_score": best_practice_score,
            "delta_vs_best_practice": delta,
            "repository_size": self._classify_size(snapshot),
            "language_ecosystem": [k for k, _ in snapshot.language_counts.most_common(3)],
            "framework_conventions": [k for k, _ in snapshot.framework_signals.most_common(3)],
        }

    def _build_report(
        self,
        overall_score: int,
        categories: Sequence[CategoryResult],
        findings: Sequence[Finding],
        recommendations: Sequence[Dict[str, Any]],
    ) -> Dict[str, Any]:
        top_categories = sorted(categories, key=lambda c: c.score, reverse=True)[:3]
        weak_candidates = [c for c in categories if c.score < 100]
        weak_categories = sorted(weak_candidates, key=lambda c: c.score)[:3]

        critical = [f.title for f in findings if f.finding_type == "problem" and f.severity in {"critical", "high"}][:8]
        arch_risks = [f.title for f in findings if f.category == "Architecture" and f.finding_type == "problem"][:5]
        sec_risks = [f.title for f in findings if f.category == "Security" and f.finding_type == "problem"][:5]
        perf_risks = [f.title for f in findings if f.category == "Performance" and f.finding_type == "problem"][:5]

        sprint_items = [f"{rec['category']}: {rec['title']}" for rec in recommendations[:6]]

        return {
            "executive_summary": (
                f"Repository health is {overall_score}/100. "
                f"Strongest areas: {', '.join([c.category for c in top_categories])}. "
                f"Priority improvements: {', '.join([c.category for c in weak_categories])}."
            ),
            "strengths": [f"{c.category} ({c.score})" for c in top_categories],
            "weaknesses": [f"{c.category} ({c.score})" for c in weak_categories],
            "critical_risks": critical,
            "architecture_risks": arch_risks,
            "security_risks": sec_risks,
            "performance_risks": perf_risks,
            "recommended_sprint": sprint_items,
        }

    def _serialize_category(
        self,
        category: CategoryResult,
        *,
        analysis_timestamp: datetime,
        branch: str,
        commit_sha: str,
    ) -> Dict[str, Any]:
        problems = [f.title for f in category.findings if f.finding_type == "problem"]
        positives = [f.title for f in category.findings if f.finding_type == "positive"]
        recs = [f.recommendation for f in category.findings if f.recommendation][:5]
        severity_breakdown = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        for finding in category.findings:
            if finding.finding_type != "problem":
                continue
            sev = str(finding.severity or "low").lower()
            if sev in severity_breakdown:
                severity_breakdown[sev] += 1
        files_analyzed = max(len(category.affected_files), len(category.findings))
        return {
            "category": category.category,
            "score": category.score,
            "grade": self._grade_for_score(category.score),
            "trend": category.trend,
            "explanation": category.explanation,
            "detected_problems": problems,
            "positive_findings": positives,
            "recommendations": recs,
            "affected_files": category.affected_files,
            "affected_modules": category.affected_modules,
            "confidence": round(float(category.confidence), 2),
            "files_analyzed": files_analyzed,
            "checks_performed": self._checks_for_category(category.category),
            "findings_count": len(category.findings),
            "severity_breakdown": severity_breakdown,
            "analysis_timestamp": analysis_timestamp,
            "branch": branch,
            "commit_sha": commit_sha,
        }

    def _checks_for_category(self, category: str) -> List[str]:
        checks = {
            "Architecture": ["dependency_graph_scan", "cycle_detection", "module_boundary_analysis"],
            "Security": ["auth_guard_scan", "secret_pattern_scan", "sensitive_log_scan"],
            "Testing": ["test_coverage_proxy", "test_mapping_scan", "negative_test_signal_scan"],
            "Documentation": ["readme_presence", "doc_coverage_scan"],
            "Performance": ["async_blocking_scan", "caching_signal_scan"],
            "Maintainability": ["function_complexity_scan", "duplication_signal_scan"],
            "Technical Debt": ["todo_fixme_scan", "legacy_marker_scan"],
            "Dependencies": ["manifest_scan", "version_pin_scan"],
            "Code Quality": ["lint_signal_scan", "style_signal_scan"],
            "Scalability": ["concurrency_signal_scan", "queue_usage_scan"],
            "Observability": ["logging_signal_scan", "tracing_signal_scan"],
            "Developer Experience": ["onboarding_signal_scan", "tooling_script_scan"],
        }
        return checks.get(category, ["heuristic_repository_scan"])

    def _serialize_finding(self, finding: Finding) -> Dict[str, Any]:
        return {
            "id": finding.id,
            "category": finding.category,
            "finding_type": finding.finding_type,
            "severity": finding.severity,
            "title": finding.title,
            "details": finding.details,
            "evidence": finding.evidence,
            "recommendation": finding.recommendation,
            "affected_files": finding.affected_files,
            "affected_modules": finding.affected_modules,
            "expected_score_gain": finding.expected_score_gain,
        }

    def _detect_language_from_ext(self, ext: str) -> Optional[str]:
        mapping = {
            ".py": "Python",
            ".ts": "TypeScript",
            ".tsx": "TypeScript",
            ".js": "JavaScript",
            ".jsx": "JavaScript",
            ".go": "Go",
            ".java": "Java",
            ".rb": "Ruby",
            ".rs": "Rust",
            ".php": "PHP",
        }
        return mapping.get(ext)

    def _detect_framework_signals(self, content: str, filename: str) -> List[str]:
        text = f"{filename}\n{content}".lower()
        frameworks = []
        signal_map = {
            "fastapi": ["fastapi", "apirouter("],
            "django": ["django", "urlpatterns"],
            "flask": ["flask", "@app.route"],
            "react": ["react", "useeffect", "usestate"],
            "next.js": ["next.config", "next/navigation"],
            "spring": ["@springbootapplication", "org.springframework"],
            "nestjs": ["@nestjs", "@controller("],
        }
        for framework, signals in signal_map.items():
            if any(s in text for s in signals):
                frameworks.append(framework)
        return frameworks
