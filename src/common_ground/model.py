"""Dataclasses that describe a parsed argument graph."""

from dataclasses import dataclass, field


@dataclass
class TopicMetadata:
    """Top-level metadata parsed from a topic's `topic.md`."""

    topic: str | None = None
    title: str | None = None
    language: str | None = None
    version: str | None = None
    contributors: list[str] = field(default_factory=list)
    license: str | None = None
    actors_registry: str | None = None


@dataclass
class Source:
    """A citation attached to a statement (URL, retrieval date, jurisdiction)."""

    url: str | None = None
    label: str | None = None
    retrieved: str | None = None
    source_type: str | None = None
    jurisdiction: str | None = None


@dataclass
class DataRef:
    """A reference from a statement to a data file (CSV, dataset, etc.)."""

    path: str
    label: str | None = None
    description: str | None = None


@dataclass
class Statement:
    """A node: id + layer + claim text, with its sources, endorsements, disputes, and data refs."""

    id: str
    layer: int
    text: str
    sources: list[Source] = field(default_factory=list)
    endorsed_by: list[str] = field(default_factory=list)
    disputed_by: list[str] = field(default_factory=list)
    data_refs: list[DataRef] = field(default_factory=list)


@dataclass
class Edge:
    """A typed relation from one statement to another (e.g. `supports`, `contradicts`)."""

    source: str
    target: str
    relation: str


@dataclass
class TypedGraph:
    """A parsed argument graph: statements, edges between them, and topic metadata."""

    statements: list[Statement] = field(default_factory=list)
    edges: list[Edge] = field(default_factory=list)
    metadata: TopicMetadata = field(default_factory=TopicMetadata)
