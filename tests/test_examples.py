from pathlib import Path

import pytest

from common_ground import parse_dir

EXAMPLES_DIR = Path(__file__).parent / "fixtures"

EXAMPLE_EXPECTATIONS = {
    "minimal": {"statements": 1, "edges": 0},
    "edges": {"statements": 5, "edges": 5},
    "full": {"statements": 2, "edges": 1},
}


@pytest.mark.parametrize("name", sorted(EXAMPLE_EXPECTATIONS))
def test_example_parses_with_expected_shape(name: str):
    expected = EXAMPLE_EXPECTATIONS[name]
    graph = parse_dir(EXAMPLES_DIR / name)

    assert len(graph.statements) == expected["statements"]
    assert len(graph.edges) == expected["edges"]


def test_full_example_exercises_every_primitive():
    graph = parse_dir(EXAMPLES_DIR / "full")

    assert graph.metadata.topic == "full-example"
    assert graph.metadata.title == "Full example"
    assert graph.metadata.language == "en"
    assert graph.metadata.contributors == ["Example Author"]

    by_id = {s.id: s for s in graph.statements}

    f1 = by_id["f1"]
    assert len(f1.sources) == 1
    assert f1.sources[0].url == "https://example.org/gdp-2023"
    assert f1.sources[0].source_type == "gov-statistics"
    assert f1.sources[0].jurisdiction == "DE"
    assert f1.endorsed_by == ["example-stats-agency"]
    assert len(f1.data_refs) == 1
    assert f1.data_refs[0].path == "../data/gdp.csv"

    p1 = by_id["p1"]
    assert p1.endorsed_by == ["example-party"]
    assert p1.disputed_by == ["opposition-party"]
