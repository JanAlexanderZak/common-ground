from pathlib import Path

from common_ground import parse_dir

TOPICS_DIR = Path(__file__).parent.parent / "src" / "topics"


def test_schuldenbremse_parses_cleanly():
    graph = parse_dir(TOPICS_DIR / "schuldenbremse")

    assert graph.metadata.topic == "schuldenbremse-bund"
    assert graph.metadata.language == "de"

    assert len(graph.statements) >= 30
    assert len(graph.edges) >= 40

    layers = {s.layer for s in graph.statements}
    assert layers == {0, 1, 2, 3, 4}, f"missing layers: {layers}"


def test_schuldenbremse_has_no_unresolved_cross_file_references():
    graph = parse_dir(TOPICS_DIR / "schuldenbremse")
    ids = {s.id for s in graph.statements}
    edge_targets = {e.target for e in graph.edges}
    edge_sources = {e.source for e in graph.edges}

    unresolved_targets = edge_targets - ids
    unresolved_sources = edge_sources - ids

    assert not unresolved_targets, f"edge targets not in graph: {unresolved_targets}"
    assert not unresolved_sources, f"edge sources not in graph: {unresolved_sources}"


def test_schuldenbremse_l0_l1_statements_have_sources():
    graph = parse_dir(TOPICS_DIR / "schuldenbremse")
    fact_statements = [s for s in graph.statements if s.layer in (0, 1)]
    unsourced = [s.id for s in fact_statements if not s.sources]
    assert not unsourced, f"L0/L1 statements without sources: {unsourced}"


def test_schuldenbremse_has_data_refs():
    graph = parse_dir(TOPICS_DIR / "schuldenbremse")
    statements_with_data = [s for s in graph.statements if s.data_refs]
    assert len(statements_with_data) >= 3, (
        "Expected ≥3 statements with data refs (BIP / Schuldenquote / inflation)"
    )
