"""Concept 6: PDF reporting.

`build_digest_data` gathers the market pulse, the AI commentary and the user's
watchlist. `render_pdf` writes an HTML page and asks a headless browser to print
it. The file is stored on disk; the API only ever hands out its id and a link.
"""

import datetime
import html
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import yfinance as yf

from app.config import REPORTS_DIR
from app.db import connect
from app.market import fetch_quotes

_CHROME = [
    os.environ.get("CHROME_BIN"),
    shutil.which("chrome"),
    shutil.which("google-chrome"),
    shutil.which("chromium"),
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
]


def _chrome_bin() -> str:
    for c in _CHROME:
        if c and Path(c).exists():
            return c
    raise RuntimeError("No Chrome/Chromium/Edge found. Set CHROME_BIN.")


def _watchlist_quotes(user_id: str) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT symbol, label FROM watchlist WHERE user_id = ?", (user_id,)
        ).fetchall()
    if not rows:
        return []
    out = []
    for r in rows:
        try:
            info = yf.Ticker(r["symbol"]).fast_info
            price, prev = info.last_price, info.previous_close
            change = ((price - prev) / prev * 100) if prev else 0.0
        except Exception:
            price, change = None, None
        out.append({"label": r["label"], "price": price, "change_percent": change})
    return out


def build_digest_data(user_id: str, insight) -> dict:
    quotes, _ = fetch_quotes()
    return {
        "generated": datetime.date.today().isoformat(),
        "pulse": [
            {
                "name": q["name"],
                "price": q["price"],
                "change_percent": q["change_percent"],
            }
            for q in quotes
        ],
        "insight": [{"title": i.title, "text": i.text} for i in insight.items],
        "watchlist": _watchlist_quotes(user_id),
    }


_STYLE = """
@page { size: A4; margin: 18mm 16mm; }
* { font-family: 'Segoe UI', Arial, sans-serif; color: #1a1a1a; }
h1 { font-size: 22px; margin: 0 0 2px; }
.date { color: #666; margin-bottom: 22px; }
h2 { font-size: 15px; margin: 22px 0 8px; border-bottom: 2px solid #333; padding-bottom: 3px; }
table { border-collapse: collapse; width: 100%; font-size: 12px; }
thead { display: table-header-group; }
tr { break-inside: avoid; }
th, td { border: 1px solid #ccc; padding: 5px 9px; text-align: left; }
th { background: #f0f0f0; }
td.num { text-align: right; }
.up { color: #0a7a2f; } .down { color: #b91c1c; }
.insight { margin: 10px 0; }
.insight b { display: block; }
"""


def _pct(v):
    if v is None:
        return "<td class='num'>n/a</td>"
    cls = "up" if v >= 0 else "down"
    return f"<td class='num {cls}'>{v:+.2f}%</td>"


def build_html(data: dict) -> str:
    pulse_rows = "".join(
        f"<tr><td>{html.escape(p['name'])}</td>"
        f"<td class='num'>{p['price']:,.2f}</td>{_pct(p['change_percent'])}</tr>"
        for p in data["pulse"]
    )
    insight_html = "".join(
        f"<div class='insight'><b>{html.escape(i['title'])}</b>"
        f"{html.escape(i['text'])}</div>"
        for i in data["insight"]
    )
    if data["watchlist"]:
        wl_rows = "".join(
            f"<tr><td>{html.escape(w['label'])}</td>"
            f"<td class='num'>{w['price']:,.2f}</td>{_pct(w['change_percent'])}</tr>"
            if w["price"] is not None
            else f"<tr><td>{html.escape(w['label'])}</td>"
            "<td class='num'>n/a</td><td class='num'>n/a</td></tr>"
            for w in data["watchlist"]
        )
        wl_section = (
            "<h2>Your watchlist</h2><table><thead><tr>"
            "<th>Ticker</th><th>Price</th><th>Change</th></tr></thead>"
            f"<tbody>{wl_rows}</tbody></table>"
        )
    else:
        wl_section = "<h2>Your watchlist</h2><p>No tickers followed yet.</p>"

    return f"""<!doctype html><html><head><meta charset="utf-8">
<style>{_STYLE}</style></head><body>
<h1>FinSight weekly digest</h1>
<div class="date">Generated {data['generated']} &middot; Indian markets</div>
<h2>Market pulse</h2>
<table><thead><tr><th>Index</th><th>Level</th><th>Change</th></tr></thead>
<tbody>{pulse_rows}</tbody></table>
<h2>What moved, and why</h2>
{insight_html}
{wl_section}
</body></html>"""


def render_pdf(html_str: str, out_path: Path) -> Path:
    out_path = out_path.resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", suffix=".html", delete=False, encoding="utf-8"
    ) as fh:
        fh.write(html_str)
        html_file = Path(fh.name)
    try:
        subprocess.run(
            [
                _chrome_bin(),
                "--headless",
                "--disable-gpu",
                "--no-pdf-header-footer",
                f"--print-to-pdf={out_path}",
                html_file.as_uri(),
            ],
            check=True,
            capture_output=True,
            timeout=60,
        )
    finally:
        html_file.unlink(missing_ok=True)
    return out_path


def generate_digest(user_id: str, insight) -> int:
    """Build the digest PDF, store it, record the row, return the report id."""
    data = build_digest_data(user_id, insight)
    now = datetime.datetime.now(datetime.timezone.utc)
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO reports (user_id, kind, path, created_at, day) "
            "VALUES (?, 'weekly-digest', '', ?, ?)",
            (user_id, now.isoformat(timespec="seconds"), now.date().isoformat()),
        )
        rid = cur.lastrowid
    pdf_path = REPORTS_DIR / f"{rid}.pdf"
    render_pdf(build_html(data), pdf_path)
    with connect() as conn:
        conn.execute("UPDATE reports SET path = ? WHERE id = ?", (str(pdf_path), rid))
    return rid
