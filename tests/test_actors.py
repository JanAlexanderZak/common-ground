import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).parent.parent
ACTORS_DIR = ROOT / "src" / "actors"
ACTORS_README = ACTORS_DIR / "README.md"
REQUIRED_ACTOR_FIELDS = ("id", "type", "country", "url", "mission")
REGISTRY_NON_ACTOR_FILES = {"README.md"}


def _validate_actor_registry(actors_dir: Path, readme_path: Path) -> list[str]:
    actor_types = _documented_actor_types(readme_path)
    issues: list[str] = []

    for path in sorted(actors_dir.glob("*.md")):
        if path.name in REGISTRY_NON_ACTOR_FILES:
            continue

        frontmatter = _actor_frontmatter(path)
        if frontmatter is None:
            issues.append(f"{path.name}: missing YAML frontmatter")
            continue

        for field in REQUIRED_ACTOR_FIELDS:
            if frontmatter.get(field) in (None, ""):
                issues.append(f"{path.name}: missing required field: {field}")

        actor_id = frontmatter.get("id")
        if actor_id is not None and actor_id != path.stem:
            issues.append(
                f"{path.name}: filename stem {path.stem!r} does not match "
                f"frontmatter id {actor_id!r}"
            )

        actor_type = frontmatter.get("type")
        if actor_type is not None and actor_type not in actor_types:
            issues.append(f"{path.name}: undocumented actor type: {actor_type}")

    return issues


def _documented_actor_types(readme_path: Path) -> set[str]:
    readme = readme_path.read_text(encoding="utf-8")
    return set(re.findall(r"^\|\s*`([^`]+)`\s*\|", readme, flags=re.MULTILINE))


def _actor_frontmatter(path: Path) -> dict[str, object] | None:
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        return None

    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            loaded = yaml.safe_load("\n".join(lines[1:index])) or {}
            return loaded if isinstance(loaded, dict) else None

    return None


def _write_actor_profile(
    path: Path,
    *,
    actor_id: str | None,
    actor_type: str | None,
    omitted_fields: set[str] | None = None,
) -> None:
    omitted_fields = omitted_fields or set()
    frontmatter = {
        "id": actor_id,
        "type": actor_type,
        "country": "DE",
        "url": "https://example.invalid",
        "mission": "Example actor",
    }
    lines = ["---"]
    lines.extend(
        f"{key}: {value}"
        for key, value in frontmatter.items()
        if value is not None and key not in omitted_fields
    )
    lines.extend(["---", "", f"# {path.stem}"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_actor_registry_files_match_documented_shape():
    issues = _validate_actor_registry(ACTORS_DIR, ACTORS_README)

    assert issues == []


@pytest.mark.parametrize(
    ("filename", "actor_id", "actor_type", "expected_issue"),
    [
        ("different-name.md", "declared-id", "government", "filename stem"),
        ("missing-id.md", None, "government", "missing required field: id"),
        ("bad-type.md", "bad-type", "unlisted-type", "undocumented actor type"),
    ],
)
def test_actor_registry_validator_reports_shape_issues(
    tmp_path: Path,
    filename: str,
    actor_id: str | None,
    actor_type: str | None,
    expected_issue: str,
):
    actors_dir = tmp_path / "actors"
    actors_dir.mkdir()
    _write_actor_profile(
        actors_dir / filename,
        actor_id=actor_id,
        actor_type=actor_type,
    )

    issues = _validate_actor_registry(actors_dir, ACTORS_README)

    assert any(expected_issue in issue for issue in issues)


@pytest.mark.parametrize("field", REQUIRED_ACTOR_FIELDS)
def test_actor_registry_validator_requires_all_frontmatter_fields(
    tmp_path: Path, field: str
):
    actors_dir = tmp_path / "actors"
    actors_dir.mkdir()
    _write_actor_profile(
        actors_dir / "example.md",
        actor_id="example",
        actor_type="government",
        omitted_fields={field},
    )

    issues = _validate_actor_registry(actors_dir, ACTORS_README)

    assert any(f"missing required field: {field}" in issue for issue in issues)


def test_actor_registry_validator_ignores_non_actor_registry_files(tmp_path: Path):
    actors_dir = tmp_path / "actors"
    actors_dir.mkdir()
    (actors_dir / "README.md").write_text("# Registry docs\n", encoding="utf-8")
    _write_actor_profile(
        actors_dir / "example.md",
        actor_id="example",
        actor_type="government",
    )

    issues = _validate_actor_registry(actors_dir, ACTORS_README)

    assert issues == []
