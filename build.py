"""Parse a topic directory, validate it, and emit JSON.

Usage: python build.py <topic-path> [output-path]

If <output-path> is given, the JSON is written to that file as UTF-8
(no BOM). Otherwise, it's printed to stdout. Prefer the file form on
Windows — PowerShell's `>` redirect re-encodes stdout to UTF-16-LE-
with-BOM, which downstream JSON parsers reject.

Reference resolution is checked against the in-repo `src/actors/`
registry (if present) and against `<topic>/data/` for data references.
Any unresolved references print to stderr and the script exits non-zero.
"""

import sys
from pathlib import Path

from common_ground import parse_dir, to_json, validate_graph

REPO_ROOT = Path(__file__).resolve().parent
ACTORS_DIR = REPO_ROOT / "src" / "actors"
TOPICS_DIR = REPO_ROOT / "src" / "topics"


def _resolve_actors_dir(topic_path: Path) -> Path | None:
    # The central actors/ registry only governs topics under topics/.
    # Examples and out-of-repo topics use their own (or no) actor IDs.
    if not ACTORS_DIR.is_dir():
        return None
    if TOPICS_DIR in topic_path.resolve().parents:
        return ACTORS_DIR
    return None


def main(argv: list[str]) -> int:
    if not 2 <= len(argv) <= 3:
        print(f"usage: {argv[0]} <topic-path> [output-path]", file=sys.stderr)
        return 2

    topic_path = Path(argv[1])
    graph = parse_dir(topic_path)

    actors_dir = _resolve_actors_dir(topic_path)
    issues = validate_graph(graph, actors_dir=actors_dir, topic_dir=topic_path)
    if issues:
        for issue in issues:
            print(f"{issue.severity}: {issue.kind}: {issue.detail}", file=sys.stderr)
        print(f"\n{len(issues)} issue(s) found in {topic_path}", file=sys.stderr)
        return 1

    json_str = to_json(graph)

    if len(argv) == 3:
        Path(argv[2]).write_text(json_str + "\n", encoding="utf-8")
    else:
        # Force UTF-8 on stdout so non-ASCII content survives shell redirection
        # on Windows (default cp1252 / UTF-16-LE-with-BOM corrupt UTF-8 bytes).
        sys.stdout.reconfigure(encoding="utf-8")
        print(json_str)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
