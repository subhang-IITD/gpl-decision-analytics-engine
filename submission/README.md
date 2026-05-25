# GPL Decision Analytics Engine — Final Submission

This folder contains the documentation deliverables for the GPL Decision
Analytics Engine. The full source code is in the project's private Git
repository.

## Contents

| Item | Description |
|---|---|
| `GPL_Decision_Analytics_Engine.tex` | Main documentation (LaTeX). Compile on Overleaf or with `tectonic` → PDF. |
| `GPL_Decision_Analytics_Engine.pdf` | Compiled PDF (if present). |
| `diagrams/` | Architecture, data-flow and valuation-pipeline figures (PNG) + Mermaid source. |
| `markdown_docs/` | The same documentation as individual Markdown files. |

## The four mandatory handover deliverables (brief §6.1)

| Required deliverable | Where |
|---|---|
| Architecture diagram | `diagrams/architecture.png`; LaTeX §2; `markdown_docs/ARCHITECTURE.md` |
| Data dictionary | LaTeX §3; `markdown_docs/DATA_DICTIONARY.md` |
| Model logic (per sub-module) | LaTeX §4; `markdown_docs/MODEL_LOGIC.md` |
| API documentation | LaTeX §5; `markdown_docs/API.md` (live OpenAPI at `/docs`) |
| Deployment guide | LaTeX §6; `markdown_docs/DEPLOYMENT.md` |
| User guide | LaTeX §7; `markdown_docs/USER_GUIDE.md` |
| Admin guide | LaTeX §8; `markdown_docs/ADMIN_GUIDE.md` |

`markdown_docs/EXPLAINED_SIMPLY.md` is a plain-English overview of the whole
project. `markdown_docs/STREAMLIT_DEPLOY.md` covers the live demo deployment.

## Compiling the PDF

```bash
# Option A — Overleaf: upload the .tex and the diagrams/ folder, compile.
# Option B — local:
tectonic GPL_Decision_Analytics_Engine.tex
```
