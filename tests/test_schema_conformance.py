import json
from pathlib import Path

import jsonschema
import pytest

from common_ground import parse_dir, to_json
from common_ground.model import Edge, Statement, TypedGraph

ROOT = Path(__file__).parent.parent
SCHEMA = json.loads((ROOT / "src" / "format" / "schema.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    "topic_path",
    [
        ROOT / "tests" / "fixtures" / "minimal",
        ROOT / "tests" / "fixtures" / "edges",
        ROOT / "tests" / "fixtures" / "full",
        ROOT / "src" / "topics" / "schuldenbremse",
    ],
    ids=lambda p: p.relative_to(ROOT).as_posix(),
)
def test_to_json_conforms_to_schema(topic_path: Path) -> None:
    graph = parse_dir(topic_path)
    payload = json.loads(to_json(graph))
    jsonschema.validate(instance=payload, schema=SCHEMA)


def test_schema_accepts_edge_pair_relation_arrays() -> None:
    graph = TypedGraph(
        statements=[
            Statement(id="f1", layer=0, text="First fact"),
            Statement(id="f2", layer=0, text="Second fact"),
        ],
        edges=[
            Edge(source="f1", target="f2", relation="supports"),
            Edge(source="f1", target="f2", relation="attacks"),
            Edge(source="f2", target="f1", relation="qualifies"),
        ],
    )

    payload = json.loads(to_json(graph))

    jsonschema.validate(instance=payload, schema=SCHEMA)
