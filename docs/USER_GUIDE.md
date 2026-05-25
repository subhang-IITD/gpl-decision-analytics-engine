# User Guide — for GPL BD, Sales Strategy & Management

This tool gives you an evidence-backed second opinion on four decisions. It does
**not** make decisions for you — it shows you the data and assumptions so you can
interrogate every number. Open the dashboard and pick a module from the sidebar.

---

## How to enter a land parcel

In **1 · Land Valuation** (sidebar):
1. Select the **micro-market** (catchment).
2. Enter **latitude / longitude** (the map picker or your survey coordinates).
   Defaults to the micro-market centre.
3. Enter **area (acres)** and **FSI** (floor-space index allowed on the plot).
4. Adjust **construction cost** and **minimum margin** if Finance's numbers
   differ from the defaults.
5. Click **Run valuation**.

Impossible inputs (FSI above 6, negative margin, zero area) are rejected with a
clear message — fix and re-run.

---

## How to interpret each output

### 1 · Land Valuation
- **Base / Bull / Bear Rs./sqft (land)** — the maximum *justifiable* land price
  per sqft of land area, and the total parcel value in ₹Cr.
  - **Base** = market as it is today.
  - **Bull** = planned infrastructure materialises, demand keeps growing (priced
    ~18 months forward).
  - **Bear** = absorption slows ~30%.
- **Monte Carlo confidence chart** — the price the market supports at 80% / 50% /
  20% confidence. Use the **80% number as your safe negotiation floor**; the gap
  to the 20% number shows your upside room.
- **Why** + expanders — the comparables, infra score, demand intensity, residual
  line items, and the assumptions/conditions behind each scenario. If you
  disagree with an assumption, change the cost inputs and re-run.
- A **sparse-data warning** means few comparables exist — treat the point
  estimate cautiously; the confidence band is deliberately wider.

### 2 · Product Mix
- **Recommended mix** table & pie — how many of each configuration to build, the
  % split, expected realisation, and revenue per config.
- **Blended Rs./sqft** and **total revenue** — the headline outcome.
- **Delta vs market** — where your recommended mix differs from what competitors
  are supplying (positive = you're leaning into an under-served, faster-selling
  type).
- Tick **Override mix** to test your own split and compare revenue.

### 3 · Launch Pricing
- **Optimal launch Rs./sqft** with projected **units/month** and **months to
  sellout**.
- **Demand curve** — each dot is a comparable project (price vs velocity); the
  line is the fitted relationship; the dashed line is the recommended price.
- **Escalation schedule** — when and how much to raise price, each step gated by
  an absorption trigger.
- **Upside vs instinct** — what extra revenue the model price captures vs a gut
  price, and the velocity trade-off.
- **Scenario test slider** — set any price and see the projected outcome.

### 4 · Inventory Phasing
- **Phase 1** — high-velocity units to launch first and set the price anchor.
- **Phase 2** — mid units, released once Phase 1 hits its velocity trigger.
- **Phase 3 (premium)** — top-floor / premium-facing / large units, **held until
  40% absorption**, then released at a 12–18% premium.
- **Cash-flow alignment** — whether each phase's revenue covers the construction
  drawdown milestone.
- **Competitor response** — type in a competitor event to get an
  accelerate/hold/adjust recommendation.

### 5 · Competitive Monitoring
- The **alert feed** lists new filings near GPL projects, ≥5% competitor price
  moves, absorption tightening/overhang, and government infrastructure news.
- Click **Run scan** to refresh. Enable delivery to get email/WhatsApp alerts.

---

## How to adjust assumptions
Every cost and threshold the model uses is visible and editable:
- Per-parcel: change construction cost / margin in the Land Valuation sidebar.
- Per-micro-market defaults (infra weights, costs): see the **Admin guide**.
- Cash-flow targets and phase triggers: set on the Pricing and Phasing pages.

If a recommendation looks wrong, open the **Why** section first — it usually
comes down to an assumption you can correct.
