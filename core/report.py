"""Builds the PDF report (daily or weekly) from the state database."""
import datetime as dt
import json
import time
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer,
                                Table, TableStyle)

INK = colors.HexColor("#1F2328")
MUTED = colors.HexColor("#5B6470")
ACCENT = colors.HexColor("#2F5BD3")
LINE = colors.HexColor("#D8DDE3")
SOFT = colors.HexColor("#F3F5F8")
WARN = colors.HexColor("#B4232C")
GOOD = colors.HexColor("#1F7A4D")

STATUS_LABEL = {"verified": "Verified", "simulated": "Simulated OK", "needs_review": "Needs review",
                "disclosure_draft": "Disclosure draft"}

ss = getSampleStyleSheet()
H1 = ParagraphStyle("h1", parent=ss["Title"], fontName="Helvetica-Bold", fontSize=20, textColor=INK,
                    alignment=TA_LEFT, spaceAfter=2)
SUB = ParagraphStyle("sub", parent=ss["Normal"], fontSize=9.5, textColor=MUTED, spaceAfter=10)
H2 = ParagraphStyle("h2", parent=ss["Heading2"], fontName="Helvetica-Bold", fontSize=13.5, textColor=INK,
                    spaceBefore=12, spaceAfter=4)
BODY = ParagraphStyle("body", parent=ss["Normal"], fontSize=9.5, leading=13, textColor=INK)
SMALL = ParagraphStyle("small", parent=BODY, fontSize=8.3, leading=11, textColor=MUTED)
CELL = ParagraphStyle("cell", parent=BODY, fontSize=8.3, leading=10.5)
ITEM_T = ParagraphStyle("itemt", parent=BODY, fontName="Helvetica-Bold", fontSize=10, spaceAfter=1)


def _money(v):
    if not v:
        return "—"
    return f"${v:,.0f}" if v >= 10 else f"${v:,.2f}"


def _when(ts):
    return dt.datetime.utcfromtimestamp(ts).strftime("%d %b %H:%M UTC")


def _stat_boxes(stats):
    cells = [[Paragraph(f"<font size=18><b>{v}</b></font><br/><font color='#5B6470' size=8>{k}</font>", BODY)
              for k, v in stats]]
    t = Table(cells, colWidths=[44 * mm] * len(stats), rowHeights=[17 * mm])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), SOFT), ("BOX", (0, 0), (-1, -1), 0.5, LINE),
                           ("INNERGRID", (0, 0), (-1, -1), 3, colors.white),
                           ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 8)]))
    return t


def _footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(MUTED)
    canvas.drawString(18 * mm, 10 * mm, "SCARA Opportunity Engine · private report — do not forward PRIVATE items")
    canvas.drawRightString(A4[0] - 18 * mm, 10 * mm, f"Page {doc.page}")
    canvas.restoreState()


def build(con, plugins_meta, out_path, period="daily", sample=False):
    days = 7 if period == "weekly" else 1
    since = time.time() - days * 86400
    rows = [dict(r) for r in con.execute("SELECT * FROM candidates WHERE last_seen>=? ORDER BY score DESC", (since,))]
    new_rows = [r for r in rows if r["first_seen"] >= since]
    runs = [dict(r) for r in con.execute("SELECT * FROM runs WHERE ts>=?", (since,))]
    llm = [dict(r) for r in con.execute(
        "SELECT provider, SUM(calls) c FROM llm_usage WHERE day>=? GROUP BY provider",
        ((dt.date.today() - dt.timedelta(days=days)).isoformat(),))]
    min_top = 1.0
    top = [r for r in rows if r["score"] >= min_top][:12]
    errors = sum(1 for r in runs if r["error"])

    doc = SimpleDocTemplate(out_path, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                            topMargin=16 * mm, bottomMargin=16 * mm,
                            title=f"SCARA {period} report", author="SCARA Opportunity Engine")
    s = []
    label = "Weekly" if period == "weekly" else "Daily"
    s.append(Paragraph(f"SCARA Opportunity Report — {label}" + (" (SAMPLE DATA)" if sample else ""), H1))
    s.append(Paragraph(f"{dt.datetime.utcnow():%A %d %B %Y} · covers the last {days * 24} hours · "
                       f"{len(runs)} ground-runs completed", SUB))
    s.append(_stat_boxes([("New findings", len(new_rows)), ("Worth a look (score ≥ 1)", len(top)),
                          ("Verified / simulated", sum(1 for r in rows if r["status"] in ("verified", "simulated"))),
                          ("Run errors", errors)]))
    s.append(Spacer(1, 6))

    # ── Act on these first
    s.append(Paragraph("Act on these first", H2))
    if top:
        data = [["#", "Ground", "Finding", "Value", "Cost", "Score", "Deadline", "Status"]]
        for i, r in enumerate(top, 1):
            title = escape(r["title"])
            if r["url"]:
                title = f"<link href='{escape(r['url'])}' color='{'#B4232C' if r['private'] else '#2F5BD3'}'>{title}</link>"
            data.append([str(i), r["plugin"].upper(), Paragraph(title, CELL), _money(r["value_usd"]),
                         _money(r["cost_usd"]), f"{r['score']:,.1f}", r["deadline"] or "—",
                         STATUS_LABEL.get(r["status"], r["status"])])
        t = Table(data, colWidths=[7 * mm, 12 * mm, 66 * mm, 17 * mm, 14 * mm, 14 * mm, 20 * mm, 24 * mm],
                  repeatRows=1)
        t.setStyle(TableStyle([
            ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 8), ("FONT", (0, 1), (-1, -1), "Helvetica", 8),
            ("TEXTCOLOR", (0, 0), (-1, 0), MUTED), ("LINEBELOW", (0, 0), (-1, 0), 0.8, INK),
            ("LINEBELOW", (0, 1), (-1, -1), 0.3, LINE), ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ALIGN", (3, 0), (5, -1), "RIGHT")]))
        s.append(t)
    else:
        s.append(Paragraph("Nothing crossed the score threshold this period. That's normal — the engine "
                           "is a long-shot search; the sections below show everything it is watching.", BODY))

    # ── Per ground
    s.append(PageBreak())
    s.append(Paragraph("By hunting ground", H2))
    s.append(Paragraph("Each ground shows its newest findings (up to 6). Automatic pursuit is switched off "
                       "until you enable it; the mode shown is what the ground is allowed to do later.", SMALL))
    for meta in plugins_meta:
        g_rows = [r for r in rows if r["plugin"] == meta["key"]]
        g_runs = [r for r in runs if r["plugin"] == meta["key"]]
        head = Paragraph(f"#{meta['ground']} · {escape(meta['name'])}", H2)
        sub = Paragraph(f"{len(g_rows)} active · "
                         f"{sum(1 for r in g_rows if r['first_seen'] >= since)} new · "
                         f"{sum(r['seconds'] for r in g_runs) / 60:.0f} min scanned · "
                        f"pursuit: {escape(meta['pursuit'])}", SMALL)
        block = [head, sub, Spacer(1, 3)]
        if not g_rows:
            block.append(Paragraph("No findings this period.", SMALL))
        for r in sorted(g_rows, key=lambda x: -x["first_seen"])[:6]:
            t = escape(r["title"])
            if r["url"]:
                t = f"<link href='{escape(r['url'])}' color='#2F5BD3'>{t}</link>"
            colr = WARN if r["private"] else INK
            block.append(Paragraph(t, ParagraphStyle("x", parent=ITEM_T, textColor=colr)))
            block.append(Paragraph(escape(r["summary"]), BODY))
            block.append(Paragraph(
                f"Value {_money(r['value_usd'])} · cost {_money(r['cost_usd'])} · score {r['score']:,.1f} · "
                f"claimability {r['claimability']:.0%} · awareness {r['awareness']:.0%} · "
                f"{STATUS_LABEL.get(r['status'], r['status'])} · first seen {_when(r['first_seen'])}", SMALL))
            if r["private"]:
                draft = (json.loads(r["data"] or "{}") or {}).get("draft")
                if draft:
                    block.append(Paragraph("<b>Disclosure draft:</b> " + escape(draft[:1200]), SMALL))
            block.append(Spacer(1, 5))
        s.append(KeepTogether(block[:6]))
        s.extend(block[6:])

    # ── System health
    s.append(Paragraph("System health", H2))
    hdata = [["Ground", "Runs", "Minutes", "Items checked", "Hits", "Last problem"]]
    for meta in plugins_meta:
        g = [r for r in runs if r["plugin"] == meta["key"]]
        last_err = next((r["error"] for r in reversed(g) if r["error"]), "")
        hdata.append([f"#{meta['ground']} {meta['name']}", str(len(g)), f"{sum(r['seconds'] for r in g) / 60:.0f}",
                      str(sum(r["items"] for r in g)), str(sum(r["hits"] for r in g)),
                      Paragraph(escape(last_err[:160]) or "—", CELL)])
    ht = Table(hdata, colWidths=[52 * mm, 12 * mm, 16 * mm, 22 * mm, 12 * mm, 60 * mm])
    ht.setStyle(TableStyle([("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 8), ("FONT", (0, 1), (-1, -1), "Helvetica", 8),
                            ("TEXTCOLOR", (0, 0), (-1, 0), MUTED), ("LINEBELOW", (0, 0), (-1, 0), 0.8, INK),
                            ("LINEBELOW", (0, 1), (-1, -1), 0.3, LINE), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    s.append(ht)
    s.append(Spacer(1, 4))
    s.append(Paragraph("LLM calls: " + (", ".join(f"{r['provider']} {r['c']}" for r in llm) or "none"), SMALL))

    s.append(Paragraph("How to read the numbers", H2))
    for line in [
        "<b>Value</b> — estimated claimable value in USD (rough; verify before acting).",
        "<b>Score</b> — value after cost × claimability ÷ (others claiming + 1), boosted when few people seem aware.",
        "<b>Claimability</b> — how sure the engine is that you are allowed and able to claim it.",
        "<b>Awareness</b> — 0% means nobody seems to know; 100% means widely known.",
        "<b>Simulated OK</b> — the claim succeeded in a free simulation; <b>Verified</b> — confirmed from source data.",
        "<b style='color:#B4232C'>PRIVATE</b> items are possible bugs: disclose to the project only. Never interact.",
    ]:
        s.append(Paragraph(line, SMALL))
    doc.build(s, onFirstPage=_footer, onLaterPages=_footer)
    return {"new": len(new_rows), "top": len(top), "errors": errors}
