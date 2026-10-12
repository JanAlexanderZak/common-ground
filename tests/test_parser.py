from pathlib import Path

from common_ground import Edge, parse_dir, parse_string


def test_parse_minimal_l0_statement():
    md = """# Test topic

## L0 — Facts

### f1: The sky is blue.
"""
    graph = parse_string(md)

    assert len(graph.statements) == 1
    statement = graph.statements[0]
    assert statement.id == "f1"
    assert statement.layer == 0
    assert statement.text == "The sky is blue."


def test_parse_multiple_layers_and_statements():
    md = """# Schuldenbremse

## L0 — Empirical facts

### f1: Article 109 GG limits structural deficit to 0.35% GDP.

### f2: Germany's debt-to-GDP was 62.4% end-2023.

## L2 — Causal mechanisms

### c1: Higher public debt raises long-term interest rates.

## L4 — Policy positions

### p1: Reform Schuldenbremse to allow 1.0% deficit for investment.
"""
    graph = parse_string(md)

    assert [s.id for s in graph.statements] == ["f1", "f2", "c1", "p1"]
    by_id = {s.id: s for s in graph.statements}
    assert by_id["f1"].layer == 0
    assert by_id["f2"].layer == 0
    assert by_id["c1"].layer == 2
    assert by_id["p1"].layer == 4


def test_parse_edges_under_statement():
    md = """# Test

## L4 — Policies

### p1: Reform Schuldenbremse to allow investment deficit.

- **supports:** c1, v3
- **attacked-by:** p2
"""
    graph = parse_string(md)

    assert len(graph.statements) == 1
    assert sorted(graph.edges, key=lambda e: (e.relation, e.target)) == [
        Edge(source="p1", target="p2", relation="attacked-by"),
        Edge(source="p1", target="c1", relation="supports"),
        Edge(source="p1", target="v3", relation="supports"),
    ]


def test_parse_edges_do_not_attach_after_intervening_paragraph():
    md = """# Test

## L4 — Policies

### p1: Reform Schuldenbremse to allow investment deficit.

This ordinary prose explains the statement but is not an attachment block.

- **supports:** c1
"""
    graph = parse_string(md)

    assert len(graph.statements) == 1
    assert graph.edges == []


def test_parse_statement_with_citation():
    md = """# Test

## L0 — Facts

### f1: Article 109 GG limits structural deficit to 0.35% GDP.

> **Quelle:** [Bundestag — GG Art. 109](https://www.bundestag.de/grundgesetz)
> - retrieved: 2026-04-01
> - source-type: legal-text
> - jurisdiction: DE
"""
    graph = parse_string(md)

    assert len(graph.statements) == 1
    statement = graph.statements[0]
    assert len(statement.sources) == 1

    source = statement.sources[0]
    assert source.url == "https://www.bundestag.de/grundgesetz"
    assert source.label == "Bundestag — GG Art. 109"
    assert source.retrieved == "2026-04-01"
    assert source.source_type == "legal-text"
    assert source.jurisdiction == "DE"


def test_parse_metadata_does_not_attach_after_intervening_paragraph():
    md = """# Test

## L0 — Facts

### f1: Article 109 GG limits structural deficit to 0.35% GDP.

This ordinary prose explains context before a later quote.

> **Quelle:** [Bundestag — GG Art. 109](https://www.bundestag.de/grundgesetz)
> **Endorsed by:** @spd-2025
> **Disputed by:** @fdp-2025
> **Data:** [`debt-to-gdp.csv`](../data/debt-to-gdp.csv)
"""
    graph = parse_string(md)

    statement = graph.statements[0]
    assert statement.sources == []
    assert statement.endorsed_by == []
    assert statement.disputed_by == []
    assert statement.data_refs == []


def test_parse_actor_references():
    md = """# Test

## L4 — Policies

### p1: Reform Schuldenbremse to allow investment deficit.

> **Endorsed by:** @spd-2025, @grüne-2025
> **Disputed by:** @cdu-2025, @fdp-2025
"""
    graph = parse_string(md)

    statement = graph.statements[0]
    assert statement.endorsed_by == ["spd-2025", "grüne-2025"]
    assert statement.disputed_by == ["cdu-2025", "fdp-2025"]


def test_parse_data_reference():
    md = """# Test

## L0 — Facts

### f2: Schuldenstand-zu-BIP-Verhältnis Ende 2023: 62,4%

> **Data:** [`debt-to-gdp.csv`](../data/debt-to-gdp.csv) — column `debt_to_gdp_pct`, 2010–2024
"""
    graph = parse_string(md)

    statement = graph.statements[0]
    assert len(statement.data_refs) == 1

    ref = statement.data_refs[0]
    assert ref.path == "../data/debt-to-gdp.csv"
    assert ref.label == "debt-to-gdp.csv"
    assert ref.description is not None
    assert "column" in ref.description
    assert "debt_to_gdp_pct" in ref.description


def test_parse_dir_merges_statement_files(tmp_path: Path):
    statements = tmp_path / "statements"
    statements.mkdir()
    (statements / "01-facts.md").write_text(
        "# Facts\n\n## L0 — Facts\n\n### f1: Sky is blue.\n",
        encoding="utf-8",
    )
    (statements / "02-mechanisms.md").write_text(
        "# Mechanisms\n\n## L2 — Causal\n\n### c1: Things cause other things.\n",
        encoding="utf-8",
    )

    graph = parse_dir(tmp_path)

    assert {s.id for s in graph.statements} == {"f1", "c1"}
    by_id = {s.id: s for s in graph.statements}
    assert by_id["f1"].layer == 0
    assert by_id["c1"].layer == 2


def test_parse_dir_returns_empty_for_missing_statements(tmp_path: Path):
    graph = parse_dir(tmp_path)
    assert graph.statements == []
    assert graph.edges == []


def test_parse_dir_carries_edges_across_files(tmp_path: Path):
    statements = tmp_path / "statements"
    statements.mkdir()
    (statements / "facts.md").write_text(
        "## L0 — Facts\n\n### f1: Premise.\n",
        encoding="utf-8",
    )
    (statements / "policies.md").write_text(
        "## L4 — Policies\n\n### p1: Policy.\n\n- **supports:** f1\n",
        encoding="utf-8",
    )

    graph = parse_dir(tmp_path)

    assert graph.edges == [Edge(source="p1", target="f1", relation="supports")]


def test_parse_dir_reads_topic_metadata(tmp_path: Path):
    (tmp_path / "topic.md").write_text(
        """---
topic: example-topic
language: en
version: "0.1"
contributors:
  - Jane Doe
  - John Roe
license: AGPL-3.0
actors-registry: ../../actors
---

# Example topic title

Description body.
""",
        encoding="utf-8",
    )

    graph = parse_dir(tmp_path)

    md = graph.metadata
    assert md.topic == "example-topic"
    assert md.title == "Example topic title"
    assert md.language == "en"
    assert md.version == "0.1"
    assert md.contributors == ["Jane Doe", "John Roe"]
    assert md.license == "AGPL-3.0"
    assert md.actors_registry == "../../actors"


def test_parse_dir_without_topic_md_yields_empty_metadata(tmp_path: Path):
    graph = parse_dir(tmp_path)
    assert graph.metadata.topic is None
    assert graph.metadata.title is None
    assert graph.metadata.contributors == []


def test_parse_dir_topic_md_without_frontmatter_extracts_h1_title(tmp_path: Path):
    (tmp_path / "topic.md").write_text(
        "# Just a title\n\nNo frontmatter here.\n",
        encoding="utf-8",
    )

    graph = parse_dir(tmp_path)

    assert graph.metadata.title == "Just a title"
    assert graph.metadata.topic is None
    assert graph.metadata.language is None
