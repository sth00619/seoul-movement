/* -----------------------------------------------------------------------
   Reading Seoul Through Its Movement — client-side pipeline animator
   Loads the precomputed pipeline.json and swaps state on step click.
   ----------------------------------------------------------------------- */

const DATA_URL = "data/pipeline.json";

// Pipeline step definitions — labels and library function names for the middle pane.
// The stage_id field must match the "id" of a stage inside pipeline.json.
const STEPS = [
  {
    stage_id: "raw",
    index_label: "STAGE 0",
    label: "Ingest raw API rows",
    func:  "requests.get()  ·  json_normalize()",
    tooltip: "Fetch OA-12252 from Seoul Open Data (paginated, tenacity-retried). What comes back is wide, Korean-named, string-typed.",
  },
  {
    stage_id: "standardized",
    index_label: "STAGE 0.5",
    label: "Rank distinctive columns",
    func:  "groupby().mean()  ·  coefficient of variation",
    tooltip: "34,560 raw rows collapse into 48 hour×direction columns. Coefficient of variation ranks which columns actually discriminate between stations — before any feature is hand-picked.",
  },
  {
    stage_id: "normalized",
    index_label: "STAGE 1",
    label: "Normalize schema",
    func:  "pd.melt()  ·  df.astype()  ·  rename()",
    tooltip: "Melt 48 hourly columns into (hour × direction). Coerce types. Canonicalize station names. Now every row is one observation.",
  },
  {
    stage_id: "features",
    index_label: "STAGE 2",
    label: "Engineer 6 features",
    func:  "groupby().agg()  ·  custom aggregators",
    tooltip: "Six dimensionless features per station: peak intensity, weekend balance, late-night share, directional asymmetry, volatility. This is the station's fingerprint.",
  },
  {
    stage_id: "clustered",
    index_label: "STAGE 3",
    label: "Standardize + KMeans",
    func:  "StandardScaler()  ·  KMeans.fit()",
    tooltip: "Standardize (mean 0, variance 1) so no single feature dominates by unit. Silhouette-select k. Cluster.",
  },
  {
    stage_id: "projected",
    index_label: "STAGE 4",
    label: "Project 6D → 2D (UMAP)",
    func:  "umap.UMAP().fit_transform()",
    tooltip: "UMAP preserves local neighborhood structure — stations of the same archetype land next to each other in the 2D scatter.",
  },
];

// Cached data + current state
let PIPELINE = null;
let CURRENT_STAGE_ID = null;

// ─────────────────────────────────────────────────────────────────────
// Bootstrap
// ─────────────────────────────────────────────────────────────────────
(async function init() {
  try {
    const res = await fetch(DATA_URL);
    if (!res.ok) throw new Error(`Failed to fetch ${DATA_URL}: ${res.status}`);
    PIPELINE = await res.json();
  } catch (err) {
    console.error(err);
    document.getElementById("data-tbody").innerHTML =
      `<tr><td style="color:#C1272D;padding:20px;">Failed to load pipeline data: ${err.message}</td></tr>`;
    return;
  }

  renderHeader();
  renderSteps();
  goToStage(STEPS[0].stage_id);
})();

// ─────────────────────────────────────────────────────────────────────
// Header meta
// ─────────────────────────────────────────────────────────────────────
function renderHeader() {
  document.getElementById("meta-generated").textContent =
    PIPELINE.generated_at.replace("T", " ").replace("Z", " UTC");
  const raw = PIPELINE.stages.find(s => s.id === "raw");
  document.getElementById("meta-records").textContent =
    `${raw.preview.total_rows.toLocaleString()} rows (${PIPELINE.n_months} months, source: ${PIPELINE.source})`;
}

// ─────────────────────────────────────────────────────────────────────
// Middle pane — pipeline steps
// ─────────────────────────────────────────────────────────────────────
function renderSteps() {
  const ol = document.getElementById("pipeline-steps");
  ol.innerHTML = "";
  STEPS.forEach(step => {
    const li = document.createElement("li");
    li.className = "step";
    li.dataset.stageId = step.stage_id;
    li.title = step.tooltip;
    li.innerHTML = `
      <span class="step-index">${step.index_label}</span>
      <span class="step-label">${step.label}</span>
      <span class="step-func">${step.func}</span>
    `;
    li.addEventListener("click", () => goToStage(step.stage_id));
    ol.appendChild(li);
  });
}

// ─────────────────────────────────────────────────────────────────────
// Stage transition — the interactive centerpiece
// ─────────────────────────────────────────────────────────────────────
function goToStage(stageId) {
  if (stageId === CURRENT_STAGE_ID) return;
  const stage = PIPELINE.stages.find(s => s.id === stageId);
  if (!stage) { console.warn("Unknown stage:", stageId); return; }
  CURRENT_STAGE_ID = stageId;

  const idx = STEPS.findIndex(s => s.stage_id === stageId);
  updateActiveStep(stageId);
  updateBadges(idx, STEPS[idx].label);
  updateDescription(stage.description);
  renderTable(stage.preview);
  renderViz(stage.viz);
  renderCode(stage);
}

function updateActiveStep(stageId) {
  document.querySelectorAll(".step").forEach(el => {
    el.classList.toggle("active", el.dataset.stageId === stageId);
  });
}

function updateBadges(index, label) {
  const text = `Stage ${index} · ${label.split(" ").slice(0, 3).join(" ")}`;
  document.getElementById("left-badge").textContent  = text;
  document.getElementById("right-badge").textContent = text;
}

function updateDescription(text) {
  const el = document.getElementById("stage-description");
  el.textContent = text;
}

// ─────────────────────────────────────────────────────────────────────
// Left pane — data table with flash animation
// ─────────────────────────────────────────────────────────────────────
function renderTable(preview) {
  document.getElementById("data-meta").textContent =
    `${preview.total_rows.toLocaleString()} rows × ${preview.total_cols} columns  ·  showing first ${preview.rows.length}`;

  const thead = document.getElementById("data-thead");
  thead.innerHTML = preview.columns.map(c => `<th>${escapeHtml(c)}</th>`).join("");

  const tbody = document.getElementById("data-tbody");
  tbody.innerHTML = preview.rows.map(row =>
    "<tr class='updated'>" + row.map(cell =>
      `<td>${escapeHtml(cell)}</td>`
    ).join("") + "</tr>"
  ).join("");

  // Trigger cell flash animation
  requestAnimationFrame(() => {
    setTimeout(() => {
      tbody.querySelectorAll(".updated").forEach(tr => tr.classList.remove("updated"));
    }, 800);
  });
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

// ─────────────────────────────────────────────────────────────────────
// Right pane — Plotly renderer (dispatches on viz.type)
// ─────────────────────────────────────────────────────────────────────
function renderViz(viz) {
  document.getElementById("viz-title").textContent    = viz.title;
  document.getElementById("viz-subtitle").textContent = viz.subtitle;
  const el = document.getElementById("viz-chart");

  let plotlyData, plotlyLayout;
  switch (viz.type) {
    case "bar":       [plotlyData, plotlyLayout] = buildBar(viz); break;
    case "lines":     [plotlyData, plotlyLayout] = buildLines(viz); break;
    case "radar":     [plotlyData, plotlyLayout] = buildRadar(viz); break;
    case "scatter2d": [plotlyData, plotlyLayout] = buildScatter(viz); break;
    default:
      console.warn("Unknown viz type:", viz.type);
      return;
  }

  Plotly.react(el, plotlyData, plotlyLayout, {
    responsive: true,
    displayModeBar: false,
  });
}

// ── Plotly builders ────────────────────────────────────────────────────
const AXIS_STYLE = {
  color: "#2A2622", gridcolor: "#E5E1D8", zerolinecolor: "#E5E1D8",
  titlefont: { family: "Fraunces, serif", size: 12, color: "#2A2622" },
  tickfont:  { family: "Inter, sans-serif", size: 11, color: "#4A443D" },
};
const BASE_LAYOUT = {
  paper_bgcolor: "#F4F0E6", plot_bgcolor: "#F4F0E6",
  font: { family: "Inter, sans-serif", size: 12, color: "#2A2622" },
  margin: { t: 30, r: 24, b: 50, l: 60 },
  showlegend: true,
  legend: { bgcolor: "rgba(0,0,0,0)", font: { size: 11 } },
};

function buildBar(v) {
  const data = [{
    type: "bar",
    x: v.trace.x,
    y: v.trace.y,
    marker: { color: v.trace.colors },
    hovertemplate: "<b>%{x}</b><br>%{y:,} <extra></extra>",
  }];
  const layout = {
    ...BASE_LAYOUT,
    xaxis: { ...AXIS_STYLE, title: "" },
    yaxis: { ...AXIS_STYLE, title: "Count" },
    showlegend: false,
    transition: { duration: 600, easing: "cubic-in-out" },
  };
  return [data, layout];
}

function buildLines(v) {
  const data = v.traces.map(t => ({
    type: "scatter", mode: "lines+markers",
    name: t.name, x: t.x, y: t.y,
    line: { color: t.color, width: 2.4 },
    marker: { color: t.color, size: 6, line: { color: "#F4F0E6", width: 1.5 } },
  }));
  const layout = {
    ...BASE_LAYOUT,
    xaxis: { ...AXIS_STYLE, title: v.xaxis || "" },
    yaxis: { ...AXIS_STYLE, title: v.yaxis || "" },
    transition: { duration: 600, easing: "cubic-in-out" },
  };
  return [data, layout];
}

function buildRadar(v) {
  const data = v.traces.map(t => ({
    type: "scatterpolar",
    r: t.r, theta: t.theta,
    fill: "toself",
    name: t.name,
    line: { color: t.color, width: 2.2 },
    fillcolor: hexToRgba(t.color, 0.18),
  }));
  const layout = {
    ...BASE_LAYOUT,
    polar: {
      bgcolor: "#F4F0E6",
      radialaxis: { visible: true, range: [0, 1], showticklabels: false,
                    gridcolor: "#D8CFB8", color: "#4A443D" },
      angularaxis: { gridcolor: "#D8CFB8", color: "#2A2622",
                     tickfont: { size: 11 } },
    },
    margin: { t: 30, r: 40, b: 30, l: 40 },
    legend: { orientation: "h", y: -0.08, x: 0.5, xanchor: "center",
              font: { size: 11 } },
  };
  return [data, layout];
}

function buildScatter(v) {
  const data = v.traces.map(t => {
    // Focus stations get bigger + labeled markers, others plain dots
    const sizes  = t.focus_flags.map(f => f ? 18 : 11);
    const opac   = t.focus_flags.map(f => f ? 1.0 : 0.85);
    const symbol = t.focus_flags.map(f => f ? "star" : "circle");
    const text   = t.focus_flags.map((f, i) => f ? `<b>${t.text[i]}</b>` : t.text[i]);
    return {
      type: "scatter", mode: "markers+text",
      name: t.name,
      x: t.x, y: t.y, text: text,
      textposition: "top center",
      textfont: { size: 11, color: "#2A2622", family: "Inter, sans-serif" },
      marker: {
        color: t.color, size: sizes, opacity: opac,
        symbol: symbol,
        line: { color: "#F4F0E6", width: 2 },
      },
      hovertemplate: "<b>%{text}</b><br>UMAP1=%{x:.2f}, UMAP2=%{y:.2f}<extra></extra>",
    };
  });
  const layout = {
    ...BASE_LAYOUT,
    xaxis: { ...AXIS_STYLE, title: v.xaxis || "UMAP 1" },
    yaxis: { ...AXIS_STYLE, title: v.yaxis || "UMAP 2" },
    transition: { duration: 600, easing: "cubic-in-out" },
  };
  return [data, layout];
}

// ── Utility ───────────────────────────────────────────────────────────
function hexToRgba(hex, alpha) {
  const h = hex.replace("#", "");
  const r = parseInt(h.slice(0, 2), 16);
  const g = parseInt(h.slice(2, 4), 16);
  const b = parseInt(h.slice(4, 6), 16);
  return `rgba(${r},${g},${b},${alpha})`;
}

// ─────────────────────────────────────────────────────────────────────
// Code drawer — real source per stage, with color-coded line tags
// ─────────────────────────────────────────────────────────────────────

const TAG_LABELS = {
  preprocessing:  "Preprocessing",
  outlier:        "Outlier / Distinctiveness",
  modeling:       "Modeling",
  visualization:  "Visualization",
};

function renderCode(stage) {
  const codeEl  = document.getElementById("code-content");
  const notesEl = document.getElementById("code-notes");
  const fileEl  = document.getElementById("code-toggle-file");

  if (!stage.code) {
    codeEl.textContent = "// No code snippet for this stage.";
    notesEl.innerHTML = "";
    fileEl.textContent = "—";
    return;
  }

  fileEl.textContent = stage.source_file || "—";

  // Let highlight.js tokenize the raw code first (syntax colors), then
  // wrap the requested line ranges in a colored <span> for the tag overlay.
  const highlighted = hljs.highlight(stage.code, { language: "python" }).value;
  const lines = highlighted.split("\n");
  const tags = stage.tags || [];

  const taggedLines = lines.map((lineHtml, i) => {
    const lineNo = i + 1;
    const tag = tags.find(t => lineNo >= t.start && lineNo <= t.end);
    const cls = tag ? `code-line tag-${tag.label}` : "code-line";
    return `<span class="${cls}">${lineHtml || " "}</span>`;
  });

  codeEl.innerHTML = taggedLines.join("\n");
  codeEl.className = "language-python hljs";

  // Notes panel — one card per tag, in source order
  notesEl.innerHTML = tags.map(t => `
    <div class="code-note tag-${t.label}">
      <span class="code-note-label">${TAG_LABELS[t.label] || t.label} · lines ${t.start}-${t.end}</span>
      ${escapeHtml(t.note)}
    </div>
  `).join("");
}

// ─────────────────────────────────────────────────────────────────────
// Code drawer toggle
// ─────────────────────────────────────────────────────────────────────
(function initCodeDrawer() {
  const toggle = document.getElementById("code-drawer-toggle");
  const body   = document.getElementById("code-drawer-body");
  const icon   = document.getElementById("code-toggle-icon");
  if (!toggle) return;

  toggle.addEventListener("click", () => {
    const isOpen = toggle.getAttribute("aria-expanded") === "true";
    toggle.setAttribute("aria-expanded", String(!isOpen));
    body.hidden = isOpen;
    icon.textContent = isOpen ? "▸" : "▾";
  });
})();
