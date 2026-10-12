# Web renderer

Static single-page renderer for `topic.json` (the output of `build.py`). Loads
React, React Flow, htm, and Tailwind from CDNs - no bundler, no `npm install`.

## Run locally

From the **project root**:

```bash
# 1. Generate a topic.json from one of the example topics or a real topic.
#    Pass the output path as a 2nd argument (don't use shell redirection -
#    PowerShell's `>` re-encodes to UTF-16-LE-with-BOM and breaks JSON.parse).
uv run python build.py src/topics/schuldenbremse src/web/topic.json

# 2. Serve src/web/ over HTTP. (Opening index.html via file:// won't work because
#    the page fetches topic.json, and browsers block fetch() over file://.)
python -m http.server 8000 --directory src/web
```

Then open <http://localhost:8000>.

## Smoke test

The focused no-network renderer smoke generates `src/web/topic.json` from the
Schuldenbremse topic, checks the HTML import map and module entrypoint, verifies
the generated graph has renderable statement data, checks the dependency-trace
helper, and runs `node --check` on the web modules:

```bash
uv run pytest tests/test_web_renderer_smoke.py -q --no-cov
node --check src/web/main.js
node --check src/web/graph-utils.js
```

## Layer-color legend

| Layer | Meaning | Visual |
|---|---|---|
| L0 | Empirical fact | grey |
| L1 | Stylized fact | blue |
| L2 | Causal mechanism | orange |
| L3 | Value claim | purple |
| L4 | Policy position | red |

Edges:

| Relation | Style |
|---|---|
| `supports` | solid green |
| `attacks` / `attacked-by` | dashed red |
| `evidence` | solid blue |
| `qualifies` | dotted purple |
| (other) | grey |

Layout uses a custom layer-band pass in `main.js`: L0 starts on the left,
higher layers progress to the right, and cards are softly shifted within their
bands to reduce overlap and keep connected statements near each other.

## Files

- `index.html` - minimal HTML shell with an import map pointing at
  [esm.sh](https://esm.sh/) for React, `@xyflow/react`, and `htm/react`.
  Tailwind is loaded through the play CDN.
- `main.js` - single ES module: fetches `./topic.json`, builds the
  policy-first reference viewer, renders React Flow nodes/edges with the custom
  layer-band layout, and manages the details drawer, view modes, legend, and
  trace state.
- `graph-utils.js` - pure graph helpers for policy extraction, view filtering,
  and dependency-only trace traversal.
- `topic.json` - generated build artifact (gitignored). Run `build.py` to
  produce.

## Interactions

- **Policy positions** rail - shows each L4 policy as a readable entry point
  with endorsing/disputing actor badges. Click a policy to inspect it and keep
  the graph as context.
- **Click a node** - opens the details drawer with the full statement, sources
  (including retrieval/source-type metadata), endorsing/disputing actors, data
  refs, and relationship chips.
- **View modes** - `All` shows the full graph; `Facts & mechanisms` isolates
  the L0-L2 substrate.
- **Trace dependencies** - fades all nodes outside the selected statement's
  dependency chain. The trace follows `supports`, `evidence`, and `qualifies`;
  attack relations remain visible in the details drawer but are not followed,
  so policy conflicts do not expand the dependency trace.
- **Mobile drawer** - on narrow screens the selected-statement details open as
  a full-screen drawer while the graph and policy rail remain available behind
  it.

## Limitations (Phase A)

- **Tailwind play CDN is not for production.** Fine for a demo/tester round; for
  deployment, swap to a real Tailwind build step.
- **No data-trace sparklines yet.** Statements with `data_refs` show the label
  and description in the details drawer but do not yet fetch and plot the
  underlying CSV.
- **No URL-state sync.** Selected statement and view mode are not reflected in
  the URL, so you cannot share a deep link to a specific view.
