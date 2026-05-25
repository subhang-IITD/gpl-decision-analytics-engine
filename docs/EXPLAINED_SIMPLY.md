# What We Built — In Plain English

A simple guide to the project for the freelancer. No jargon. Read this once and
you'll understand what the tool does, what each part is, and how to talk about it.

---

## 1. What is the client asking for?

**Godrej Properties (GPL)** builds apartment projects. Before they build, they
make four big-money decisions, and right now they make them mostly on gut feel:

1. **How much to pay for a piece of land?**
2. **What mix of flats to build?** (how many 2BHK vs 3BHK vs 4BHK)
3. **What price to launch flats at, and when to raise prices?**
4. **Which flats to sell first, and which to hold back?**

They want a **software tool that looks at real market data and gives them a
data-backed answer** for each — like a smart assistant that says *"based on the
numbers, pay around ₹X for this land, build this mix, launch at this price."*

It does **not** make the final decision. A human still decides. The tool just
replaces guessing with evidence.

---

## 2. What did we build? (the 5 parts)

Think of it as **5 calculators**, all sharing one big pool of market data.

### Calculator 1 — Land Valuation
*"What's the most we should pay for this land?"*

You type in the land's location, size, and how much you're allowed to build on
it. The tool looks at what flats nearby actually sell for, subtracts all the
costs of building (construction, loan interest, approvals, marketing) and GPL's
required profit — whatever is left over is the **most you can afford to pay for
the land**.

It gives **three answers**:
- **Base** — if the market stays as it is today.
- **Bull** — the optimistic case (e.g. a new metro line gets built nearby).
- **Bear** — the pessimistic case (sales slow down).

It also runs the calculation **10,000 times** with slightly different
assumptions each time (costs a bit higher, prices a bit lower, etc.) to show a
**range** instead of one fragile number. So instead of "the land is worth
₹2,200", it says "we're 80% confident it's worth at least ₹1,481, and there's
upside to ₹2,989." That range is gold in a negotiation.

### Calculator 2 — Product Mix
*"What combination of flat types makes the most money?"*

If a plot can hold 130 flats, should they be mostly 2BHKs? Mostly 3BHKs? The
tool looks at **which flat types are selling fastest** in that area and which
are **over-built** by competitors, then works out the mix that earns the most
money while fitting the building rules. You can also type in your own mix and
compare.

### Calculator 3 — Launch Pricing
*"What price should we launch at?"*

Price too high → flats sell slowly → cash is stuck. Price too low → you leave
money on the table. The tool studies how fast similar projects sold **at
different prices** and finds the sweet spot that makes the most money while
still selling fast enough to pay the construction bills. It also suggests **when
to raise prices** (e.g. "raise 4% at month 3 if sales are good").

### Calculator 4 — Inventory Phasing
*"Which flats do we sell first?"*

Not all flats are equal — a 5th-floor flat sells faster than a top-floor premium
one. The tool scores every flat and says: **sell the easy ones first** to build
momentum and set a price anchor, then **hold the premium flats** (top floor,
best view) until the project is 40% sold — by then you can charge 12-18% more
for them.

### Calculator 5 — Competitive Monitoring
*"What's changing in the market that we should know about?"*

This one runs in the background and **raises alerts**: a competitor launched
nearby, a competitor dropped prices, a project is almost sold out, or the
government announced a new metro line. Alerts can go out by **email and
WhatsApp**.

---

## 3. Where does the data come from?

The tool is only as good as its data. There are two kinds:

- **Data we fetch automatically** — real estate websites (MagicBricks, 99acres),
  government RERA portals, a paid data service called **PropEquity**, Google Maps
  (for distances to metro/schools), news, and government announcements.
- **Data GPL types in** — the land details, their cost numbers, their past
  project sales.

**Important:** right now we are using **real PropEquity data files** the client
gave us (for Chennai and Coimbatore). We are **not using fake/made-up data**.
The other sources (websites, Google Maps, etc.) are fully wired up — they just
switch on when the client provides their passwords/keys. Until then, the tool
runs on the real PropEquity data we have.

---

## 4. The pieces of software (so you can name them)

| Piece | What it is | Why it's there |
|---|---|---|
| **Warehouse** (database) | Where all the data is stored | One tidy place for every number |
| **Ingestion** | The code that pulls in data | Loads PropEquity files, scrapes websites |
| **Models** | The 5 calculators | The actual brains |
| **API** (FastAPI) | A way for other software to ask the calculators questions | So GPL's other systems can plug in |
| **Dashboard** (Streamlit) | The screen GPL staff actually click on | The friendly front-end |
| **Airflow** | An automatic scheduler | Refreshes the data daily/weekly on its own |
| **LLM** | An AI that reads text (news, notes) | Pulls useful signals out of articles/notes |

---

## 5. A note on the "demand curve" and accuracy

In Calculator 3 we draw a **demand curve** — a line showing "higher price = fewer
sales per month." We try three shapes of curve (straight, curved, and a decay
shape) and keep whichever matches the data best.

You may notice the **fit is weak** (a stat called R² is low). This is **not a
bug** — it's the truth about the data. Real flat sales depend on dozens of things
(brand, location, amenities, timing), not just price. So price alone only
explains a small slice. A good consultant **reports this honestly** and widens
the uncertainty range, rather than pretending the number is more precise than it
is. With richer data (more projects, more history), the fit improves. This is
worth saying to the client — it builds trust.

---

## 5b. "How do I know if the price I'm getting is even useful?"

This was a key worry, so the tool now answers it directly. Every result shows a
**Confidence badge**: 🟢 HIGH / 🟡 MEDIUM / 🔴 LOW, plus the reasons in plain
English. It looks at three things:

1. **How many real sales backed the answer** (more = better).
2. **How consistent those sales were** (if nearby flats sell anywhere from
   ₹5,000 to ₹15,000/sqft, no single number is trustworthy — it'll say so).
3. **How well the maths actually fit the data** (the R² number).

So you'll never get a bare number pretending to be precise. A 🔴 LOW badge means
*"use this as a rough hint, go gather more data."* A 🟢 HIGH badge means *"you can
lean on this in a negotiation."*

**Two engines, cross-checked.** For price we run TWO independent methods:
- a **comparable average** (what similar flats nearby actually sold for), and
- a **machine-learning model** (XGBoost / gradient boosting) trained on every
  transaction, which reaches a solid **R²≈0.68** on the real data.

If both agree → high confidence. If they disagree a lot → the tool flags it so
you investigate instead of trusting a wrong number. That disagreement is a
*feature*, not a bug — it's the tool being honest.

> Note on the demand curve's low R²: that one specific chart (price vs
> sales-speed) genuinely has a weak signal because sales speed depends on far
> more than price. The tool reports that honestly and lowers the confidence
> badge rather than faking precision. The **price prediction** (the number you
> actually care about for land value) is the strong R²≈0.68 model.

## 6. What's done vs what needs the client

**Done and working now:**
- All 5 calculators, running on real PropEquity data.
- The dashboard, the API, the database, the auto-scheduler.
- Full documentation. Tests that prove the maths works.

**Needs the client to switch on (just passwords/settings, no new code):**
- Live website scraping (needs anti-blocking proxies — a small monthly cost).
- PropEquity live feed, Google Maps, Salesforce, email/WhatsApp sending.
- Deploying it on GPL's own Amazon cloud (guide is in `DEPLOYMENT.md`).
- Adding map locations for new cities (guide is in `ADMIN_GUIDE.md`).

---

## 7. How to run it yourself (to show the client)

```bash
cd gpl_engine
source .venv/bin/activate          # turn on the environment
streamlit run dashboard/app.py     # opens the dashboard at localhost:8501
```

Then click through the 5 pages in the left menu. That's the whole product.

---

## 8. One-line summary you can tell anyone

> *"It's a smart assistant for Godrej Properties that reads real housing-market
> data and tells them how much to pay for land, what flats to build, what price
> to sell at, and which to sell first — with honest confidence ranges, not
> guesses."*
