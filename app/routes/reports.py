"""Report routes. Auth. Generate a digest, look it up, download the file.

The PDF is stored on disk and served by link (`FileResponse`); the JSON
endpoints only carry the report's id and link, never its bytes.
"""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import FileResponse

import datetime

from app.cache import cache
from app.db import connect
from app.insight import STUB as INSIGHT_STUB
from app.reports import generate_digest
from app.security import current_user

router = APIRouter(prefix="/reports", tags=["reports"])


def _link(rid: int) -> str:
    return f"/reports/{rid}/file"


@router.post("/weekly-digest")
def create_weekly_digest(response: Response, user_id: str = Depends(current_user)):
    """Render this week's digest PDF. Reuses today's if one exists (idempotent
    per day); pass nothing to force is not supported here on purpose - the
    scheduled job is the source of truth, this endpoint is the on-demand copy."""
    with connect() as conn:
        row = conn.execute(
            "SELECT id, day FROM reports WHERE user_id = ? AND kind = 'weekly-digest' "
            "ORDER BY id DESC LIMIT 1",
            (user_id,),
        ).fetchone()
    if row and row["day"] == datetime.date.today().isoformat():
        response.status_code = 200
        return {"id": row["id"], "file": _link(row["id"]), "reused": True}

    insight = cache.get("market:insight") or INSIGHT_STUB
    rid = generate_digest(user_id, insight)
    response.status_code = 201
    return {"id": rid, "file": _link(rid), "reused": False}


@router.get("/{report_id}")
def get_report(report_id: int, user_id: str = Depends(current_user)):
    with connect() as conn:
        row = conn.execute(
            "SELECT id, kind, created_at FROM reports WHERE id = ? AND user_id = ?",
            (report_id, user_id),
        ).fetchone()
    if row is None:
        raise HTTPException(404, detail="Report not found")
    return {**dict(row), "file": _link(row["id"])}


@router.get("/{report_id}/file")
def get_report_file(report_id: int, user_id: str = Depends(current_user)):
    with connect() as conn:
        row = conn.execute(
            "SELECT path FROM reports WHERE id = ? AND user_id = ?",
            (report_id, user_id),
        ).fetchone()
    if row is None or not row["path"] or not Path(row["path"]).exists():
        raise HTTPException(404, detail="Report file not found")
    return FileResponse(
        row["path"],
        media_type="application/pdf",
        filename=f"finsight-digest-{report_id}.pdf",
    )
