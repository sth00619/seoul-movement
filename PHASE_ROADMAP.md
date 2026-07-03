# Phase Roadmap

This document tracks what has been produced so far and what comes next. Each phase closes with a checkpoint where SONG confirms before we proceed.

---

## Phase 1 — Foundation ✅ *(this delivery)*

**Purpose:** lock the architecture before writing any code that would be painful to unwind.

**Delivered:**
- `README.md` — HR-facing landing page for the repo
- `FACT_CHECK_LOG.md` — verified API endpoints, deliberate non-use of the OD dataset, GitHub Pages deployment architecture confirmed
- `PRESENTATION_DESIGN_md.pdf` — the design document that governs everything else (copied into the repo root as the source of truth)
- `.github/workflows/deploy.yml` — GitHub Actions workflow that auto-deploys `interactive/` to GitHub Pages on every push to main
- `requirements.txt` — pinned dependencies for the full pipeline
- `.gitignore` — keeps raw API pulls, secrets, and build artifacts out of the repo
- Full directory structure

**Architecture decisions locked:**
1. Primary data source is OA-12252 (hourly), with OA-12914 (daily) as complement. 서울 생활이동 is deliberately not used.
2. MOLIT apartment prices via `PublicDataReader` wrapper. Three focus 법정동 codes stored.
3. GitHub Pages hosts a **fully static** site. Dynamic feel comes from precomputed JSON snapshots + Plotly.js on the browser, not from a server.
4. GitHub Actions builds and deploys on every push to `main` — SONG never touches deployment manually.

---

## Phase 2 — Data Pipeline `data_pipeline.ipynb`

**Purpose:** produce clean, feature-ready tables that every downstream chart consumes.

**Will deliver:**
- `notebooks/data_pipeline.ipynb` — a single narrative notebook implementing PRESENTATION_DESIGN Stages 0 → 7:
  - Stage 0 · Ingestion (Seoul Open Data + MOLIT with retries and paging)
  - Stage 1 · Schema normalization (Korean → snake_case English)
  - Stage 2 · Entity resolution (station → coordinates → gu)
  - Stage 3 · Feature engineering (6 features per station)
  - Stage 4 · Standardization + KMeans + UMAP (with elbow & silhouette plots inline)
  - Stage 5 · Apartment price panel construction
  - Stage 6 · Statistical tests (KS test between focus-station distributions, one-way ANOVA on cluster price growth)
  - Stage 7 · Export figures (calls into `chart_functions.py`)
- `src/ingest.py`, `src/preprocess.py`, `src/features.py`, `src/cluster.py` — the modular Python behind the notebook
- `src/mock_data.py` — offline generator so the pipeline runs identically without an API key (useful for the CI job and for anyone reproducing the lecture)
- `src/lawd_codes.py` — legal-dong code lookup for the three focus gu

**Checkpoint before Phase 3:** SONG runs the notebook end-to-end (or looks at the executed output) and confirms the feature matrix, cluster labels, and price panel look sensible.

---

## Phase 3 — Chart Functions `chart_functions.py`

**Purpose:** every one of the 16 charts (A → P) implemented as a callable, tested, and exported as both PNG (for the PPT) and HTML (for the interactive site).

**Will deliver:**
- `src/chart_functions.py` — one `make_chart_X(...)` function per chart, all with:
  - Consistent styling (fonts, palette, size)
  - English-only labels
  - Docstring stating chart type, data required, and reason this chart type was chosen (mirroring the design doc)
- `data/exports/*.png` and `data/exports/*.html` for every chart
- A "chart index" thumbnail sheet (`data/exports/_index.png`) showing all 16 at a glance

**Checkpoint before Phase 4:** SONG scans the thumbnail sheet, flags any chart that doesn't read well, and either accepts or requests revisions.

---

## Phase 4 — Interactive Site `interactive/`

**Purpose:** the live demo shown in Section 8 of the lecture. Three panes: raw data (left), library-function buttons with arrows (middle), animating visualization (right).

**Will deliver:**
- `interactive/index.html` — semantic 3-pane layout
- `interactive/css/style.css` — matches the SONG Files dossier aesthetic (warm dark base, manila tan, JetBrains Mono for utility labels)
- `interactive/js/pipeline.js` — state machine:
  - each transformation button owns a `from_state` and `to_state`
  - clicking triggers (a) left pane updates to show the transformed dataframe head, (b) right pane morphs the Plotly chart via `Plotly.animate()`
  - each button has a tooltip: "why is this step necessary for the final chart to be honest?"
- `interactive/data/*.json` — precomputed snapshots (one per pipeline stage)
- `src/build_interactive.py` — the script Actions calls to regenerate snapshots from processed data

**Deploy target:** `https://sth00619.github.io/2026-Summer-Study/projects/seoul-movement-lecture/` (or a dedicated repo, TBD in Phase 4)

**Checkpoint before Phase 5:** SONG clicks through the deployed site on desktop and mobile, confirms the animation reads well.

---

## Phase 5 — Presentation Assets `slides/`

**Purpose:** everything needed to actually give the 50-minute talk.

**Will deliver:**
- `slides/deck.pptx` — matches the 9-section narrative arc in PRESENTATION_DESIGN
- Cover art + section dividers (visual identity matching the interactive site)
- Speaker notes for each slide (English on-slide, Korean in the notes for private reference)
- `slides/deck.pdf` — export for sharing with the professor / archive
- `slides/QR_interactive.png` and `slides/QR_repo.png` — the two QR codes on the final Q&A slide
- One-page handout PDF summarizing the three hypotheses and their outcomes, for students to take home

**Checkpoint:** SONG does a dry run against the clock. Talk should land within 48–52 minutes with room for the 10-minute Q&A.

---

## Notion mirror plan

For each phase's completion, mirror in Notion:
- **Project database entry** (existing 2026-Summer-Study tracker) with links to: this repo, the deployed interactive URL, the slide PDF
- **Post-lecture retrospective note** (private) after the talk: what landed, what didn't, questions students asked, changes for the 25-district version
- Portfolio site `projects-library.js`: new FILE No. under DA/BI category, status `SHIPPED` after the talk, tagged as `guest-lecture`, Featured Case eligible
