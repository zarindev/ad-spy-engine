"""Side-by-side comparison of 2–3 competitors."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.analysis.insights import ads_for, brand_summary, highlights, opportunities_from_data, public
from app.api.serializers import ad_out, asset_url
from app.db.models import Competitor
from app.db.session import session_scope

router = APIRouter(prefix="/api/compare", tags=["compare"])

MAX_BRANDS = 3


@router.get("")
def compare(
    ids: str = Query(..., description="Comma-separated competitor IDs (2–3)"),
    own_only: bool = Query(True, description="Only ads from the brand's own pages"),
) -> dict:
    try:
        wanted = list(dict.fromkeys(int(x) for x in ids.split(",") if x.strip()))
    except ValueError as exc:
        raise HTTPException(422, "ids must be comma-separated integers") from exc
    if not 1 <= len(wanted) <= MAX_BRANDS:
        raise HTTPException(422, f"Pick between 1 and {MAX_BRANDS} competitors")

    brands = []
    with session_scope() as session:
        for cid in wanted:
            comp = session.get(Competitor, cid)
            if comp is None:
                raise HTTPException(404, f"Competitor {cid} not found")
            ads, excluded = ads_for(session, comp, own_only=own_only)
            brands.append(brand_summary(session, comp, ads, excluded=excluded))

    out = []
    for b in brands:
        group = b["_biggest_group"]
        out.append(
            {
                **public(b),
                "logo": asset_url(b["logo"]),
                "top_ads": [ad_out(a) for a in b["_ads"][:4]],
                "largest_group_lead": ad_out(max(group, key=lambda a: a.score)) if group else None,
            }
        )
    return {
        "brands": out,
        "highlights": highlights(brands),
        "opportunities": opportunities_from_data(brands),
    }
