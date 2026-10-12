import json
import re
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB_DIR = ROOT / "src" / "web"
INDEX_HTML = WEB_DIR / "index.html"
MAIN_JS = WEB_DIR / "main.js"
TOPIC_JSON = WEB_DIR / "topic.json"
SCHULDENBREMSE_TOPIC = ROOT / "src" / "topics" / "schuldenbremse"

IMPORT_MAP_KEYS = {
    "react",
    "react-dom/client",
    "@xyflow/react",
    "htm/react",
}


class RendererHtmlParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.has_root = False
        self.module_scripts = []
        self.import_map_chunks = []
        self.stylesheets = []
        self._in_import_map = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "div" and attrs.get("id") == "root":
            self.has_root = True
        if tag == "script" and attrs.get("type") == "module":
            self.module_scripts.append(attrs.get("src"))
        if tag == "script" and attrs.get("type") == "importmap":
            self._in_import_map = True
        if tag == "link" and attrs.get("rel") == "stylesheet":
            self.stylesheets.append(attrs.get("href"))

    def handle_data(self, data):
        if self._in_import_map:
            self.import_map_chunks.append(data)

    def handle_endtag(self, tag):
        if tag == "script" and self._in_import_map:
            self._in_import_map = False


def run_checked(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )


def generate_schuldenbremse_topic_json() -> dict:
    previous_topic_json = TOPIC_JSON.read_bytes() if TOPIC_JSON.exists() else None
    try:
        run_checked(
            [
                sys.executable,
                str(ROOT / "build.py"),
                str(SCHULDENBREMSE_TOPIC),
                str(TOPIC_JSON),
            ],
        )
        return json.loads(TOPIC_JSON.read_text(encoding="utf-8"))
    finally:
        if previous_topic_json is None:
            TOPIC_JSON.unlink(missing_ok=True)
        else:
            TOPIC_JSON.write_bytes(previous_topic_json)


def test_web_renderer_smoke_contract():
    graph = generate_schuldenbremse_topic_json()
    statements = {statement["id"]: statement for statement in graph["statements"]}

    assert graph["metadata"]["topic"] == "schuldenbremse-bund"
    assert len(statements) >= 1
    assert len(graph["edges"]) >= 1
    assert graph["derived"]["edge_pairs"]
    assert {statement["layer"] for statement in statements.values()} == {0, 1, 2, 3, 4}

    investment_statement = statements["p-investitionsausnahme"]
    assert investment_statement["layer"] == 4
    assert "Schuldenbremse" in investment_statement["text"]
    assert "diw-berlin" in investment_statement["endorsed_by"]

    html = INDEX_HTML.read_text(encoding="utf-8")
    parser = RendererHtmlParser()
    parser.feed(html)

    assert parser.has_root
    main_script = next(
        (src for src in parser.module_scripts if src.startswith("./main.js")),
        None,
    )
    assert main_script is not None
    assert main_script != "./main.js"
    assert "v=legend-fix" in main_script
    assert any("@xyflow/react@12/dist/style.css" in href for href in parser.stylesheets)

    import_map = json.loads("".join(parser.import_map_chunks))
    imports = import_map["imports"]
    assert set(imports) >= IMPORT_MAP_KEYS
    assert all(imports[key].startswith("https://esm.sh/") for key in IMPORT_MAP_KEYS)

    main_js = MAIN_JS.read_text(encoding="utf-8")
    imported_modules = set(re.findall(r'from\s+["\']([^"\']+)["\']', main_js))
    bare_imports = {module for module in imported_modules if not module.startswith(".")}
    relative_imports = {module for module in imported_modules if module.startswith(".")}
    assert bare_imports <= set(imports)
    for module in relative_imports:
        imported_path = (WEB_DIR / module).resolve()
        assert imported_path.is_relative_to(WEB_DIR.resolve())
        assert imported_path.is_file()

    assert 'fetch("./topic.json")' in main_js
    assert 'createRoot(document.getElementById("root"))' in main_js
    assert "root.render" in main_js
    assert "ReactFlow" in main_js
    assert "StatementNode" in main_js
    assert "PolicyRail" in main_js
    assert "Policy positions" in main_js
    assert "Facts & mechanisms" in main_js
    assert "onNodeClick" in main_js
    assert "DetailsPanel" in main_js
    assert "Trace dependencies" in main_js
    assert "Trace down" not in main_js
    assert "My disagreements" not in main_js
    assert "<${RelationLine}" not in main_js
    assert "<-></span>" not in main_js
    assert "@${id}" in main_js

    run_checked(["node", "--check", str(MAIN_JS)])


def test_dependency_trace_excludes_policy_attack_cycles():
    script = """
import {
  dependencyTraceIds,
  policyStatements,
  visibleStatementsForView,
} from "./src/web/graph-utils.js";

const statements = [
  { id: "p1", layer: 4, text: "Policy one" },
  { id: "p2", layer: 4, text: "Policy two" },
  { id: "m1", layer: 2, text: "Mechanism one" },
  { id: "f1", layer: 0, text: "Fact one" },
  { id: "m2", layer: 2, text: "Unrelated mechanism" },
];

const edges = [
  { source: "p1", target: "m1", relation: "supports" },
  { source: "m1", target: "f1", relation: "evidence" },
  { source: "p1", target: "p2", relation: "attacks" },
  { source: "p2", target: "m2", relation: "supports" },
];

const trace = [...dependencyTraceIds("p1", statements, edges)].sort();
const policies = policyStatements(statements).map((s) => s.id);
const facts = visibleStatementsForView(statements, "facts").map((s) => s.id);

console.log(JSON.stringify({ trace, policies, facts }));
"""
    result = run_checked(["node", "--input-type=module", "-e", script])
    observed = json.loads(result.stdout)

    assert observed == {
        "facts": ["m1", "f1", "m2"],
        "policies": ["p1", "p2"],
        "trace": ["f1", "m1", "p1"],
    }
