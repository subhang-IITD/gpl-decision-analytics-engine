"""Generate clean flow diagrams as PNGs for the submission document.

Pure matplotlib (boxes + arrows) so the images embed directly in LaTeX with no
external Mermaid/Graphviz step. Run:  python -m scripts.make_diagrams
Outputs into ../final_submission/diagrams/.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

OUT = Path(__file__).resolve().parent.parent.parent / "final_submission" / "diagrams"
OUT.mkdir(parents=True, exist_ok=True)

NAVY = "#1f2d4d"
BLUE = "#2e6fb0"
TEAL = "#2a9d8f"
AMBER = "#e9a23b"
GREY = "#5c6b7a"
LIGHT = "#eef3f8"


def _box(ax, x, y, w, h, text, fc, tc="white", fs=11, bold=True):
    box = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.06",
                         linewidth=0, facecolor=fc, zorder=2)
    ax.add_patch(box)
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", color=tc,
            fontsize=fs, fontweight="bold" if bold else "normal", zorder=3, wrap=True)
    return (x + w / 2, y, x + w / 2, y + h)  # bottom-center, top-center anchors


def _arrow(ax, p1, p2, color=GREY, style="-|>"):
    ax.add_patch(FancyArrowPatch(p1, p2, arrowstyle=style, mutation_scale=14,
                                 color=color, linewidth=1.6, zorder=1,
                                 shrinkA=2, shrinkB=2))


def architecture():
    fig, ax = plt.subplots(figsize=(11, 7.5))
    ax.set_xlim(0, 12); ax.set_ylim(0, 10); ax.axis("off")
    ax.text(6, 9.6, "GPL Decision Analytics Engine — System Architecture",
            ha="center", fontsize=14, fontweight="bold", color=NAVY)

    # layer bands
    for y, label in [(8.0, "DATA SOURCES"), (6.1, "INGESTION"), (4.4, "WAREHOUSE"),
                     (2.6, "MODELS"), (0.7, "SERVING")]:
        ax.text(0.15, y + 0.35, label, fontsize=8, color=GREY, fontweight="bold", rotation=0)

    # sources
    src = [("PropEquity\n(Excel/API)", 1.6), ("RERA portals", 4.0),
           ("MagicBricks /\n99acres", 6.3), ("News / Gov", 8.6), ("GPL CRM\n(internal)", 10.8)]
    src_anchors = []
    for t, x in src:
        a = _box(ax, x - 0.9, 8.1, 1.8, 0.9, t, BLUE, fs=8.5)
        src_anchors.append(a)

    # ingestion
    ing = _box(ax, 2.0, 6.2, 3.2, 0.95, "Scrapers (Scrapy/Playwright)\n+ API clients + Excel loaders", TEAL, fs=8.5)
    llm = _box(ax, 6.0, 6.2, 2.4, 0.95, "Pluggable LLM\n(Ollama / Claude / regex)", TEAL, fs=8.5)
    air = _box(ax, 9.0, 6.2, 2.4, 0.95, "Airflow / Airbyte\n(scheduled)", GREY, fs=8.5)

    # warehouse
    wh = _box(ax, 3.0, 4.5, 6.0, 0.95,
              "Data Warehouse  (PostgreSQL / RDS  or  SQLite)", NAVY, fs=10)

    # models
    mods = ["1 Land\nValuation", "2 Product\nMix", "3 Launch\nPricing", "4 Phasing", "5 Monitoring"]
    mod_anchors = []
    for i, m in enumerate(mods):
        x = 1.2 + i * 2.15
        a = _box(ax, x, 2.7, 1.9, 0.95, m, AMBER, tc=NAVY, fs=8.5)
        mod_anchors.append(a)

    # serving
    api = _box(ax, 2.2, 0.8, 2.6, 0.95, "FastAPI\n/api/v1/*", BLUE, fs=9)
    ui = _box(ax, 5.3, 0.8, 2.6, 0.95, "Streamlit\nDashboard", BLUE, fs=9)
    al = _box(ax, 8.4, 0.8, 2.6, 0.95, "Email + WhatsApp\nAlerts", BLUE, fs=9)

    # arrows: sources -> ingestion
    for a in src_anchors[:3]:
        _arrow(ax, (a[0], a[1]), (ing[0], ing[3]))
    _arrow(ax, (src_anchors[3][0], src_anchors[3][1]), (llm[0], llm[3]))
    _arrow(ax, (src_anchors[4][0], src_anchors[4][1]), (wh[0] + 1.5, wh[3]))
    # ingestion -> warehouse
    _arrow(ax, (ing[0], ing[1]), (wh[0] - 1.0, wh[3]))
    _arrow(ax, (llm[0], llm[1]), (wh[0] + 0.5, wh[3]))
    _arrow(ax, (air[0], air[1]), (wh[0] + 1.8, wh[3]), color=AMBER)
    # warehouse -> models
    for a in mod_anchors:
        _arrow(ax, (wh[0], wh[1]), (a[0], a[3]))
    # models -> serving
    _arrow(ax, (mod_anchors[0][0], mod_anchors[0][1]), (api[0], api[3]))
    _arrow(ax, (mod_anchors[2][0], mod_anchors[2][1]), (ui[0], ui[3]))
    _arrow(ax, (mod_anchors[4][0], mod_anchors[4][1]), (al[0], al[3]))

    fig.savefig(OUT / "architecture.png", dpi=160, bbox_inches="tight")
    plt.close(fig)


def data_flow():
    fig, ax = plt.subplots(figsize=(11, 4.2))
    ax.set_xlim(0, 12); ax.set_ylim(0, 4); ax.axis("off")
    ax.text(6, 3.7, "Data Flow: Fetch & Feed → Warehouse → Decision Outputs",
            ha="center", fontsize=13, fontweight="bold", color=NAVY)

    feed = _box(ax, 0.3, 2.2, 2.4, 1.0, "FETCH (auto)\nPropEquity, RERA,\nportals, news, maps", BLUE, fs=8.5)
    feed2 = _box(ax, 0.3, 0.7, 2.4, 1.0, "FEED (GPL types in)\nparcel, costs, margin,\nCRM bookings", TEAL, fs=8.5)
    wh = _box(ax, 3.6, 1.45, 2.4, 1.1, "WAREHOUSE\nprojects · txns ·\nabsorption · POIs", NAVY, fs=9)
    proc = _box(ax, 6.9, 1.45, 2.2, 1.1, "MODELS\n+ ML price model\n+ trust score", AMBER, tc=NAVY, fs=9)
    out = _box(ax, 9.8, 1.45, 1.9, 1.1, "OUTPUTS\nprice ranges,\nmix, alerts", BLUE, fs=9)

    _arrow(ax, (feed[2], feed[3] - 0.5), (wh[0] - 1.2, wh[3] - 0.55))
    _arrow(ax, (feed2[2], feed2[3] - 0.5), (wh[0] - 1.2, wh[1] + 0.55))
    _arrow(ax, (wh[0] + 1.2, wh[1] + 0.55), (proc[0] - 1.1, proc[1] + 0.55))
    _arrow(ax, (proc[0] + 1.1, proc[1] + 0.55), (out[0] - 0.95, out[1] + 0.55))

    fig.savefig(OUT / "data_flow.png", dpi=160, bbox_inches="tight")
    plt.close(fig)


def valuation_pipeline():
    fig, ax = plt.subplots(figsize=(12.5, 4.6))
    ax.set_xlim(0, 12.4); ax.set_ylim(0, 4.4); ax.axis("off")
    ax.text(6.2, 4.1, "Land Valuation — How One Number Is Produced",
            ha="center", fontsize=13, fontweight="bold", color=NAVY)

    steps = [
        ("Parcel input\n(lat, lng, FSI,\narea, costs)", BLUE),
        ("Find comparables\n(radius + recency\n+ similarity wt.)", TEAL),
        ("Demand intensity\n+ infra score", TEAL),
        ("Residual land\nvalue (3 scenarios:\nbase/bull/bear)", AMBER),
        ("Monte Carlo\n10,000 sims →\n80/50/20% bands", AMBER),
        ("ML cross-check\n+ Trust score\n→ explainable output", NAVY),
    ]
    anchors = []
    for i, (t, c) in enumerate(steps):
        x = 0.15 + i * 2.04
        tc = NAVY if c == AMBER else "white"
        a = _box(ax, x, 1.6, 1.8, 1.3, t, c, tc=tc, fs=7.8)
        anchors.append((x, x + 1.8))
    for i in range(len(anchors) - 1):
        _arrow(ax, (anchors[i][1], 2.25), (anchors[i + 1][0], 2.25))

    fig.savefig(OUT / "valuation_pipeline.png", dpi=160, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    architecture()
    data_flow()
    valuation_pipeline()
    print(f"Diagrams written to {OUT}")
    for f in sorted(OUT.glob("*.png")):
        print("  -", f.name)
