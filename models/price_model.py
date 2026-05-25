"""Price-prediction model (brief 5.2: XGBoost for non-linear patterns).

Learns price_per_sqft as a function of interpretable features (location,
configuration, unit size, segment proxy, absorption, infrastructure score,
micro-market) from the real transactions in the warehouse. Unlike the
comparable-average (which is a local lookup), this captures non-linear
interactions across the whole dataset and is used as a cross-check on the
realisation estimate.

Honesty first: the model reports cross-validated R2 and MAE so the user knows
how trustworthy a prediction is. If too few rows exist, it declines to predict
and says so. XGBoost is used when installed; otherwise scikit-learn's
GradientBoostingRegressor (same family, pure-Python wheels) is the fallback so
the engine always runs.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import cross_val_predict
from sqlalchemy import select

from db.schema import Project, ReraTransaction
from db.session import get_session
from models.market_data import infrastructure_score

MIN_ROWS_TO_TRAIN = 40
CONFIG_ORDINAL = {"1BHK": 1, "2BHK": 2, "3BHK": 3, "3.5BHK": 3.5, "4BHK": 4, "PLOT": 0}


def _try_xgb():
    try:
        from xgboost import XGBRegressor

        return XGBRegressor(
            n_estimators=300, max_depth=4, learning_rate=0.05,
            subsample=0.9, colsample_bytree=0.9, random_state=42, n_jobs=2,
        )
    except Exception:
        from sklearn.ensemble import GradientBoostingRegressor

        return GradientBoostingRegressor(
            n_estimators=300, max_depth=3, learning_rate=0.05, subsample=0.9, random_state=42,
        )


@dataclass
class PriceModelResult:
    backend: str
    n_rows: int
    cv_r2: float | None
    cv_mae: float | None
    feature_importance: dict
    trained: bool
    note: str = ""
    _model: object = field(default=None, repr=False)
    _feature_cols: list = field(default_factory=list, repr=False)
    _mm_map: dict = field(default_factory=dict, repr=False)

    def predict(self, lat: float, lng: float, config_type: str, unit_sqft: float,
                absorption_pct: float, micro_market_id: int | None) -> float | None:
        if not self.trained:
            return None
        infra = infrastructure_score(lat, lng).score
        row = {
            "lat": lat, "lng": lng,
            "config_ord": CONFIG_ORDINAL.get(config_type, 3),
            "unit_sqft": unit_sqft,
            "absorption_pct": absorption_pct,
            "infra_score": infra,
            "mm_code": self._mm_map.get(micro_market_id, -1),
        }
        X = pd.DataFrame([row])[self._feature_cols]
        return float(self._model.predict(X)[0])


def _build_dataset() -> pd.DataFrame:
    with get_session() as s:
        txns = s.execute(select(ReraTransaction)).scalars().all()
        projects = {p.id: p for p in s.execute(select(Project)).scalars().all()}
        rows = []
        for t in txns:
            if not t.price_per_sqft or t.price_per_sqft < 500:
                continue
            p = projects.get(t.project_id)
            if not p:
                continue
            rows.append({
                "price_per_sqft": t.price_per_sqft,
                "lat": p.lat, "lng": p.lng,
                "config_ord": CONFIG_ORDINAL.get(t.config_type, 3),
                "unit_sqft": t.carpet_sqft or 1200,
                "absorption_pct": (p.pct_sold or 0.0),
                "mm_id": p.micro_market_id or -1,
            })
    return pd.DataFrame(rows)


_CACHE: dict = {"result": None}


def get_price_model(force_retrain: bool = False) -> PriceModelResult:
    """Cached accessor -- trains once per process. Call with force_retrain=True
    (or after ingesting new data) to rebuild."""
    if force_retrain or _CACHE["result"] is None:
        _CACHE["result"] = train_price_model()
    return _CACHE["result"]


def train_price_model() -> PriceModelResult:
    df = _build_dataset()
    if len(df) < MIN_ROWS_TO_TRAIN:
        return PriceModelResult(backend="none", n_rows=len(df), cv_r2=None, cv_mae=None,
                                feature_importance={}, trained=False,
                                note=f"Only {len(df)} rows; need >= {MIN_ROWS_TO_TRAIN} to train. "
                                     "Ingest more data for this market.")
    # add infra score per unique location (cached by rounding)
    locs = df[["lat", "lng"]].round(3).drop_duplicates()
    infra_cache = {(r.lat, r.lng): infrastructure_score(r.lat, r.lng).score for r in locs.itertuples()}
    df["infra_score"] = [infra_cache.get((round(la, 3), round(lo, 3)), 0.0)
                         for la, lo in zip(df["lat"], df["lng"])]

    # encode micro-market as a small integer code
    mm_codes = {mm: i for i, mm in enumerate(sorted(df["mm_id"].unique()))}
    df["mm_code"] = df["mm_id"].map(mm_codes)

    feature_cols = ["lat", "lng", "config_ord", "unit_sqft", "absorption_pct", "infra_score", "mm_code"]
    X, y = df[feature_cols], df["price_per_sqft"]

    model = _try_xgb()
    backend = "xgboost" if model.__class__.__name__ == "XGBRegressor" else "sklearn_gbr"

    # honest, cross-validated performance (5-fold)
    n_splits = min(5, max(2, len(df) // 20))
    cv_pred = cross_val_predict(model, X, y, cv=n_splits)
    cv_r2 = float(r2_score(y, cv_pred))
    cv_mae = float(mean_absolute_error(y, cv_pred))

    model.fit(X, y)
    importances = getattr(model, "feature_importances_", None)
    fi = {c: round(float(v), 3) for c, v in zip(feature_cols, importances)} if importances is not None else {}

    return PriceModelResult(
        backend=backend, n_rows=len(df), cv_r2=round(cv_r2, 3), cv_mae=round(cv_mae, 0),
        feature_importance=fi, trained=True,
        note=f"{backend} trained on {len(df)} transactions, {n_splits}-fold CV.",
        _model=model, _feature_cols=feature_cols, _mm_map=mm_codes,
    )
