# Data Dictionary

Every field stored in the warehouse, its source, refresh frequency, and use in
the model. Tables are defined in `db/schema.py`. Source categories follow brief
§3.1 (Fetch) and §3.2 (Feed).

## Refresh schedule (brief §3.1)

| Source | Method | Frequency | Pipeline |
|---|---|---|---|
| RERA portals (KA/MH/UP/TN) | API where available, else scraper | Weekly | `rera_weekly` |
| PropEquity | REST API / Excel import | Weekly | `propequity_weekly` |
| MagicBricks / 99acres / NoBroker | Playwright scraper | Daily | `portals_daily` |
| Google Maps Distance Matrix | API (on-demand) | Per parcel eval | inline |
| Naukri / LinkedIn jobs | scraper | Monthly | `jobs_monthly` |
| Gov gazette / BMRCL / NHAI | scraper + LLM | Weekly | `news_gov_daily` |
| News RSS (ET Realty, Housing) | feedparser + LLM | Daily | `news_gov_daily` |

---

## Tables

### `micro_markets` — reference
| Field | Type | Source | Use |
|---|---|---|---|
| id | int PK | system | join key |
| name | str | PropEquity / config | micro-market label |
| city | str | PropEquity | grouping |
| center_lat / center_lng | float | geocode table | distance calcs, nearest-market |
| rera_state | str | derived from city | which RERA portal to scrape |

### `micro_market_configs` — configurable weights (§4.1, §3.2)
| Field | Type | Source | Use |
|---|---|---|---|
| infra_weights | JSON | Strategy (Feed) | per-market infra-score weights (metro/IT-park/highway/school/hospital) |
| cost_assumptions | JSON | Finance (Feed) | construction/finance/approvals/marketing/duration/saleable ratio |
| min_margin_pct_of_gdv | float | Finance (Feed) | residual-value margin floor |

### `projects` — Fetch (RERA / PropEquity)
| Field | Type | Source | Use |
|---|---|---|---|
| rera_id | str | RERA | dedupe, new-filing alert |
| name, developer | str | PropEquity/RERA | identification, GPL flag |
| is_gpl | bool | derived (developer contains "Godrej") | monitoring proximity base |
| lat / lng | float | geocode | comparables, proximity, monitoring |
| launch_date | date | PropEquity | recency, new-filing window |
| status | enum | PropEquity | stalled→overhang signal |
| total_units / units_sold | int | PropEquity | absorption %, tightening signal |
| source | str | system | provenance (rera/propequity) |

### `rera_transactions` — Fetch (RERA / PropEquity)
| Field | Type | Source | Use |
|---|---|---|---|
| config_type | str | PropEquity bedroom range | comparable selection, mix demand |
| carpet_sqft | float | PropEquity unit size | unit sizing, revenue |
| price_per_sqft | float | PropEquity BSP | **core** — weighted-avg realisation, demand curve |
| price_total | float | derived | revenue |
| floor, facing | int/str | RERA where present | saleability scoring |
| txn_date | date | PropEquity quarter | recency weighting |
| lat / lng | float | project | radius filter |

### `listings` — Fetch (portals)
| Field | Type | Source | Use |
|---|---|---|---|
| portal | str | scraper | provenance |
| listed_price_per_sqft | float | scraper | price-change >5% alert |
| available_units | int | scraper | inventory overhang |
| scraped_at | datetime | system | change detection |

### `absorption_snapshots` — Fetch (PropEquity quarterly)
| Field | Type | Source | Use |
|---|---|---|---|
| as_of | date | PropEquity quarter | time series |
| units_sold_cumulative | int | PropEquity | absorption % |
| units_sold_in_month | int | derived (quarter/3) | **demand curve velocity**, intensity |
| avg_price_per_sqft | float | PropEquity price trend | demand-curve price axis |

### `points_of_interest` — Fetch (Google Maps / gov)
| Field | Type | Source | Use |
|---|---|---|---|
| category | str | curated | infra-score category |
| lat / lng | float | Maps | proximity distance |
| planned | bool | gov announcements | bull-case infra scenario |

### `job_signals` — Fetch (Naukri/LinkedIn)
| Field | Type | Source | Use |
|---|---|---|---|
| active_postings | int | scraper | demand-intensity job-growth component |
| as_of | date | system | trend slope |

### `news_items`, `gov_announcements` — Fetch + LLM
| Field | Type | Source | Use |
|---|---|---|---|
| title, url | str | RSS / scraper | reference |
| relevance | str | **LLM** | filter to decision-relevant |
| category | str | **LLM** | infra type (metro/SEZ/IT-park/road) |
| extracted_signal | text | **LLM** | monitoring alert body |

### `land_parcels` — Feed (BD §3.2)
| Field | Type | Source | Use |
|---|---|---|---|
| lat/lng, area_acres, fsi | float | BD form | valuation/mix inputs |
| current_land_use, title_status | str | BD form | context |
| bd_notes | text | BD free text | LLM-parsed risk/interest signals |
| bd_notes_signals | JSON | **LLM** | structured BD signals |
| cost_assumptions | JSON | Finance | parcel-specific overrides |

### `historical_sales` — Feed (CSV / Salesforce §3.2)
| Field | Type | Source | Use |
|---|---|---|---|
| planned_units / sold_units | int | SFDC/CSV | GPL absorption benchmark |
| launch_price_per_sqft / realised_price_per_sqft | float | SFDC/CSV | realisation vs launch delta |
| months_to_50pct | float | SFDC/CSV | velocity prior |

> **Security:** `historical_sales`, `cost_assumptions`, and `min_margin` are
> GPL-internal and are **never** sent to any external LLM (brief §5.1).

### `drawdown_schedules` — Feed (Projects §3.2)
| Field | Type | Source | Use |
|---|---|---|---|
| month_index, amount_inr | int/float | Projects form | phasing cash-flow alignment |

### `alerts`, `pipeline_runs` — system outputs
| Field | Type | Use |
|---|---|---|
| alerts.kind/severity/message/payload | — | monitoring feed, delivery log |
| pipeline_runs.pipeline/status/records/detail | — | admin health monitoring (§5.3) |
