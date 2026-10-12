# Common Ground format specification — v0.1

**Status:** Draft, May 2026.
**Reference implementation:** the Python package [`common_ground`](../src/common_ground/) (parser based on `marko`).
**JSON schema for parser output:** [`schema.json`](schema.json).

---

## 1. Overview

The Common Ground format is a Markdown convention for typed, layered argument graphs. A topic is a directory of plain `.md` files; the parser extracts a structured graph from standard Markdown constructs (headings, lists, blockquotes) without introducing new syntax.

This spec describes the directory layout, the Markdown conventions, the data model produced by the parser, and the known limitations of v0.1.

---

## 2. Topic directory

A topic is a directory. The directory may contain:

```
<topic>/
├── topic.md            # OPTIONAL. Topic-level metadata + description.
├── statements/         # OPTIONAL. Statement files (.md).
│   └── *.md
├── data/               # OPTIONAL. Versioned datasets referenced by statements.
│   ├── *.csv
│   └── README.md
├── edges/              # OPTIONAL. Cross-cutting edge files (reserved; not parsed in v0.1).
│   └── *.md
└── translations/       # OPTIONAL. Parallel structure per language (reserved; not parsed in v0.1).
    └── <lang>/...
```

**Empty / missing optional components are not errors**: a topic with no `topic.md` produces empty metadata; a topic with no `statements/` produces an empty graph.

**Statement files are processed in alphanumeric filename order.** Convention: `01-facts.md`, `02-mechanisms.md`, ... lets authors control sequencing.

**Each statement file is parsed independently.** The H2/H3/Quote state machine resets at every file boundary; cross-file resolution happens at merge time, not at parse time.

---

## 3. `topic.md`

`topic.md` consists of an optional YAML frontmatter block followed by a Markdown body.

### 3.1 Frontmatter

A frontmatter block is delimited by lines containing exactly `---`:

```yaml
---
topic: <slug>            # machine-readable id
language: <bcp47-code>   # e.g. "de", "en", "de-DE"
version: <string>        # use a string; quote numerics like "0.1"
contributors:            # list of strings
  - "Jane Doe"
license: <SPDX-id>       # e.g. "AGPL-3.0", "MIT"
actors-registry: <path>  # optional path or URL to an external actors registry
---
```

All fields are optional. Unknown keys are silently ignored for forward compatibility.

### 3.2 Body

If present, the first H1 (`# Title`) in the body is extracted as `metadata.title`. The remainder of the body is currently not parsed (reserved for future use as a topic description).

---

## 4. Layers

A second-level heading of the form

```markdown
## L<n> — <name>
```

opens a layer section. The integer `<n>` is the layer index. Until the next layer heading (or end of file), all H3 statements inherit `<n>` as their layer.

Conventional indices:

| `n` | Meaning |
|---:|---|
| 0 | Empirical fact |
| 1 | Stylized fact |
| 2 | Causal / mechanism claim |
| 3 | Value claim |
| 4 | Policy position |

The `—` is a typographic convention; the parser only requires the substring `L<n>` somewhere in the heading. The dash, name, and any other heading content are display-only.

A new layer heading **resets the current statement context**, so any list immediately following a new H2 is not attributed to a statement from the previous layer.

---

## 5. Statements

A third-level heading of the form

```markdown
### <id>: <text>
```

defines a statement. Constraints:

- `<id>` matches the regex `[\w-]+` (letters, digits, underscore, hyphen). Convention: `f1` for facts, `c1` for causal claims, `p1` for policies, `v1` for values.
- `<text>` is everything after the first `:`-and-space.
- The statement inherits the current layer (the most recent `## L<n>` heading in the same file).
- An H3 not preceded by a layer heading is silently skipped.

A statement opens a "current statement context" that the next list and the next blockquote can attach to. A new H3 closes the previous statement's context.

---

## 6. Edges

A bullet list **immediately following** a statement defines its outgoing edges. Each list item has the form:

```markdown
- **<relation>:** <target-id>[, <target-id>, ...]
```

For each target id, the parser emits one `Edge(source=current_statement.id, target=<target-id>, relation=<relation>)`.

**Relation labels are stored verbatim.** No canonicalization is applied. `supports`, `attacks`, `attacked-by`, `evidence`, `qualifies`, etc. are all distinct relations as far as the parser is concerned. Downstream consumers may apply their own canonical mapping (e.g. treat `attacked-by` as inverted `attacks`).

A list item that does not begin with a `**Key:**` strong-emphasis prefix is silently ignored. A list with no preceding statement is silently ignored.

---

## 7. Metadata blocks

A blockquote **immediately following** a statement is its metadata block. Inside a metadata block:

- Each paragraph that begins with a `**Key:**` strong-emphasis label is dispatched as a metadata field.
- A bullet list **between** two metadata fields attaches to the **last** field of the preceding paragraph as structured sub-fields.

A single CommonMark paragraph may contain multiple `**Key:**` fields separated only by line breaks (CommonMark merges consecutive `>` lines into one paragraph). The parser splits at every strong-emphasis run.

### 7.1 Citations: `Quelle:` / `Source:`

```markdown
> **Quelle:** [Label](url)
> - retrieved: <date>
> - source-type: <enum>
> - jurisdiction: <code>
```

- The first `Link` in the field's inline content provides `url` and `label` (link text).
- Sub-list keys recognized:

| Key | Type | Notes |
|---|---|---|
| `retrieved` | ISO-8601 date string | e.g. `2026-04-01` |
| `source-type` | enum | `legal-text` \| `gov-statistics` \| `peer-reviewed` \| `expert-report` \| `news` \| `opinion` |
| `jurisdiction` | string | free-form, e.g. `DE`, `EU-27`, `OECD` |

Sub-field keys are normalized: kebab-case → snake_case (e.g. `source-type` → `source_type`). Unknown sub-fields are silently ignored.

`Quelle:` (German) and `Source:` (English) are equivalent.

### 7.2 Actor attribution: `Endorsed by:` / `Disputed by:`

```markdown
> **Endorsed by:** @id1, @id2, @id3
> **Disputed by:** @id4
```

`@<actor-id>` references are extracted via regex `@([\w-]+)`. The leading `@` is a sigil; the model stores bare ids (`["id1", "id2", "id3"]`).

**Resolution against an actors registry is out of scope for v0.1.** The parser records ids only; loading actor profiles is a downstream step.

### 7.3 Data references: `Data:`

```markdown
> **Data:** [<label>](path/to/data.csv) — <description>
```

- The first `Link` provides `path` (link target) and `label` (link text).
- All inline content after the link is concatenated and stripped → `description`.

The parser does not validate that the referenced path exists or is a well-formed CSV.

### 7.4 Sub-list separator (authoring rule)

When a metadata block contains a sub-list followed by another `**Key:**` field, the two MUST be separated by a blank `>` line:

```markdown
> **Source:** [Example](https://example.org)
> - retrieved: 2026-04-01
> - source-type: gov-statistics
>
> **Endorsed by:** @example-agency
```

Without the blank `>`, CommonMark applies "lazy continuation" and the next `**Key:**` line is absorbed into the last sub-list item, corrupting both fields. This is a property of CommonMark, not of the parser.

---

## 8. Output data model

The parser produces a `TypedGraph`:

```python
TypedGraph
├── metadata:   TopicMetadata
├── statements: list[Statement]
└── edges:      list[Edge]

TopicMetadata(topic, title, language, version, contributors, license, actors_registry)
Statement(id, layer, text, sources, endorsed_by, disputed_by, data_refs)
Source(url, label, retrieved, source_type, jurisdiction)
DataRef(path, label, description)
Edge(source, target, relation)
```

**Always-present semantics**: `metadata` is never `None`; missing `topic.md` produces an empty `TopicMetadata`. List fields are never `None`; missing primitives produce empty lists. Optional scalars (`url`, `label`, etc.) are `None` when absent.

**JSON serialization**: `dataclasses.asdict` + `json.dumps(ensure_ascii=False)`. See [`schema.json`](schema.json) for the full JSON schema.

---

## 9. Edge cases & known limitations

- **No premise–conclusion micro-structures.** Argdown-style `(1) ... (2) ... ---- (3)` blocks are not supported. Use list-item edges instead.
- **No multi-paragraph statements.** A statement is a single H3; trailing prose between an H3 and its list/blockquote is silently dropped.
- **No nested topics.** Each topic is a flat directory.
- **No actor resolution.** The parser does not load or validate `actors/*.md` files.
- **No path validation for `Data:`.** Existence and content of referenced CSVs are not checked.
- **No reference validation.** `target-id`s in edges, actor ids, and `Same as:` references are recorded as written; dangling references are not flagged.
- **No heading hierarchy enforcement.** A file with H3 statements but no H2 layer header has those statements silently skipped (no `current_layer`).

These limitations are intentional for v0.1 — most map cleanly to validator features, which are deferred to a later iteration.

---

## 10. Versioning

This is **v0.1** of the format. Breaking changes are possible until v1.0.

v1.0 is targeted for the Phase B (Prototype Fund funded period, June–November 2027), at which point both the Markdown conventions and the JSON schema become stable. Pre-1.0 consumers should pin to a specific reference-implementation version.
