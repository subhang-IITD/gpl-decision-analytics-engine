"""Trust / confidence scoring shared across modules.

Answers the user's core question: "is this number even useful?" Every module
attaches a TrustScore so the output is never a bare number with false authority.

The score blends three honest signals:
  - sample size   (how many real comparables backed the answer)
  - model fit     (cross-validated R2 where a model was fitted; None if N/A)
  - dispersion    (how spread-out the comparable prices are -- tight = trustworthy)

Output is a 0-1 score plus a plain-English band (HIGH / MEDIUM / LOW) and the
reasons, so a non-technical user can read it directly.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class TrustScore:
    score: float
    band: str
    reasons: list[str] = field(default_factory=list)
    sample_size: int = 0
    fit_r2: float | None = None
    dispersion_cv: float | None = None  # coefficient of variation of comparables


def compute_trust(sample_size: int, values: list[float] | None = None,
                  fit_r2: float | None = None, min_sample: int = 5) -> TrustScore:
    reasons: list[str] = []

    # 1) sample-size component (saturates around 30 comparables)
    size_comp = min(1.0, sample_size / 30.0)
    if sample_size < min_sample:
        reasons.append(f"Only {sample_size} comparables (< {min_sample}); treat as indicative, not precise.")
    elif sample_size < 15:
        reasons.append(f"{sample_size} comparables — moderate evidence base.")
    else:
        reasons.append(f"{sample_size} comparables — solid evidence base.")

    # 2) dispersion component: tight prices -> high confidence
    disp_comp, cv = 0.5, None
    if values and len(values) >= 2 and np.mean(values) > 0:
        cv = float(np.std(values) / np.mean(values))
        disp_comp = max(0.0, 1.0 - cv / 0.5)  # CV of 0 -> 1.0, CV of 0.5+ -> 0
        if cv > 0.35:
            reasons.append(f"Comparable prices vary widely (±{cv*100:.0f}%); the market here is heterogeneous.")
        else:
            reasons.append(f"Comparable prices are fairly consistent (±{cv*100:.0f}%).")

    # 3) fit component
    fit_comp = None
    if fit_r2 is not None:
        fit_comp = max(0.0, min(1.0, fit_r2))
        if fit_r2 < 0.3:
            reasons.append(f"Statistical fit is weak (R²={fit_r2:.2f}); price alone explains little — rely on the range, not the point.")
        elif fit_r2 < 0.6:
            reasons.append(f"Moderate statistical fit (R²={fit_r2:.2f}).")
        else:
            reasons.append(f"Strong statistical fit (R²={fit_r2:.2f}).")

    comps = [size_comp, disp_comp] + ([fit_comp] if fit_comp is not None else [])
    score = float(np.mean(comps))
    band = "HIGH" if score >= 0.66 else ("MEDIUM" if score >= 0.4 else "LOW")
    return TrustScore(score=round(score, 2), band=band, reasons=reasons,
                      sample_size=sample_size, fit_r2=fit_r2,
                      dispersion_cv=round(cv, 3) if cv is not None else None)
