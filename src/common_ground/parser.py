"""Parse Markdown topic directories and statement files into a `TypedGraph`."""

import re
from pathlib import Path
from typing import Any

import marko
import yaml
from marko.block import BlankLine, Heading, Paragraph, Quote
from marko.block import List as MarkoList
from marko.inline import Link, StrongEmphasis

from common_ground.model import (
    DataRef,
    Edge,
    Source,
    Statement,
    TopicMetadata,
    TypedGraph,
)

_LAYER_PATTERN = re.compile(r"L(\d+)")
_STATEMENT_PATTERN = re.compile(r"^([\w-]+):\s+(.+)$")
_FIELD_PATTERN = re.compile(r"^([\w-]+):\s*(.+)$")
_ACTOR_REF_PATTERN = re.compile(r"@([\w-]+)")
_CITATION_LABELS = {"quelle", "source"}
_ENDORSED_LABELS = {"endorsed-by"}
_DISPUTED_LABELS = {"disputed-by"}
_DATA_LABELS = {"data"}


def _normalize_label(label: str) -> str:
    """Lower-case, trim, and dash-separate a field label for matching."""
    return label.lower().strip().replace(" ", "-")


def _extract_actor_ids(inlines: list[Any]) -> list[str]:
    """Return all `@actor-id` mentions found in a sequence of inline nodes."""
    text = "".join(_inline_text(c) for c in inlines)
    return _ACTOR_REF_PATTERN.findall(text)


def _inline_text(node: Any) -> str:
    """Recursively flatten a marko inline node (or list of them) into plain text."""
    if isinstance(node, str):
        return node
    children = getattr(node, "children", None)
    if isinstance(children, str):
        return children
    if isinstance(children, list):
        return "".join(_inline_text(c) for c in children)
    return ""


def _parse_edge_item(item: Any) -> tuple[str, list[str]] | None:
    """Parse a `**relation:** target1, ...` list item into (relation, [targets]) or None."""
    if not item.children:
        return None
    block = item.children[0]
    inline_children = getattr(block, "children", None)
    if not isinstance(inline_children, list) or not inline_children:
        return None

    first = inline_children[0]
    if not isinstance(first, StrongEmphasis):
        return None

    label = _inline_text(first).rstrip(":").strip()
    if not label:
        return None

    rest = "".join(_inline_text(c) for c in inline_children[1:])
    targets = [t.strip() for t in rest.split(",") if t.strip()]
    if not targets:
        return None

    return label, targets


def _parse_field_item(item: Any) -> tuple[str, str] | None:
    """Parse a `key: value` list item into (key, value); return None if it doesn't match."""
    if not item.children:
        return None
    block = item.children[0]
    text = _inline_text(block).strip()
    match = _FIELD_PATTERN.match(text)
    if match:
        return match.group(1).lower(), match.group(2).strip()
    return None


def _apply_source_field(source: Source, key: str, value: str) -> None:
    """Assign `value` to the matching attribute of `source` (dashes mapped to underscores)."""
    attr = key.replace("-", "_")
    if hasattr(source, attr):
        setattr(source, attr, value)


def _build_source(inline_rest: list[Any], sub_list: Any | None) -> Source:
    """Build a `Source` from an inline `Link` plus an optional sub-list of `key: value` fields."""
    source = Source()
    for inline in inline_rest:
        if isinstance(inline, Link):
            source.url = inline.dest
            source.label = _inline_text(inline)
            break
    if sub_list is not None:
        for item in sub_list.children:
            kv = _parse_field_item(item)
            if kv is not None:
                _apply_source_field(source, kv[0], kv[1])
    return source


def _build_data_ref(inline_value: list[Any]) -> DataRef | None:
    """Build a `DataRef` from an inline `Link` followed by optional description text."""
    path: str | None = None
    label: str | None = None
    description_parts: list[str] = []
    found_link = False

    for inline in inline_value:
        if isinstance(inline, Link) and not found_link:
            path = inline.dest
            label = _inline_text(inline)
            found_link = True
        elif found_link:
            description_parts.append(_inline_text(inline))

    if path is None:
        return None

    description = "".join(description_parts).strip() or None
    return DataRef(path=path, label=label, description=description)


def _split_paragraph_fields(inlines: list[Any]) -> list[tuple[str, list[Any]]]:
    """Split a paragraph's inlines on bold (`**Label:**`) markers into (label, inlines) pairs."""
    fields: list[tuple[str, list[Any]]] = []
    current_label: str | None = None
    current_value: list[Any] = []

    for inline in inlines:
        if isinstance(inline, StrongEmphasis):
            if current_label is not None:
                fields.append((current_label, current_value))
            current_label = _inline_text(inline).rstrip(":").strip()
            current_value = []
        elif current_label is not None:
            current_value.append(inline)

    if current_label is not None:
        fields.append((current_label, current_value))

    return fields


def _parse_metadata_block(quote: Quote, statement: Statement) -> None:
    """Attach a blockquote's citation / endorsement / dispute / data-ref fields to `statement`.

    A trailing sub-list is treated as detail for the last bold field of the
    preceding paragraph.
    """
    children = list(quote.children)
    i = 0
    while i < len(children):
        block = children[i]
        if isinstance(block, Paragraph):
            inlines = block.children if isinstance(block.children, list) else []
            fields = _split_paragraph_fields(inlines)

            sub_list: Any | None = None
            if fields and i + 1 < len(children) and isinstance(children[i + 1], MarkoList):
                sub_list = children[i + 1]

            for j, (raw_label, inline_value) in enumerate(fields):
                label = _normalize_label(raw_label)
                # Sub-list attaches to the last field — its immediate predecessor.
                field_sub_list = sub_list if j == len(fields) - 1 else None

                if label in _CITATION_LABELS:
                    statement.sources.append(_build_source(inline_value, field_sub_list))
                elif label in _ENDORSED_LABELS:
                    statement.endorsed_by.extend(_extract_actor_ids(inline_value))
                elif label in _DISPUTED_LABELS:
                    statement.disputed_by.extend(_extract_actor_ids(inline_value))
                elif label in _DATA_LABELS:
                    data_ref = _build_data_ref(inline_value)
                    if data_ref is not None:
                        statement.data_refs.append(data_ref)

            if sub_list is not None:
                i += 1
        i += 1


_FRONTMATTER_DELIMITER = "---"


def _split_frontmatter(content: str) -> tuple[str, str]:
    """Separate a leading `---`-delimited YAML frontmatter from the rest of the Markdown body."""
    lines = content.splitlines(keepends=False)
    if not lines or lines[0].strip() != _FRONTMATTER_DELIMITER:
        return "", content
    for i in range(1, len(lines)):
        if lines[i].strip() == _FRONTMATTER_DELIMITER:
            return "\n".join(lines[1:i]), "\n".join(lines[i + 1 :])
    return "", content


def _parse_topic_md(content: str) -> TopicMetadata:
    """Build a `TopicMetadata` from `topic.md` content (YAML frontmatter + first H1 as title)."""
    metadata = TopicMetadata()
    frontmatter, body = _split_frontmatter(content)

    if frontmatter:
        loaded = yaml.safe_load(frontmatter) or {}
        if isinstance(loaded, dict):
            metadata.topic = _str_or_none(loaded.get("topic"))
            metadata.language = _str_or_none(loaded.get("language"))
            metadata.version = _str_or_none(loaded.get("version"))
            metadata.license = _str_or_none(loaded.get("license"))
            metadata.actors_registry = _str_or_none(loaded.get("actors-registry"))
            contributors = loaded.get("contributors")
            if isinstance(contributors, list):
                metadata.contributors = [str(c) for c in contributors]

    if body.strip():
        doc = marko.parse(body)
        for node in doc.children:
            if isinstance(node, Heading) and node.level == 1:
                metadata.title = _inline_text(node)
                break

    return metadata


def _str_or_none(value: Any) -> str | None:
    """Return `str(value)`, or None if `value` is None."""
    if value is None:
        return None
    return str(value)


def parse_dir(topic_path: str | Path) -> TypedGraph:
    """Parse a topic directory (`topic.md` + `statements/*.md`) into a TypedGraph."""
    topic_path = Path(topic_path)
    graph = TypedGraph()

    topic_md = topic_path / "topic.md"
    if topic_md.is_file():
        graph.metadata = _parse_topic_md(topic_md.read_text(encoding="utf-8"))

    statements_dir = topic_path / "statements"
    if statements_dir.is_dir():
        for md_file in sorted(statements_dir.glob("*.md")):
            partial = parse_string(md_file.read_text(encoding="utf-8"))
            graph.statements.extend(partial.statements)
            graph.edges.extend(partial.edges)

    return graph


def parse_string(markdown: str) -> TypedGraph:
    """Parse a single statements-Markdown string into a partial TypedGraph (no metadata)."""
    doc = marko.parse(markdown)
    graph = TypedGraph()
    current_layer: int | None = None
    attachable_statement: Statement | None = None

    for node in doc.children:
        if isinstance(node, Heading):
            text = _inline_text(node)
            if node.level == 2:
                match = _LAYER_PATTERN.search(text)
                if match:
                    current_layer = int(match.group(1))
                attachable_statement = None
            elif node.level == 3 and current_layer is not None:
                match = _STATEMENT_PATTERN.match(text)
                if match:
                    statement = Statement(
                        id=match.group(1),
                        layer=current_layer,
                        text=match.group(2).strip(),
                    )
                    graph.statements.append(statement)
                    attachable_statement = statement
                else:
                    attachable_statement = None
            else:
                attachable_statement = None
        elif isinstance(node, MarkoList) and attachable_statement is not None:
            for item in node.children:
                parsed = _parse_edge_item(item)
                if parsed is None:
                    continue
                relation, targets = parsed
                for target in targets:
                    graph.edges.append(
                        Edge(
                            source=attachable_statement.id,
                            target=target,
                            relation=relation,
                        )
                    )
        elif isinstance(node, Quote) and attachable_statement is not None:
            _parse_metadata_block(node, attachable_statement)
        elif not isinstance(node, BlankLine):
            attachable_statement = None

    return graph
