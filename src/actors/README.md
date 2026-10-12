# Actors registry

This directory is the central registry of **actors** referenced in Common Ground topic graphs via the `@<actor-id>` sigil (see [`format/spec.md`](../format/spec.md) §7.2). When a statement carries `> **Endorsed by:** @ifo-institut` or `> **Disputed by:** @diw-berlin`, the bare id resolves to a file in this directory.

## File format

One file per actor at `actors/<id>.md`. The `<id>` MUST match `[\w-]+` and equal the YAML `id:` field. Each file has YAML frontmatter followed by a short Markdown body:

```markdown
---
id: <id>
type: <enum>
country: <ISO-3166-1-alpha-2>
url: <homepage>
mission: <one-line description>
---

# <Display Name>

Short paragraph (1–3 sentences) describing the actor's role and, where relevant, their general stance on the policy question.
```

### `type` enum

| Value | Use for |
|---|---|
| `government-agency` | Statistical offices, central banks, courts, public funding banks |
| `government` | Federal / state cabinets and ministries |
| `parliament` | Legislatures |
| `political-party` | Parties (federal or state level) |
| `research-institute` | Economic research institutes, councils of experts |
| `ngo` | Non-governmental organizations and civil-society associations |
| `media` | Newspapers, broadcasters, magazines |
| `expert-individual` | Named individuals with verifiable public activity in the policy area |
| `ai-agent` | AI assistants / models acting as commenters or endorsers |

## Editorial policy

Body text MUST be **neutral and factual**. For political parties, you may note their general position on the policy area in one factual sentence (e.g. "tends to support reform of the debt brake as of 2024–25"), but the registry is not the place for advocacy.

## How to add a new actor

**Pull requests only.** Direct pushes to this directory are rejected.

To propose a new actor:

1. Open a PR adding `actors/<id>.md` following the format above.
2. The actor MUST be either
   - a **public entity** (government body, party, registered NGO, established media outlet, research institute), or
   - a **named individual** with verifiable public activity in the relevant policy area (op-eds, peer-reviewed work, parliamentary speeches, etc.).
3. The PR description MUST cite at least one verifiable source for the actor's existence and policy-area activity (homepage, Wikipedia, scholar profile, etc.).
4. Anonymous handles, pseudonyms, and ad-hoc activist coalitions without a stable institutional footprint are out of scope for v0.1.

Reviewers check: id collision, type fit, URL reachability, body neutrality, and that the actor is actually referenced (or expected to be referenced) by at least one topic statement.
