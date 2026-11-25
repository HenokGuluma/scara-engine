"""Daily Idea Forge PDF: the pick of the day first, simply; details after."""
import datetime as dt
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

INK = colors.HexColor("#1F2328")
MUTED = colors.HexColor("#5B6470")
LINE = colors.HexColor("#D8DDE3")
SOFT = colors.HexColor("#F3F5F8")
VERDICT = {"Yes": ("#1F7A4D", "#E6F4EC"), "Test first": ("#9A6700", "#FFF5DB"), "No": ("#8C1D24", "#FBEAEA")}

ss = getSampleStyleSheet()
KICK = ParagraphStyle("kick", parent=ss["Normal"], fontSize=8.5, textColor=MUTED, spaceAfter=4)
TITLE = ParagraphStyle("title", parent=ss["Title"], fontName="Helvetica-Bold", fontSize=21, leading=25,
                       textColor=INK, alignment=0, spaceAfter=8)
IDEA = ParagraphStyle("idea", parent=ss["Normal"], fontSize=12.5, leading=17, textColor=INK)
H2 = ParagraphStyle("h2", parent=ss["Heading2"], fontName="Helvetica-Bold", fontSize=12.5, textColor=INK,
                    spaceBefore=11, spaceAfter=4)
BODY = ParagraphStyle("body", parent=ss["Normal"], fontSize=9.6, leading=13.2, textColor=INK)
SMALL = ParagraphStyle("small", parent=BODY, fontSize=8.2, leading=11, textColor=MUTED)
CELL = ParagraphStyle("cell", parent=BODY, fontSize=8.8, leading=11.5)


def _p(t, st=BODY):
    return Paragraph(escape(str(t or "")), st)


def _n(x):
    return "?" if x is None else f"{x:,}"


def _box(flow, bg, border=None, pad=9):
    t = Table([[flow]], colWidths=[174 * mm])
    style = [("BACKGROUND", (0, 0), (-1, -1), bg), ("LEFTPADDING", (0, 0), (-1, -1), pad),
             ("RIGHTPADDING", (0, 0), (-1, -1), pad), ("TOPPADDING", (0, 0), (-1, -1), pad),
             ("BOTTOMPADDING", (0, 0), (-1, -1), pad)]
    if border:
        style.append(("LINEBEFORE", (0, 0), (0, -1), 3, border))
    t.setStyle(TableStyle(style))
    return t


def _bullets(items, numbered=False):
    out = []
    for i, it in enumerate(items or [], 1):
        mark = f"{i}." if numbered else "•"
        out.append(Paragraph(f"<font color='#5B6470'>{mark}</font>&nbsp;&nbsp;{escape(str(it))}",
                             ParagraphStyle("b", parent=BODY, leftIndent=12, firstLineIndent=-12, spaceAfter=2)))
    return out


def _footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(MUTED)
    canvas.drawString(18 * mm, 10 * mm, "Idea Forge · ideas are AI-generated and unverified — run the cheapest test before risking money")
    canvas.drawRightString(A4[0] - 18 * mm, 10 * mm, f"Page {doc.page}")
    canvas.restoreState()


def build(path, rep, winner, stats, sample=False):
    doc = SimpleDocTemplate(path, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=15 * mm,
                            bottomMargin=16 * mm, title="Idea Forge — daily pick", author="Idea Forge")
    s = []
    s.append(Paragraph(f"IDEA FORGE · DAILY PICK · {dt.date.today():%A %d %B %Y}".upper()
                       + (" · SAMPLE" if sample else ""), KICK))
    s.append(_p(rep.get("title"), TITLE))

    # 1. The idea — first, simple, short
    s.append(_box(_p(rep.get("idea_simple"), IDEA), SOFT))
    s.append(Spacer(1, 8))

    # 2. Worth pursuing?
    v = rep.get("verdict", "Test first")
    fg, bg = VERDICT.get(v, VERDICT["Test first"])
    s.append(_box(Paragraph(f"<font color='{fg}'><b>Worth pursuing? {escape(v)}</b></font><br/>"
                            f"{escape(rep.get('worth_statement', ''))}", BODY), colors.HexColor(bg),
                  border=colors.HexColor(fg)))

    # 3. How it works / 4. Limitations
    s.append(Paragraph("How it would work", H2))
    s.extend(_bullets(rep.get("how_it_works"), numbered=True))
    s.append(Paragraph("Limitations", H2))
    s.extend(_bullets(rep.get("limitations")))

    # 5. Technical notes
    t = rep.get("technical") or {}
    rows = [
        ("Cheapest test", t.get("cheapest_test")), ("Kill it if", t.get("kill_criteria")),
        ("Start capital", t.get("start_capital")), ("Time to first result", t.get("time_to_first_result")),
        ("Tools", ", ".join(t.get("tools") or [])), ("Data sources", ", ".join(t.get("data_sources") or [])),
        ("Free resources", ", ".join(t.get("free_resources") or [])),
    ]
    tech = [Paragraph("Technical notes", H2)]
    data = [[_p(k, ParagraphStyle("k", parent=CELL, textColor=MUTED)), _p(val, CELL)] for k, val in rows if val]
    if data:
        tt = Table(data, colWidths=[38 * mm, 136 * mm])
        tt.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.3, LINE), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                                ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
        tech.append(tt)
    s.append(KeepTogether(tech))
    if rep.get("automation_plan"):
        s.append(KeepTogether([Paragraph("Automation plan", H2)] + _bullets(rep.get("automation_plan"), True)))

    # Why it won + scores + the skeptic
    panel = (winner or {}).get("panel") or {}
    att = (winner or {}).get("attention") or {}
    sc = panel.get("revised") or (winner or {}).get("quick_scores") or {}
    labels = [("plausibility", "Plausible"), ("upside", "Upside"), ("no_edge_needed", "No edge"),
              ("automatable", "Automate"), ("low_contact", "Low contact"), ("low_capital", "Low capital"),
              ("timing", "Timing"), ("durability", "Durable"), ("novelty", "Novel")]
    cells = [[_p(lbl, SMALL) for _, lbl in labels],
             [Paragraph(f"<b>{escape(str(sc.get(k, '—')))}</b>/10", CELL) for k, _ in labels]]
    st = Table(cells, colWidths=[174 * mm / len(labels)] * len(labels))
    st.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), SOFT), ("INNERGRID", (0, 0), (-1, -1), 2, colors.white),
                            ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
    why = [Paragraph("Why it won today", H2), st, Spacer(1, 4)]
    extra = []
    if winner and winner.get("matches"):
        extra.append(f"Won {winner['wins']} of {winner['matches']} head-to-head matches.")
    if att:
        extra.append(f"Public attention check (“{att.get('query')}”): "
                     f"{_n(att.get('hn_stories'))} Hacker News stories, {_n(att.get('github_repos'))} GitHub repos "
                     f"(more = more people already know).")
    if winner:
        extra.append(f"Found by the {winner.get('persona', '?')} agent using the “{winner.get('op', '?')}” approach.")
    why.append(_p(" ".join(extra), SMALL))
    if panel.get("skeptic"):
        why.append(Spacer(1, 4))
        why.append(Paragraph(f"<b>The skeptic's view:</b> {escape(panel['skeptic'])}", BODY))
    s.append(KeepTogether(why))

    # Worthy mentions
    if rep.get("mentions"):
        block = [Paragraph("Worthy mentions", H2)]
        for i, m in enumerate(rep["mentions"], 1):
            fg = VERDICT.get(m.get("verdict"), ("#5B6470", ""))[0]
            block.append(Paragraph(
                f"<b>{i}. {escape(m['name'])}</b> <font size=7.5 color='{fg}'>[{escape(m.get('verdict', ''))}]</font>"
                f" — {escape(m.get('sentence') or '')}",
                ParagraphStyle("m", parent=BODY, spaceAfter=3)))
        s.append(KeepTogether(block[:3]))
        s.extend(block[3:])

    # Run stats
    ops = ", ".join(f"{k} ×{v}" for k, v in sorted((stats.get("ops") or {}).items(), key=lambda x: -x[1]))
    s.append(Spacer(1, 8))
    s.append(_p(f"Today's run: {stats.get('generated', 0)} approaches generated → {stats.get('after_filters', 0)} "
                f"passed hard limits → {stats.get('unique', 0)} new (not seen in recent days) → "
                f"{stats.get('screened', 0)} screened → {stats.get('deep', 0)} panel-reviewed → "
                f"{stats.get('tournament', 0)} in the head-to-head final. Generation calls: {ops or '—'}. "
                f"Fresh headlines used: {stats.get('signals', 0)}. LLM calls: {stats.get('llm_calls', 0)}.", SMALL))
    doc.build(s, onFirstPage=_footer, onLaterPages=_footer)
