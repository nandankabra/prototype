"""Build an evidence-based project change history from the local Git commits."""

from __future__ import annotations

import subprocess
from collections import Counter
from datetime import date
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    BaseDocTemplate, Frame, KeepTogether, PageBreak, PageTemplate, Paragraph,
    Spacer, Table, TableStyle,
)


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "output/pdf/project_change_history_2026-09-17.pdf"
OUT.parent.mkdir(parents=True, exist_ok=True)


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def paths(old: str, new: str) -> list[tuple[str, str]]:
    result = []
    for line in git("diff", "--name-status", old, new).splitlines():
        status, path = line.split("\t", 1)
        result.append((status, path))
    return result


first = "b9ca40e"
prototype = "f6161b8"
latest = "b97ff9c"
phase_one = paths(first, prototype)
phase_two = paths(prototype, latest)
overall = paths(first, latest)
assert len(phase_one) == 182 and len(phase_two) == 121 and len(overall) == 275
assert Counter(s for s, _ in phase_two) == Counter({"A": 93, "M": 28})

navy = colors.HexColor("#142640")
teal = colors.HexColor("#0D8B8D")
muted = colors.HexColor("#546477")
line = colors.HexColor("#DCE4EA")
wash = colors.HexColor("#F2F7F8")
styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name="ReportTitle", fontName="Helvetica-Bold", fontSize=23, leading=28, textColor=navy, spaceAfter=10))
styles.add(ParagraphStyle(name="Deck", fontName="Helvetica", fontSize=10.5, leading=15, textColor=muted, spaceAfter=17))
styles.add(ParagraphStyle(name="SectionX", fontName="Helvetica-Bold", fontSize=13, leading=17, textColor=navy, spaceBefore=17, spaceAfter=8, keepWithNext=True))
styles.add(ParagraphStyle(name="SubX", fontName="Helvetica-Bold", fontSize=10, leading=14, textColor=teal, spaceBefore=9, spaceAfter=5, keepWithNext=True))
styles.add(ParagraphStyle(name="BodyX", fontName="Helvetica", fontSize=9, leading=13, textColor=navy, spaceAfter=6))
styles.add(ParagraphStyle(name="SmallX", fontName="Helvetica", fontSize=8, leading=11.3, textColor=muted, spaceAfter=5))
styles.add(ParagraphStyle(name="ListX", fontName="Helvetica", fontSize=9, leading=13, textColor=navy, leftIndent=13, firstLineIndent=-11, spaceAfter=5))
styles.add(ParagraphStyle(name="FileX", fontName="Courier", fontSize=7.15, leading=10, textColor=navy, splitLongWords=True, spaceAfter=0))
styles.add(ParagraphStyle(name="FileStatus", fontName="Helvetica-Bold", fontSize=7, leading=10, textColor=teal))


def p(text: str, style: str = "BodyX") -> Paragraph:
    return Paragraph(text, styles[style])


def bullet(text: str) -> Paragraph:
    return p("<font color='#0D8B8D'>-</font> " + text, "ListX")


def section(title: str) -> Paragraph:
    return p(title, "SectionX")


story = [
    p("Project change history", "ReportTitle"),
    p("ByteCode Verify | From the first repository commit to 17 September 2026", "Deck"),
]

summary_rows = [
    ["Baseline", "15 Sep 2026 - b9ca40e - README.md only"],
    ["Prototype", "15 Sep 2026 - f6161b8 - 182 files added"],
    ["Update", "17 Sep 2026 - b97ff9c - 93 files added, 28 modified"],
    ["Current scope", "275 tracked files added after baseline; clean working tree at review"],
]
table = Table([[p(escape(a), "SmallX"), p(escape(b), "SmallX")] for a, b in summary_rows], colWidths=[91, 406])
table.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, -1), wash),
    ("BOX", (0, 0), (-1, -1), .6, line),
    ("INNERGRID", (0, 0), (-1, -1), .35, line),
    ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ("LEFTPADDING", (0, 0), (-1, -1), 9),
    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ("TOPPADDING", (0, 0), (-1, -1), 7),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
]))
story.extend([table, Spacer(1, 10)])
story.append(p("Scope and interpretation", "SectionX"))
story.append(p("The first commit contains only a README that describes an intended, already working prototype. Git does not contain its implementation at that point. This report therefore uses the first commit as the recorded baseline and attributes source files to the two later commits. Descriptions below reflect the committed code; they do not imply every feature was independently tested today."))

story.append(section("1. Prototype implementation | 15 September"))
prototype_groups = [
    ("Application and user workflow", [
        "Created the React/TypeScript interface with login, dashboard, tender and bid views, document inspection, verification, risk, AI recommendation, audit trail, rule editor, and demo pages.",
        "Added officer, auditor, and administrator roles; bid processing, decision capture with a reason, and evidence-oriented review panels.",
    ]),
    ("Backend and data", [
        "Built the FastAPI service, SQLAlchemy models and initial Alembic schema for tenders, bidders, bids, documents, evidence, processing runs, scores, decisions, and audit events.",
        "Implemented document upload/storage, PDF text extraction with OCR fallback, classification, identifier extraction, source comparison, tender rules, scoring, anomaly analysis, retrieval-based explanations, and audit PDF export.",
        "Added seeded fictional tenders, bidders, and demonstration scenarios. The README records five tenders, 15 bids, and 89 generated sample PDFs for the initial demo.",
    ]),
    ("Source simulation and local operation", [
        "Created a separate mock government-source API and adapters. These are fictional demo records, not live government connections.",
        "Added Dockerfiles, Docker Compose, environment example, Make targets, startup/seed/smoke scripts, test suites, and a validation record.",
        "Exported 89 sample PDFs under sample-docs/generated; the generator itself is also tracked.",
    ]),
]
for title, bullets in prototype_groups:
    story.append(p(title, "SubX"))
    story.extend(bullet(b) for b in bullets)

story.append(section("2. Later update | 17 September"))
update_groups = [
    ("Official GeM tender intake", [
        "Added officer import of an official public GeM URL or an authorised uploaded GeM PDF. The provider restricts URL hosts and scheme, does not follow redirects, and reports restricted or missing pages without bypassing access controls.",
        "Stored the imported document, source metadata, hash, tender version, and audit event. Added parsing of tender metadata and an evidence-backed checklist of requirements with page text and confidence.",
        "Expanded tender search/detail screens to show GeM tenders, requirements, source document, and application queue.",
    ]),
    ("Bidder accounts and review ownership", [
        "Added bidder registration, bidder-created applications, document upload for bidder-owned submissions, and access checks that limit bidders to their own applications.",
        "Adjusted the officer/reviewer interface, navigation, dashboard and demo paths around imported tenders and application ownership.",
    ]),
    ("Source registry and risk settings", [
        "Added a source-registry API and persisted source configuration, plus a JSON file of explicit risk weights.",
        "Expanded database migrations for stored document content, tender architecture, and bidder submission ownership.",
    ]),
    ("Hosting and packaging", [
        "Added root and Vercel Dockerfiles, Vercel configuration, deployment startup/initialization scripts, production-to-local sync utility, and hosting notes.",
        "Added hosted-mode configuration, PostgreSQL URL normalization, database-backed document storage option, startup handling for stale work, and hosted processing behavior. Added a hosted-storage test.",
    ]),
    ("Repository support files", [
        "Added 69 Prisma-related agent skill/reference files and a repomix XML snapshot. These are developer support material, not application features.",
        "Added a large mock bidder JSON data file and updated ignore rules and container build configuration.",
    ]),
]
for title, bullets in update_groups:
    story.append(p(title, "SubX"))
    story.extend(bullet(b) for b in bullets)

story.append(section("3. Local setup since those commits"))
story.append(p("In the current session, Xcode's command-line-tool licence interrupted Git until it was accepted by the user. Docker then encountered host-port conflicts at 5432 and 8000. The project was started with PostgreSQL mapped to 5433 and backend mapped to 8010; the final terminal screenshot showed backend, frontend, PostgreSQL, and Qdrant containers healthy. These machine-specific operations are not source-code commits and are not included in the file inventory."))
story.append(p("The checked-in Docker Compose file currently defines four services. The README and older validation record describe a five-service layout including a separate mock API; those documents predate or differ from the latest Compose configuration. For the current runnable state, rely on the actual Compose file and container status.", "SmallX"))

story.append(section("4. How to read the complete inventory"))
story.append(p("The appendix is generated directly from Git's name-status diff for each later commit. A = added in that commit; M = modified in that commit. A path shown again as M in the second phase was first created in the prototype and later revised. Long names may wrap. The list includes generated PDFs and developer reference material so it remains exhaustive."))


def file_group(path: str) -> str:
    if path.startswith(".agents/"):
        return "Agent skills and references"
    if path.startswith("sample-docs/generated/"):
        return "Generated sample PDFs"
    if path.startswith("backend/"):
        return "Backend"
    if path.startswith("frontend/"):
        return "Frontend"
    if path.startswith("mock-gov-api/"):
        return "Mock source API"
    if path.startswith("deployment/"):
        return "Deployment"
    if path.startswith("scripts/"):
        return "Scripts"
    if path.startswith("sample-docs/"):
        return "Sample document tools"
    return "Repository root"


group_order = ["Repository root", "Backend", "Frontend", "Mock source API", "Sample document tools", "Generated sample PDFs", "Scripts", "Deployment", "Agent skills and references"]


def appendix(title: str, entries: list[tuple[str, str]]) -> None:
    story.append(PageBreak())
    story.append(section(title))
    story.append(p(f"{len(entries)} changed paths. Status is relative to the immediately preceding commit.", "SmallX"))
    for group in group_order:
        items = [(s, path) for s, path in entries if file_group(path) == group]
        if not items:
            continue
        rows = [[p(s, "FileStatus"), p(escape(path).replace("/", "/<wbr/>"), "FileX")] for s, path in items]
        listing_style = TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, colors.HexColor("#FAFCFD")]),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ])
        first_row = Table(rows[:1], colWidths=[24, 473], hAlign="LEFT")
        first_row.setStyle(listing_style)
        story.append(KeepTogether([p(f"{group} ({len(items)})", "SubX"), first_row]))
        if len(rows) > 1:
            listing = Table(rows[1:], colWidths=[24, 473], hAlign="LEFT")
            listing.setStyle(listing_style)
            story.append(listing)


appendix("Appendix A | First application build (f6161b8)", phase_one)
appendix("Appendix B | Subsequent update (b97ff9c)", phase_two)


def header_footer(canvas, doc) -> None:
    canvas.saveState()
    w, h = doc.pagesize
    canvas.setStrokeColor(line)
    canvas.setLineWidth(.5)
    canvas.line(47, h - 45, w - 47, h - 45)
    canvas.setFillColor(teal)
    canvas.setFont("Helvetica-Bold", 8)
    canvas.drawString(47, h - 35, "BYTECODE VERIFY")
    canvas.setFillColor(muted)
    canvas.setFont("Helvetica", 8)
    canvas.drawRightString(w - 47, h - 35, "CHANGE HISTORY  /  17 SEP 2026")
    canvas.line(47, 48, w - 47, 48)
    canvas.drawString(47, 34, "Source: local Git history b9ca40e..b97ff9c")
    canvas.drawRightString(w - 47, 34, f"Page {doc.page}")
    canvas.restoreState()


doc = BaseDocTemplate(str(OUT), pagesize=(595.28, 841.89), leftMargin=49, rightMargin=49, topMargin=62, bottomMargin=61, title="ByteCode Verify - Project Change History", author="Project change review")
frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0)
doc.addPageTemplates(PageTemplate(id="report", frames=frame, onPage=header_footer))
doc.build(story)
print(OUT)
print(f"Phase one: {len(phase_one)}; phase two: {len(phase_two)}; unique changed paths: {len(overall)}")
