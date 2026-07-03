# Fact-Check Log

All API and data-source claims in `PRESENTATION_DESIGN.md` and `README.md` are verified here before code is written. Each entry records: **what was checked**, **source**, **date**, **outcome**, and **decision that follows**.

---

## 1. Seoul Open Data — OA-12252 (subway ridership by station × hour)

- **Checked:** existence, current availability, update cadence, request quirks
- **Source:** https://data.seoul.go.kr/dataList/OA-12252/S/1/datasetView.do (dataset page); https://data.seoul.go.kr/together/guide/useGuide.do (API guide)
- **Date verified:** 2026-07-03
- **Outcome:**
  - Dataset is live, sourced from T-money.
  - API returns hourly tap-in / tap-out per station per date.
  - **Pagination:** hard cap of **1,000 rows per call** — must loop with `startIndex` / `endIndex`.
  - Response format: XML by default, JSON available (use JSON path).
- **Decision:** loader implements `startIndex=1, endIndex=1000` paging with retries. Full column list will be captured from a probe call before the schema-normalization stage.

## 2. Seoul Open Data — OA-12914 (subway ridership by station × day)

- **Checked:** existence, cadence
- **Source:** https://data.seoul.go.kr/dataList/OA-12914/S/1/datasetView.do
- **Date verified:** 2026-07-03
- **Outcome:** Dataset live. Daily release with ~3-day lag. Used as a coarser complement to OA-12252 for total-volume sanity checks and long-window trend.
- **Decision:** kept as secondary source. Primary analytical unit is OA-12252 (has the hourly dimension we need).

## 3. Seoul 생활이동 (life-flow / OD dataset) — DELIBERATELY NOT USED

- **Checked:** current availability
- **Outcome:** Dataset is under service renovation and not reliably usable in mid-2026.
- **Decision:** we do **not** rely on true origin-destination data. Instead, "flow" is reconstructed from tap-in / tap-out correlation between residential-cluster and business-cluster stations (documented as an explicit limitation in the talk, Section 6.5).

## 4. data.go.kr — MOLIT apartment sale transactions

- **Checked:** endpoint, request parameters, current availability
- **Source:** https://www.data.go.kr/data/15126469/openapi.do
- **Date verified:** 2026-07-03
- **Outcome:**
  - Service name: **국토교통부_아파트 매매 실거래가 자료** (`getRTMSDataSvcAptTradeDev` is the standard operation).
  - Requires **법정동 5-digit code** (`LAWD_CD`) + **계약년월 6-digit** (`DEAL_YMD`).
  - Free, no daily quota for standard usage tier; auth key issued in 1–2 hours after 활용신청.
  - `PublicDataReader` (open-source Python wrapper) is a validated shortcut and will be used to avoid re-implementing XML paging boilerplate.
- **Legal-dong codes needed for the 3 focus areas:**
  - Gangnam-gu (강남구): **11680**
  - Mapo-gu (마포구, contains 홍대입구): **11440**
  - Yeongdeungpo-gu (영등포구, contains 여의도): **11560**
- **Decision:** confirmed in the loader spec. Legal-dong code map is stored as `src/lawd_codes.py`.

## 5. Station coordinates & administrative boundary GeoJSON

- **Checked:** availability
- **Outcome:** Station coordinates are available via Seoul Open Data Plaza; administrative boundary GeoJSON is available through the Statistics Geographic Information Service (SGIS) and from community-maintained GitHub repos (Vuski/admdongkor).
- **Decision:** for lecture reproducibility we bundle a snapshot of gu-level boundaries under `data/raw/geo/` (small file, static, no license issue for administrative boundaries).

## 6. GitHub Pages + Plotly + GitHub Actions

- **Checked:** whether the "raw data left / library-function buttons middle / animating visualization right" concept can be deployed as a purely static site
- **Source:** GitHub Pages custom workflow docs (https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages); community references on Plotly + GitHub Pages
- **Date verified:** 2026-07-03
- **Outcome:**
  - GitHub Pages is static-only. A live Dash server **cannot** be hosted there.
  - The right approach: **precompute every intermediate pipeline state as JSON** in the notebook, ship Plotly.js on the browser side, and let vanilla JavaScript swap traces on button click. Fully static. Deploys to GitHub Pages cleanly via GitHub Actions.
  - GitHub Actions provides an official three-step deploy pipeline: `configure-pages` → `upload-pages-artifact` → `deploy-pages`.
- **Decision:** architecture is:
  1. `src/build_interactive.py` runs the pipeline, exports per-stage snapshots to `interactive/data/*.json`
  2. `interactive/index.html` + `interactive/js/pipeline.js` load snapshots and animate transitions
  3. `.github/workflows/deploy.yml` runs the build on every push to `main` and publishes `interactive/` to Pages
  - No server needed. The visitor sees a "click → transformation → visualization" experience that feels dynamic but is 100% pre-rendered.

## 7. Guest-lecture format

- **Checked:** with the professor
- **Outcome:** 50 min talk + 10 min Q&A, MSc audience with weak coding/finance background, professor explicitly asked that the talk emphasize graphs and the code behind graphs, and that it show how the presenter uses AI to build projects.
- **Decision:** narrative arc and Section 7 (AI as a Co-pilot) are shaped by these two requests specifically.

---

## Open items to resolve during Phase 2

- [ ] Confirm exact column names of OA-12252 with a live probe (they include Korean characters and occasionally shift).
- [ ] Decide on the exact 24-month window (rolling from most-recent complete month).
- [ ] Choose `k` for KMeans via elbow + silhouette on the real feature matrix (spec assumes ~5).
