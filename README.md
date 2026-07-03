# Reading Seoul Through Its Movement

> A data story about where 10 million people go every day — and what it tells us about where to live, work, and invest.

**Guest lecture · Data Visualization and Business Analytics (MSc)** · 50 min + 10 min Q&A

Live interactive demo → [*(GitHub Pages URL will land here after deployment)*(https://sth00619.github.io/seoul-movement/)
Slide deck (PDF) → `slides/`
Full pipeline notebook → `notebooks/data_pipeline.ipynb`

---

## What this project is

Public subway ridership at ~300 Seoul stations is treated as a fingerprint of neighborhood function. The pipeline turns raw tap-in / tap-out counts into six engineered features per station, clusters them into ~5 "neighborhood types," and tests whether ridership signature predicts apartment price movement across a 24-month window.

Three focus stations anchor the narrative:

| Station | Cluster hypothesis | What we expect to see |
|---|---|---|
| **Gangnam** (강남) | Corporate & commerce | Weekday-heavy, sharp AM tap-out peak |
| **Hongdae** (홍대입구) | Youth & nightlife | Weekend-heavy, late-night ridership |
| **Yeouido** (여의도) | Business & finance | Extreme weekday skew, symmetric AM/PM |

Full 25-district version is ongoing; the lecture focuses on these three for narrative clarity.

---

## Repo layout

```
seoul-movement-lecture/
├── README.md                     ← you are here
├── PRESENTATION_DESIGN.md        ← narrative + chart design spec
├── FACT_CHECK_LOG.md             ← verified API status, endpoints, quirks
├── notebooks/
│   └── data_pipeline.ipynb       ← Stage 0 → Stage 7, exports all charts
├── src/
│   ├── ingest.py                 ← Seoul Open Data + MOLIT API loaders
│   ├── preprocess.py             ← Stage 1–2 (schema, entity resolution)
│   ├── features.py               ← Stage 3 (6-feature engineering)
│   ├── cluster.py                ← Stage 4 (StandardScaler + KMeans + UMAP)
│   ├── chart_functions.py        ← Chart A–O as reusable functions
│   └── mock_data.py              ← offline data generator (dev without API key)
├── data/
│   ├── raw/                      ← API pulls, timestamped (gitignored)
│   ├── processed/                ← cleaned parquet tables
│   └── exports/                  ← PNG + HTML for each chart
├── interactive/                  ← GitHub Pages site
│   ├── index.html                ← 3-pane demo (raw → transform → viz)
│   ├── css/style.css
│   ├── js/pipeline.js            ← state machine driving the animation
│   └── data/*.json               ← precomputed transformation snapshots
├── slides/                       ← PPT + PDF exports
├── docs/                         ← generated site output (deployed by Actions)
└── .github/workflows/
    └── deploy.yml                ← builds interactive/ → docs/ → GitHub Pages
```

---

## Tech stack

**Analysis** — pandas, numpy, scikit-learn, umap-learn, scipy.stats
**Static charts** — matplotlib, seaborn
**Interactive charts** — plotly (Python side) + plotly.js (browser side)
**Deployment** — GitHub Actions → GitHub Pages (static hosting only)

---

## Data sources (verified 2026-07)

| Dataset | Provider | ID / Endpoint | Cadence |
|---|---|---|---|
| Subway ridership by station × hour | Seoul Open Data Plaza | `OA-12252` | Monthly (T+5) |
| Subway ridership by station × day | Seoul Open Data Plaza | `OA-12914` | Daily (T+3) |
| Apartment sale transactions | data.go.kr (MOLIT) | `getRTMSDataSvcAptTradeDev` | Monthly |
| Station coordinates + gu GeoJSON | Seoul Open Data + SGIS | multiple | Static |

See `FACT_CHECK_LOG.md` for the exact verification trail, known quirks, and the rationale for *not* using the 서울 생활이동 (OD) dataset.

---

## How to reproduce

```bash
# 1. Install
pip install -r requirements.txt

# 2. Get API keys (free)
#    - Seoul Open Data Plaza: data.seoul.go.kr → 인증키 신청
#    - data.go.kr (MOLIT):    data.go.kr    → 활용신청
export SEOUL_API_KEY="..."
export MOLIT_API_KEY="..."

# 3. Run the full pipeline
jupyter lab notebooks/data_pipeline.ipynb
#    or, headlessly:
jupyter execute notebooks/data_pipeline.ipynb

# 4. Regenerate the interactive site locally
python src/build_interactive.py
python -m http.server 8000 --directory interactive/
#    → open http://localhost:8000

# 5. No API key? Use the mock data generator
python src/mock_data.py --seed 42 --out data/raw/
#    every downstream step will run identically
```

---

## About the author

Working professional — 26 months as a backend & database engineer, currently a development project manager in fintech and video platform development. This talk is one node of a broader portfolio building toward data analyst / data scientist / growth marketing roles. See the [main portfolio](https://sth00619.github.io/2026-Summer-Study) for other case files.
