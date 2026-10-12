import json
from pathlib import Path

from common_ground import (
    DataRef,
    Edge,
    Source,
    Statement,
    TypedGraph,
    parse_dir,
    validate_graph,
)
from common_ground.validator import _ALLOWED_SOURCE_TYPES

ROOT = Path(__file__).parent.parent


def _schema_source_types() -> set[str]:
    schema = json.loads(
        (ROOT / "src" / "format" / "schema.json").read_text(encoding="utf-8")
    )
    source_type_enum = schema["$defs"]["Source"]["properties"]["source_type"]["enum"]
    return {source_type for source_type in source_type_enum if source_type is not None}


def test_empty_graph_validates_clean():
    assert validate_graph(TypedGraph()) == []


def test_distinct_statement_ids_validate_cleanly():
    graph = TypedGraph(
        statements=[
            Statement(id="f1", layer=0, text="Fact."),
            Statement(id="f2", layer=0, text="Another fact."),
        ],
    )

    assert validate_graph(graph) == []


def test_flags_invalid_source_type():
    graph = TypedGraph(
        statements=[
            Statement(
                id="f1",
                layer=0,
                text="Fact.",
                sources=[Source(source_type="blog")],
            ),
        ],
    )
    issues = validate_graph(graph)

    assert len(issues) == 1
    assert issues[0].kind == "invalid-source-type"
    assert "f1" in issues[0].detail
    assert "blog" in issues[0].detail


def test_allowed_source_types_match_schema_enum():
    assert _schema_source_types() == _ALLOWED_SOURCE_TYPES


def test_valid_source_types_validate_cleanly():
    graph = TypedGraph(
        statements=[
            Statement(
                id="f1",
                layer=0,
                text="Fact.",
                sources=[
                    Source(source_type=source_type)
                    for source_type in sorted(_schema_source_types())
                ],
            ),
        ],
    )

    assert validate_graph(graph) == []


def test_none_source_type_validates_cleanly():
    graph = TypedGraph(
        statements=[
            Statement(
                id="f1",
                layer=0,
                text="Fact.",
                sources=[Source(source_type=None)],
            ),
        ],
    )

    assert validate_graph(graph) == []


def test_flags_duplicate_statement_ids_in_typed_graph():
    graph = TypedGraph(
        statements=[
            Statement(id="f1", layer=0, text="Fact."),
            Statement(id="f1", layer=0, text="Duplicate fact."),
        ],
    )
    issues = validate_graph(graph)

    assert len(issues) == 1
    assert issues[0].kind == "duplicate-statement"
    assert "f1" in issues[0].detail


def test_flags_duplicate_statement_ids_parsed_across_files(tmp_path: Path):
    statements = tmp_path / "statements"
    statements.mkdir()
    (statements / "01-facts.md").write_text(
        "## L0 - Facts\n\n### f1: First fact.\n",
        encoding="utf-8",
    )
    (statements / "02-more-facts.md").write_text(
        "## L0 - Facts\n\n### f1: Second fact.\n",
        encoding="utf-8",
    )

    graph = parse_dir(tmp_path)
    issues = validate_graph(graph)

    assert len(issues) == 1
    assert issues[0].kind == "duplicate-statement"
    assert "f1" in issues[0].detail


def test_resolved_edges_validate_clean():
    graph = TypedGraph(
        statements=[
            Statement(id="f1", layer=0, text="Premise."),
            Statement(id="p1", layer=4, text="Policy."),
        ],
        edges=[Edge(source="p1", target="f1", relation="supports")],
    )
    assert validate_graph(graph) == []


def test_flags_dangling_edge_target():
    graph = TypedGraph(
        statements=[Statement(id="p1", layer=4, text="Policy.")],
        edges=[Edge(source="p1", target="f99", relation="supports")],
    )
    issues = validate_graph(graph)

    assert len(issues) == 1
    assert issues[0].kind == "unknown-statement"
    assert "f99" in issues[0].detail


def test_flags_dangling_edge_source():
    graph = TypedGraph(
        statements=[Statement(id="f1", layer=0, text="Fact.")],
        edges=[Edge(source="p99", target="f1", relation="supports")],
    )
    issues = validate_graph(graph)

    assert len(issues) == 1
    assert issues[0].kind == "unknown-statement"
    assert "p99" in issues[0].detail
    assert "source" in issues[0].detail


def test_flags_both_dangling_edge_endpoints():
    graph = TypedGraph(
        statements=[Statement(id="p1", layer=4, text="Policy.")],
        edges=[Edge(source="p99", target="f99", relation="supports")],
    )
    issues = validate_graph(graph)

    assert len(issues) == 2
    details = " ".join(i.detail for i in issues)
    assert {i.kind for i in issues} == {"unknown-statement"}
    assert "p99" in details
    assert "source" in details
    assert "f99" in details
    assert "target" in details


def test_flags_unknown_actor_when_actors_dir_given(tmp_path: Path):
    actors_dir = tmp_path / "actors"
    actors_dir.mkdir()
    (actors_dir / "destatis.md").write_text("# Destatis\n", encoding="utf-8")
    (actors_dir / "README.md").write_text("# Registry\n", encoding="utf-8")

    graph = TypedGraph(
        statements=[
            Statement(
                id="f1",
                layer=0,
                text="Fact.",
                endorsed_by=["destatis", "phantom-actor"],
                disputed_by=["another-phantom"],
            ),
        ],
    )
    issues = validate_graph(graph, actors_dir=actors_dir)

    assert len(issues) == 2
    kinds = {i.kind for i in issues}
    assert kinds == {"unknown-actor"}
    details = " ".join(i.detail for i in issues)
    assert "phantom-actor" in details
    assert "another-phantom" in details
    assert "destatis" not in details


def test_does_not_check_actors_when_no_actors_dir_given():
    graph = TypedGraph(
        statements=[
            Statement(id="f1", layer=0, text="Fact.", endorsed_by=["anyone"]),
        ],
    )
    assert validate_graph(graph) == []


def test_statement_relative_data_ref_validates_under_topic_data(tmp_path: Path):
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "real.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    (tmp_path / "statements").mkdir()

    graph = TypedGraph(
        statements=[
            Statement(
                id="f1",
                layer=0,
                text="Fact.",
                data_refs=[
                    DataRef(path="../data/real.csv"),
                ],
            ),
        ],
    )

    assert validate_graph(graph, topic_dir=tmp_path) == []


def test_bare_data_ref_validates_under_topic_data(tmp_path: Path):
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "real.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    (tmp_path / "statements").mkdir()

    graph = TypedGraph(
        statements=[
            Statement(
                id="f1",
                layer=0,
                text="Fact.",
                data_refs=[DataRef(path="real.csv")],
            ),
        ],
    )

    assert validate_graph(graph, topic_dir=tmp_path) == []


def test_flags_missing_data_file_when_topic_dir_given(tmp_path: Path):
    (tmp_path / "data").mkdir()
    (tmp_path / "statements").mkdir()

    graph = TypedGraph(
        statements=[
            Statement(
                id="f1",
                layer=0,
                text="Fact.",
                data_refs=[DataRef(path="../data/missing.csv")],
            ),
        ],
    )
    issues = validate_graph(graph, topic_dir=tmp_path)

    assert len(issues) == 1
    assert issues[0].kind == "missing-data-file"
    assert "missing.csv" in issues[0].detail


def test_flags_data_ref_traversal_to_existing_file_outside_topic_dir(
    tmp_path: Path,
):
    topic_dir = tmp_path / "topic"
    (topic_dir / "data").mkdir(parents=True)
    (topic_dir / "statements").mkdir()
    (tmp_path / "outside.csv").write_text("a,b\n1,2\n", encoding="utf-8")

    graph = TypedGraph(
        statements=[
            Statement(
                id="f1",
                layer=0,
                text="Fact.",
                data_refs=[DataRef(path="../../outside.csv")],
            ),
        ],
    )
    issues = validate_graph(graph, topic_dir=topic_dir)

    assert len(issues) == 1
    assert issues[0].kind == "missing-data-file"
    assert "../../outside.csv" in issues[0].detail


def test_flags_data_ref_traversal_even_when_data_basename_exists(
    tmp_path: Path,
):
    topic_dir = tmp_path / "topic"
    (topic_dir / "data").mkdir(parents=True)
    (topic_dir / "statements").mkdir()
    (tmp_path / "outside.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    (topic_dir / "data" / "outside.csv").write_text("a,b\n3,4\n", encoding="utf-8")

    graph = TypedGraph(
        statements=[
            Statement(
                id="f1",
                layer=0,
                text="Fact.",
                data_refs=[DataRef(path="../../outside.csv")],
            ),
        ],
    )
    issues = validate_graph(graph, topic_dir=topic_dir)

    assert len(issues) == 1
    assert issues[0].kind == "missing-data-file"
    assert "../../outside.csv" in issues[0].detail


def test_does_not_check_data_when_no_topic_dir_given():
    graph = TypedGraph(
        statements=[
            Statement(
                id="f1",
                layer=0,
                text="Fact.",
                data_refs=[DataRef(path="anywhere.csv")],
            ),
        ],
    )
    assert validate_graph(graph) == []


def test_full_example_validates_clean():
    topic_dir = Path(__file__).parent / "fixtures" / "full"
    graph = parse_dir(topic_dir)
    issues = validate_graph(graph, topic_dir=topic_dir)
    assert issues == [], "\n".join(f"{i.kind}: {i.detail}" for i in issues)


def test_schuldenbremse_validates_clean():
    topic_dir = ROOT / "src" / "topics" / "schuldenbremse"
    graph = parse_dir(topic_dir)
    issues = validate_graph(
        graph, actors_dir=ROOT / "src" / "actors", topic_dir=topic_dir
    )
    assert issues == [], "\n".join(f"{i.kind}: {i.detail}" for i in issues)
