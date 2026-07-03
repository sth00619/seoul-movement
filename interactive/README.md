# Interactive Site — Quick Start

**What this is.** A fully static 3-pane demo of the pipeline. Left pane shows the data at each stage, middle pane shows the transformation buttons, right pane shows the visualization that results. Every state transition is precomputed — no server, no runtime Python. Deploys to GitHub Pages via GitHub Actions.

**Where it will live.** `https://sth00619.github.io/2026-Summer-Study/projects/seoul-movement-lecture/` once the repo is pushed.

---

## Local development (3 commands)

```bash
# 1. Regenerate the snapshot data (only needed if src/ changes)
python -m src.build_interactive --source mock

# 2. Serve the interactive/ folder as static files
python -m http.server 8000 --directory interactive

# 3. Open http://localhost:8000/ in your browser
```

That's it. Every stage transition, table update, and chart animation runs in the browser. Reload after `build_interactive.py` reruns to see new data.

---

## What's actually happening under the hood

1. **`src/build_interactive.py`** runs the full pipeline (Stages 0 → 4) and dumps every intermediate result as JSON.
2. **`interactive/data/pipeline.json`** is that dump. About 30 KB — one HTTP request loads everything.
3. **`interactive/index.html`** is the 3-pane skeleton with CSS and a placeholder for Plotly.
4. **`interactive/js/pipeline.js`** loads the JSON, wires up click handlers on the middle-pane buttons, and calls `Plotly.react()` to morph the right-pane chart on each transition.
5. **`Plotly.js v3.6.0`** is loaded from the Fastly CDN — no local install, no build step.

The whole thing is ~35 KB of code + 30 KB of data. First paint under 1 second on a cold Colab-grade connection.

---

## What GitHub Actions does

On every push to `main` that touches `interactive/**` or `src/build_interactive.py`:

1. Check out the repo
2. Install Python + dependencies from `requirements.txt`
3. Regenerate `interactive/data/pipeline.json` from processed data (or mock if processed isn't committed)
4. Upload `interactive/` as a Pages artifact
5. Deploy to `github-pages` environment

The workflow file is `.github/workflows/deploy.yml`. No manual step; every push updates the live site.

---

## The 5 stages the visitor sees

| Stage | Table shows | Chart shows |
|---|---|---|
| 0 · Raw | 15 rows × 52 columns of Korean-named data | Bar chart of column-type breakdown (48 hourly cols problem) |
| 1 · Normalized | Long tidy table (station, hour, direction, count) | Multi-line hourly ridership for 3 focus stations |
| 2 · Features | 6 dimensionless features per station | Radar chart of the 3 focus profiles |
| 3 · Clustered | Station → cluster mapping | Bar chart of cluster sizes with archetype names |
| 4 · Projected | UMAP 2D coordinates per station | 2D scatter, focus stations as ⭐ stars |

Each transition triggers:
- A **cell flash** animation on the left-pane table (subtle gold pulse)
- A **Plotly morph** on the right-pane chart (600ms cubic ease)
- The middle-pane active step gets a red left-border stamp

---

## Debugging checklist

- Chart doesn't appear → open browser DevTools console. Most likely the Plotly CDN is blocked on your network. Fallback: download `plotly-3.6.0.min.js` and reference it locally.
- Table shows "Failed to load pipeline data" → `data/pipeline.json` is missing or malformed. Rerun `python -m src.build_interactive`.
- Stage switching is instant with no animation → hard-refresh (Ctrl+Shift+R). Cached CSS.
- Font looks generic instead of Fraunces → Google Fonts blocked. The site still works; only typography degrades.

---

## What to change if extending

**Add a new stage:** append to `PIPELINE.stages` in `build_interactive.py` and add a matching entry to `STEPS[]` in `pipeline.js`.

**Add a new chart type:** add a builder in `pipeline.js` (`buildFoo()`) and a case in the `switch` block of `renderViz()`.

**Change the palette:** everything is driven by CSS variables at the top of `style.css`. The Plotly charts use `AXIS_STYLE` and hard-coded hex codes in `pipeline.js`.
