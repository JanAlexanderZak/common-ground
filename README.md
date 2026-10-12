# Common Ground

Markdown-based toolchain for typed, layered argument graphs. The format encodes empirical facts, mechanisms, values, and policies as layered statements with explicit evidence, actor attribution, and data references — all in plain Markdown that renders sensibly on GitHub.

Runs on https://janalexanderzak.github.io/common_ground

## Format example

````markdown
## L0 — Empirische Fakten

### f2: Schuldenstand-zu-BIP lag Ende 2023 bei 62,4%

> **Quelle:** [Destatis 2024](https://www.destatis.de/...)
> - retrieved: 2026-04-01
> - source-type: gov-statistics
> **Endorsed by:** @destatis
> **Data:** [`debt-to-gdp.csv`](../data/debt-to-gdp.csv) — column `debt_to_gdp_pct`, 2010–2024

## L4 — Politikvorschläge

### p1: Reform der Schuldenbremse für Investitionen

- **supports:** f2
- **attacked-by:** p2
````

## Python API

```python
from pathlib import Path
from common_ground import parse_string, parse_dir, to_json

# Parse a single Markdown string.
graph = parse_string(text)

# Parse a topic directory: reads topic.md frontmatter then walks
# <topic>/statements/*.md alphabetically and merges.
graph = parse_dir(Path("topics/schuldenbremse"))

for s in graph.statements:
    print(f"L{s.layer} {s.id}: {s.text}")
for e in graph.edges:
    print(f"{e.source} --{e.relation}--> {e.target}")

# Emit JSON for the web renderer.
print(to_json(graph))
```

For the build pipeline the same is wrapped in a tiny CLI:

```bash
uv run python build.py src/topics/schuldenbremse public/schuldenbremse.json
```

(Pass the output path as a positional argument; do not use `>` redirection — PowerShell's `>` re-encodes to UTF-16-LE-with-BOM, which breaks downstream JSON parsers.)

## Web renderer

A static single-page renderer for any `topic.json` lives in [`src/web/`](src/web/). It loads React, React Flow, htm, and Tailwind from CDNs (no bundler) and visualizes the layered graph with a custom layer-band layout:

```bash
uv run python build.py src/topics/schuldenbremse src/web/topic.json
python -m http.server 8000 --directory src/web
# Open http://localhost:8000
```

The UI is static/GitHub Pages friendly: it fetches `topic.json`, starts from a readable L4 policy rail, opens a details drawer for statement sources / actors / data refs, offers `All` and `Facts & mechanisms` view modes, and exposes an explicit **Trace dependencies** action for dependency-only policy inspection. See [src/web/README.md](src/web/README.md) for layer / edge styling and known limitations.

## Format conventions

The parser interprets standard Markdown by *convention*, not custom syntax. Every `.md` file remains valid Markdown that renders on GitHub.

### Structural

- `## L<n> — <name>` (H2) sets the current layer (L0 facts → L4 policies). A new H2 resets the current statement.
- `### <id>: <text>` (H3) defines a statement. The id is the cross-file reference key (`f1`, `c1`, `p1`).
- A list immediately following a statement becomes its outgoing edges:
  `- **supports:** c1, v3` → two edges, `p1 --supports--> c1`, `p1 --supports--> v3`.
- Edges are lexically scoped to the preceding H3. A list with no preceding statement is silently ignored.
- Relation labels (`supports`, `attacked-by`, `evidence`, ...) are stored verbatim — canonicalization is a downstream concern.

### Multi-file topics

- A topic is a directory. The optional `topic.md` at its root holds metadata as YAML frontmatter (`topic`, `language`, `version`, `contributors`, `license`, `actors-registry`); its body's H1 becomes `metadata.title`.
- Each file under `<topic>/statements/*.md` is parsed independently — the H2/H3/Quote state machine resets at file boundaries. Each file should be self-contained semantically.
- Files are processed in alphabetical order. Use the convention `01-facts.md`, `02-mechanisms.md`, ... to control sequence.
- Cross-file references work after merging: a `**supports:** f1` in `04-policies.md` can target a statement defined in `01-facts.md`.
- A missing `statements/` directory or `topic.md` returns an empty graph / empty metadata (not an error). Validation is a downstream concern.

### Metadata blocks (in blockquotes following a statement)

- `> **Quelle:** [Label](url)` followed by `> - retrieved: ...`, `> - source-type: ...`, `> - jurisdiction: ...` populates a `Source`. (`Source:` works as an English alias.)
- `> **Endorsed by:** @id1, @id2` records actor IDs (the `@` is a sigil, stored without it).
- `> **Disputed by:** @id` likewise.
- `> **Data:** [label](path) — description` references a CSV.
- A single paragraph in a blockquote can contain multiple `**Key:**` fields separated only by line breaks. The trailing sub-list (if any) attaches to the last field.
- **Use a blank `>` line to separate a sub-list from a following field paragraph.** Without it, CommonMark applies lazy continuation and the next line gets glommed into the last list item, corrupting its parsed value:

  ```markdown
  > **Source:** [Example](https://example.org)
  > - retrieved: 2026-04-01
  > - source-type: gov-statistics
  >
  > **Endorsed by:** @example-agency
  ```

### Data model

```
TypedGraph
├── statements: list[Statement]
├── edges:      list[Edge]
└── metadata:   TopicMetadata

TopicMetadata(topic, title, language, version, contributors, license, actors_registry)
Statement(id, layer, text, sources, endorsed_by, disputed_by, data_refs)
Source(url, label, retrieved, source_type, jurisdiction)
DataRef(path, label, description)
Edge(source, target, relation)
```

## Quickstart

Requires [uv](https://docs.astral.sh/uv/) and Python 3.12 (uv will install Python automatically if needed).

```bash
uv sync                    # create .venv and install locked deps
uv run pytest              # run the test suite (coverage gate ≥80%)
uv run pytest tests/test_web_renderer_smoke.py -q --no-cov  # focused renderer smoke
node --check src/web/main.js # renderer ES module syntax check
uv run python              # drop into a REPL with the project env
uv run ruff check          # lint
uv run ruff check --fix    # lint + autofix
uv run ruff format         # format
uv run ty check            # type-check
```

### Troubleshooting

On Windows, if `uv run` fails with a cache `Access is denied` error under `%LOCALAPPDATA%\uv\cache`, use a repo-local cache and retry:

```powershell
$env:UV_CACHE_DIR = ".uv-cache"
uv run pytest -q
```

The `.uv-cache/` directory is ignored by Git. As a fallback, run checks through the existing virtualenv, for example `.\.venv\Scripts\python.exe -m pytest -q`.

## License

Code: **AGPL-3.0-or-later** — see [LICENSE](LICENSE).

Reference content under [src/topics/](src/topics/) carries its own per-topic license declared in each `topic.md`'s frontmatter (e.g. `CC-BY-SA-4.0` for the Schuldenbremse topic). The actor profiles under [src/actors/](src/actors/) and the format specification under [src/format/](src/format/) are AGPL-3.0-or-later along with the code.
