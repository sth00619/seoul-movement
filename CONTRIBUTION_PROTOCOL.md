# Contribution Protocol

**Purpose.** SONG will keep dropping materials into this project — screenshots, articles, reference URLs, code requests. This document is the standing agreement for how those get processed so nothing is lost and the repo/Notion mirror stay coherent.

This is written from Claude's side, but SONG is welcome to override any rule at any time.

---

## 1. What SONG hands off (5 categories)

| Type | Example | Where it lands |
|---|---|---|
| **A · Reference URL** | "look at this article on Kepler.gl" | `docs/references/references.md` (annotated) → Notion "Study Vault" |
| **B · Screenshot / image** | Instagram post with a data-science roadmap | `docs/references/images/YYYY-MM-DD_slug.png` + one-paragraph summary in `references.md` |
| **C · Dataset / spreadsheet** | CSV of station traffic, PDF of policy report | `data/raw/external/` with a `SOURCE.md` sidecar noting license + fetch date |
| **D · Code request** | "write a Python function that…" | new module under `src/` (or a scratch file under `notebooks/scratch/`) + tests + README section |
| **E · Design / aesthetic input** | color palette, dashboard mock | `docs/design/` with a dated markdown note pointing to the asset |

---

## 2. Claude's response format (every drop)

Every time SONG hands off material, Claude replies with:

1. **Classification** — which of the 5 categories above
2. **Fact-check** — before doing anything, verify the source is current (per SONG's standing rule: *기본적인 팩트 체크를 하고 진행*)
3. **Placement decision** — exact repo path + Notion location
4. **Action taken** — files created / updated, with paths
5. **What SONG needs to do next** — usually just "review and commit," sometimes "run this cell"

Claude does **not** stall on drops that are obviously safe (a public article URL, a personal screenshot). Claude asks before proceeding only when: license is unclear, category is ambiguous, or the drop would replace existing content.

---

## 3. GitHub organization rules

**Every commit follows this convention:**

```
<type>(<scope>): <short description>

Longer explanation if the change isn't obvious from the diff.
Refs: <notion page ID or URL if applicable>
```

Types (Conventional Commits, small subset):
- `feat` — new capability (chart, dataset, module)
- `fix` — corrects a bug or a wrong fact
- `docs` — README, reference notes, meeting logs
- `refactor` — code restructure with no behavior change
- `chore` — deps, CI, gitignore
- `data` — persisted parquet / JSON updates

Scopes for this project: `ingest`, `preprocess`, `features`, `cluster`, `charts`, `interactive`, `slides`, `docs`, `ci`.

**Branch strategy.** For a project of this size, `main` is the working branch. Feature branches are used only when a change touches ≥3 files across ≥2 scopes.

**Every PR (even self-authored) gets a one-paragraph description** with: what changed, why, screenshot if visual. This is the pattern HR reviewers look for when scanning a candidate's repo activity.

---

## 4. Notion organization

The Notion mirror lives under the existing 2026-Summer-Study space and follows this three-tier structure:

### Tier 1 · Project database entry
One row per project. Columns: `Name`, `Status` (Planning/In progress/Shipped), `Category` (Finance/Transport/Tourism/DA-BI/Growth/ML-DS/AI-Eng/MCP), `Featured` (★ pin), `Repo`, `Live demo`, `Slides`, `Post-mortem`.

For this project, the row is:
- Name: *Reading Seoul Through Its Movement*
- Category: DA/BI
- Status: In progress → Shipped (after the talk)
- Featured: ★ (recommend pinning)

### Tier 2 · Study Vault (references only)
A separate database for URLs, screenshots, and articles that inspire work but aren't tied to one project. Each row: `Title`, `Type` (Article/Screenshot/Video/Repo), `Source`, `Field` (Data/ML/Growth/Design/Career), `Related project` (link back to Tier 1), `Notes` (one-paragraph takeaway).

**Rule:** every image or URL SONG drops gets a row here first, even if it also lands in a project's `docs/references/`. This makes the Vault the single searchable index across all portfolios.

### Tier 3 · Post-mortem / retro (private)
After every shipped milestone, a private page under the project row: what went well, what didn't, what to change for the next iteration. These are not for HR — they're for SONG's own growth loop.

---

## 5. Code request protocol (category D)

When SONG asks for code, Claude follows this order:

1. **Restate the requirement** in one sentence, with any assumption made explicit
2. **State placement** — which module, why there
3. **Write the module first, tests second, notebook wiring third** — never inline in the notebook if it's going to be reused
4. **Every function gets:** a docstring explaining *what* and *why this approach*, type hints, and at least one usage example either in the docstring or in a smoke test
5. **Every code block that reads outside the pure-python stdlib** (pandas, sklearn, requests, etc.) gets a comment noting the version + a one-liner on why that library was chosen

This matches what senior code reviewers scan for in a portfolio: **structure > cleverness, tests > confidence, comments that explain why rather than what**.

### Language conventions
- **Python** is the default for data / analysis / ML work.
- **Java** is used when SONG requests it explicitly (aligns with the 26-month backend background). If chosen, Claude uses modern Java (records, `var`, streams, `Optional`), and follows Google Java Style.
- **JavaScript** is used only in `interactive/js/` for the browser side.
- **SQL** goes in `sql/` snippets when applicable; Postgres dialect assumed.

---

## 6. HR / recruiter surface

Every project's top-level `README.md` is written to be scannable in **30 seconds** by a hiring manager:

- **Line 1:** one-sentence description of what the project does
- **Line 2:** live demo URL, slide deck, main notebook, in that order
- **First scroll:** what problem, what data, what result — no code yet
- **Second scroll:** architecture / stack, then repo layout
- **Bottom:** about the author + link to full portfolio

This structure is applied to every project SONG ships, not just this one.

---

## 7. When SONG says "add this to the portfolio"

Standard flow:

1. New folder under `2026-Summer-Study/projects/<slug>/`
2. Follow this repo's layout as the template
3. Add a `projects-library.js` entry: `FILE No.`, category, status, tech tags, "why this matters" one-liner
4. Add a Tier 1 Notion row linking back to the folder
5. If the project has a live demo → deploy via `.github/workflows/deploy.yml` copied from here
6. If the project should be a Featured Case, pin it (max 4 total per portfolio rules)

---

## 8. Sanity rule (always applies)

Every response to SONG:
- **팩트체크 먼저** (per userPreference)
- No preamble, no "here's what I'll do" — just do it
- If a decision needs SONG's input, ask **before** doing work, not after
- Deliver files, not text blocks copied into chat
