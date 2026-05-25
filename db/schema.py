"""Warehouse schema -- every entity the engine fetches or is fed.

This is the single source of truth behind the data dictionary in
docs/DATA_DICTIONARY.md. Each table maps to a Section-3 data source or a
Section-2 model artefact. Source/refresh metadata lives in the data dictionary;
here we keep the columns and relationships.
"""
from __future__ import annotations

import datetime as dt
import enum

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.session import Base


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


# --------------------------------------------------------------------------- #
# Reference / configuration
# --------------------------------------------------------------------------- #
class MicroMarket(Base):
    """A named catchment (e.g. 'Whitefield, Bengaluru')."""

    __tablename__ = "micro_markets"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    city: Mapped[str] = mapped_column(String(80), index=True)
    center_lat: Mapped[float] = mapped_column(Float)
    center_lng: Mapped[float] = mapped_column(Float)
    rera_state: Mapped[str] = mapped_column(String(40))  # which RERA portal
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_utcnow)

    config: Mapped["MicroMarketConfig"] = relationship(back_populates="micro_market", uselist=False)
    projects: Mapped[list["Project"]] = relationship(back_populates="micro_market")


class MicroMarketConfig(Base):
    """Per-micro-market configurable weights & cost defaults (brief 4.1, 3.2)."""

    __tablename__ = "micro_market_configs"

    id: Mapped[int] = mapped_column(primary_key=True)
    micro_market_id: Mapped[int] = mapped_column(ForeignKey("micro_markets.id"), unique=True)
    infra_weights: Mapped[dict] = mapped_column(JSON)          # metro/it_park/highway/school/hospital
    cost_assumptions: Mapped[dict] = mapped_column(JSON)        # construction/finance/approvals/marketing/margin
    min_margin_pct_of_gdv: Mapped[float] = mapped_column(Float, default=0.20)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)

    micro_market: Mapped[MicroMarket] = relationship(back_populates="config")


# --------------------------------------------------------------------------- #
# FETCH sources (Section 3.1)
# --------------------------------------------------------------------------- #
class ProjectStatus(str, enum.Enum):
    launched = "launched"
    ongoing = "ongoing"
    completed = "completed"
    stalled = "stalled"


class Project(Base):
    """A residential project (GPL or competitor) from RERA/PropEquity."""

    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    rera_id: Mapped[str | None] = mapped_column(String(60), index=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    developer: Mapped[str] = mapped_column(String(160), index=True)
    is_gpl: Mapped[bool] = mapped_column(Boolean, default=False)
    micro_market_id: Mapped[int | None] = mapped_column(ForeignKey("micro_markets.id"))
    lat: Mapped[float] = mapped_column(Float)
    lng: Mapped[float] = mapped_column(Float)
    launch_date: Mapped[dt.date | None] = mapped_column(DateTime)
    status: Mapped[ProjectStatus] = mapped_column(Enum(ProjectStatus), default=ProjectStatus.launched)
    total_units: Mapped[int | None] = mapped_column(Integer)
    units_sold: Mapped[int | None] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(String(40), default="rera")  # rera|propequity
    fetched_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_utcnow)

    micro_market: Mapped["MicroMarket"] = relationship(back_populates="projects")
    transactions: Mapped[list["ReraTransaction"]] = relationship(back_populates="project")
    listings: Mapped[list["Listing"]] = relationship(back_populates="project")
    absorption: Mapped[list["AbsorptionSnapshot"]] = relationship(back_populates="project")

    @property
    def pct_sold(self) -> float | None:
        if self.total_units and self.units_sold is not None and self.total_units > 0:
            return self.units_sold / self.total_units
        return None


class ReraTransaction(Base):
    """A registered sale transaction (RERA / PropEquity, brief 3.1)."""

    __tablename__ = "rera_transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"), index=True)
    config_type: Mapped[str] = mapped_column(String(20), index=True)   # 2BHK/3BHK/...
    carpet_sqft: Mapped[float] = mapped_column(Float)
    price_total: Mapped[float] = mapped_column(Float)
    price_per_sqft: Mapped[float] = mapped_column(Float, index=True)
    floor: Mapped[int | None] = mapped_column(Integer)
    facing: Mapped[str | None] = mapped_column(String(20))
    txn_date: Mapped[dt.date] = mapped_column(DateTime, index=True)
    lat: Mapped[float] = mapped_column(Float)
    lng: Mapped[float] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(40), default="rera")

    project: Mapped["Project"] = relationship(back_populates="transactions")


class Listing(Base):
    """A live competitor listing scraped from MagicBricks/99acres/NoBroker."""

    __tablename__ = "listings"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"), index=True)
    portal: Mapped[str] = mapped_column(String(30))  # magicbricks|99acres|nobroker
    config_type: Mapped[str] = mapped_column(String(20))
    listed_price_per_sqft: Mapped[float] = mapped_column(Float)
    available_units: Mapped[int | None] = mapped_column(Integer)
    scraped_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_utcnow, index=True)

    project: Mapped["Project"] = relationship(back_populates="listings")


class AbsorptionSnapshot(Base):
    """Time-series of units-sold for a project (drives demand curve & monitoring)."""

    __tablename__ = "absorption_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    as_of: Mapped[dt.date] = mapped_column(DateTime, index=True)
    units_sold_cumulative: Mapped[int] = mapped_column(Integer)
    units_sold_in_month: Mapped[int] = mapped_column(Integer)
    avg_price_per_sqft: Mapped[float] = mapped_column(Float)

    project: Mapped["Project"] = relationship(back_populates="absorption")


class PointOfInterest(Base):
    """Infrastructure POIs for proximity scoring (Google Maps, brief 4.1)."""

    __tablename__ = "points_of_interest"

    id: Mapped[int] = mapped_column(primary_key=True)
    category: Mapped[str] = mapped_column(String(30), index=True)  # metro/it_park/highway/school/hospital
    name: Mapped[str] = mapped_column(String(160))
    lat: Mapped[float] = mapped_column(Float)
    lng: Mapped[float] = mapped_column(Float)
    planned: Mapped[bool] = mapped_column(Boolean, default=False)  # for bull-case infra


class JobSignal(Base):
    """Monthly job-posting counts by catchment (Naukri/LinkedIn, brief 3.1)."""

    __tablename__ = "job_signals"

    id: Mapped[int] = mapped_column(primary_key=True)
    micro_market_id: Mapped[int] = mapped_column(ForeignKey("micro_markets.id"), index=True)
    as_of: Mapped[dt.date] = mapped_column(DateTime, index=True)
    active_postings: Mapped[int] = mapped_column(Integer)
    employer_category: Mapped[str | None] = mapped_column(String(60))


class NewsItem(Base):
    """RSS news, LLM-classified for relevance (brief 3.1)."""

    __tablename__ = "news_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(60))
    title: Mapped[str] = mapped_column(String(400))
    url: Mapped[str] = mapped_column(String(600))
    published_at: Mapped[dt.datetime | None] = mapped_column(DateTime)
    micro_market_id: Mapped[int | None] = mapped_column(ForeignKey("micro_markets.id"))
    relevance: Mapped[str | None] = mapped_column(String(20))  # high/medium/low
    extracted_signal: Mapped[str | None] = mapped_column(Text)
    fetched_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_utcnow)


class GovAnnouncement(Base):
    """Infrastructure announcements parsed by LLM (BMRCL/NHAI/gazette, brief 3.1)."""

    __tablename__ = "gov_announcements"

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(80))
    title: Mapped[str] = mapped_column(String(400))
    url: Mapped[str | None] = mapped_column(String(600))
    announced_at: Mapped[dt.datetime | None] = mapped_column(DateTime)
    category: Mapped[str | None] = mapped_column(String(40))  # metro/sez/it_park/road
    micro_market_id: Mapped[int | None] = mapped_column(ForeignKey("micro_markets.id"))
    extracted_signal: Mapped[str | None] = mapped_column(Text)
    fetched_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_utcnow)


# --------------------------------------------------------------------------- #
# FEED sources (Section 3.2) -- entered by GPL teams
# --------------------------------------------------------------------------- #
class LandParcel(Base):
    """A parcel under evaluation, entered by the BD team (brief 3.2)."""

    __tablename__ = "land_parcels"

    id: Mapped[int] = mapped_column(primary_key=True)
    label: Mapped[str] = mapped_column(String(160))
    lat: Mapped[float] = mapped_column(Float)
    lng: Mapped[float] = mapped_column(Float)
    area_acres: Mapped[float] = mapped_column(Float)
    fsi: Mapped[float] = mapped_column(Float)
    current_land_use: Mapped[str | None] = mapped_column(String(80))
    title_status: Mapped[str | None] = mapped_column(String(80))
    micro_market_id: Mapped[int | None] = mapped_column(ForeignKey("micro_markets.id"))
    bd_notes: Mapped[str | None] = mapped_column(Text)            # free text -> LLM parsed
    bd_notes_signals: Mapped[dict | None] = mapped_column(JSON)   # structured LLM output
    cost_assumptions: Mapped[dict | None] = mapped_column(JSON)   # parcel-specific overrides
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_utcnow)


class HistoricalSale(Base):
    """GPL's own historical project performance (CSV/Salesforce, brief 3.2)."""

    __tablename__ = "historical_sales"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_name: Mapped[str] = mapped_column(String(200))
    micro_market_id: Mapped[int | None] = mapped_column(ForeignKey("micro_markets.id"))
    config_type: Mapped[str] = mapped_column(String(20))
    planned_units: Mapped[int] = mapped_column(Integer)
    sold_units: Mapped[int] = mapped_column(Integer)
    launch_price_per_sqft: Mapped[float] = mapped_column(Float)
    realised_price_per_sqft: Mapped[float] = mapped_column(Float)
    months_to_50pct: Mapped[float | None] = mapped_column(Float)
    phase: Mapped[int | None] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(String(30), default="csv")  # csv|salesforce


class DrawdownSchedule(Base):
    """Construction cost drawdown milestones per project (brief 3.2)."""

    __tablename__ = "drawdown_schedules"

    id: Mapped[int] = mapped_column(primary_key=True)
    parcel_id: Mapped[int | None] = mapped_column(ForeignKey("land_parcels.id"), index=True)
    month_index: Mapped[int] = mapped_column(Integer)  # 0,1,2,...
    amount_inr: Mapped[float] = mapped_column(Float)


# --------------------------------------------------------------------------- #
# Model outputs / operations
# --------------------------------------------------------------------------- #
class AlertSeverity(str, enum.Enum):
    info = "info"
    warning = "warning"
    critical = "critical"


class Alert(Base):
    """Competitive-monitoring alerts (brief 2.5)."""

    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(50))  # new_filing/price_change/absorption/gov
    severity: Mapped[AlertSeverity] = mapped_column(Enum(AlertSeverity), default=AlertSeverity.info)
    micro_market_id: Mapped[int | None] = mapped_column(ForeignKey("micro_markets.id"))
    message: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict | None] = mapped_column(JSON)
    delivered: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_utcnow, index=True)


class PipelineRun(Base):
    """Ingestion pipeline run log -- powers admin health monitoring (brief 5.3)."""

    __tablename__ = "pipeline_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    pipeline: Mapped[str] = mapped_column(String(60), index=True)
    status: Mapped[str] = mapped_column(String(20))  # success|failed|partial
    records_ingested: Mapped[int] = mapped_column(Integer, default=0)
    detail: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_utcnow)
    finished_at: Mapped[dt.datetime | None] = mapped_column(DateTime)
