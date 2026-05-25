# START HERE — Read This First

This is a guide for **anyone**, technical or not. It explains, in plain English,
what this project is, what's in this folder, and what to do with it. Read this
one page and you'll understand the whole submission.

---

## 1. What is this project?

We built a software tool for **Godrej Properties (GPL)** — a "smart assistant"
that reads real housing-market data and helps them make four big decisions:

1. **How much to pay for a piece of land.**
2. **What mix of flats to build** (how many 2BHKs vs 3BHKs, etc.).
3. **What price to launch flats at**, and when to raise prices.
4. **Which flats to sell first**, and which to hold back for a premium.

It also **watches the market** and sends alerts when something important
happens (a competitor drops prices, a new metro line is announced, etc.).

The tool does **not** make decisions on its own. It gives GPL's team a
data-backed "second opinion" with honest confidence levels, so they stop
guessing and start deciding with evidence.

---

## 2. What is in this folder?

| File / folder | What it is | Who reads it |
|---|---|---|
| **START_HERE.md** | This file — the plain-English overview. | Everyone |
| **GPL_Decision_Analytics_Engine.tex** | The main report. Open it in [Overleaf.com](https://overleaf.com) (free) to turn it into a polished PDF. | Reviewer / GPL |
| **diagrams/** | The flow-chart pictures used in the report. | — |
| **../docs/** | The detailed documentation as separate plain-text files (see below). | Technical reader |

### What's inside the `docs/` folder (one level up, in the code repo)

| File | In one sentence |
|---|---|
| `EXPLAINED_SIMPLY.md` | The whole project explained with no jargon (read this second). |
| `ARCHITECTURE.md` | How the software is put together. |
| `DATA_DICTIONARY.md` | Every piece of data the tool stores, and where it comes from. |
| `MODEL_LOGIC.md` | The maths/logic behind each of the four calculators. |
| `API.md` | How other software can talk to the tool. |
| `DEPLOYMENT.md` | How GPL installs it on their own servers. |
| `USER_GUIDE.md` | How a GPL staff member actually uses the screens. |
| `ADMIN_GUIDE.md` | How to maintain it (add cities, fix data feeds, check health). |
| `STREAMLIT_DEPLOY.md` | How to put the live demo on the web. |
| `PROJECT_README.md` | The technical "front page" of the code. |

> **The source code itself** lives in a separate folder/repository called
> `gpl_engine`. This folder is just the documentation and diagrams.

---

## 3. How does the tool actually work? (the 30-second version)

1. **It collects real data** — actual project and price data from PropEquity
   (a property-data company), plus public websites and news.
2. **It stores everything in one organised database.**
3. **Four "calculators" do the thinking** — land price, flat mix, launch price,
   sell-order. A fifth one watches for market changes.
4. **You see the answers on a simple website** (the dashboard), with charts and
   a clear **confidence badge** (🟢 high / 🟡 medium / 🔴 low) so you know how
   much to trust each number.

There's a picture of this in `diagrams/architecture.png`.

---

## 4. Is it real, or a mock-up?

**Real.** It runs on actual market data for **Chennai, Coimbatore, and
Bengaluru** (about 1,000 real projects and 1,700+ real price records), plus
GPL's own past sales. Nothing is faked. Where data is thin, the tool honestly
says "low confidence" instead of inventing a number.

---

## 5. What do I do with this?

- **To read the report:** upload `GPL_Decision_Analytics_Engine.tex` and the
  `diagrams/` folder to [Overleaf.com](https://overleaf.com) → it makes a PDF.
  (Or just read the `markdown_docs/` files — they're the same content as plain
  text.)
- **To see the tool running:** the code folder (`gpl_engine`) has a one-command
  start; see `PROJECT_README.md`. There is also a live web demo (link provided
  separately once deployed).
- **To hand it to GPL:** give them the code repository link + this folder. The
  `DEPLOYMENT.md` tells their IT team how to install it on their own systems.

---

## 6. One honest note (worth knowing)

The tool is **strong where there's lots of data and cautious where there isn't**
— on purpose. For a ₹100-crore land decision, "we don't have enough data to be
sure" is a more valuable answer than a confident-but-wrong number. The
confidence badge on every screen reflects this. GPL specifically asked for this
honesty in their requirements.

---

*That's everything. For the simple deep-dive, read `markdown_docs/EXPLAINED_SIMPLY.md` next.*
