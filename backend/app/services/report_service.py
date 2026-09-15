from io import BytesIO
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether


def audit_pdf(events: list[dict], integrity: dict, review: dict | None = None) -> bytes:
    """Paginated, printable officer evidence report with full hash and decision references."""
    buffer = BytesIO()
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='Small', fontSize=8, leading=12, textColor=colors.HexColor('#546578'), wordWrap='CJK'))
    styles.add(ParagraphStyle(name='TitleBC', fontSize=24, leading=29, textColor=colors.HexColor('#11243d'), spaceAfter=14))
    styles.add(ParagraphStyle(name='LabelBC', fontSize=10, leading=15, textColor=colors.HexColor('#117e81'), spaceAfter=12))
    p = lambda text, style='BodyText': Paragraph(escape(str(text)), styles[style])
    story = [p('BYTECODE VERIFY / AUDIT REPORT', 'LabelBC'), p('Evidence. Review. Accountability.', 'TitleBC'),
             p('MOCK AUTHORISED SOURCE - DEMO. All source checks use fictional records. The procurement officer retains final authority.'),
             Spacer(1, 6*mm), p(f"Audit integrity: {integrity['status']} | {integrity['checked_events']} events checked", 'Heading2'),
             p('Chain head: '+integrity.get('head_hash', integrity.get('failed_event_id', '')), 'Small'),
             p('Tamper-evident at the application layer. This is not an external timestamp or independent attestation.', 'Small'), Spacer(1, 7*mm)]
    if review:
        story.extend([p(review['bidder']['name'], 'Heading1'), p(review['tender']['reference']+' - '+review['tender']['title']),
                      p(f"Compliance: {review['compliance_score']} / 100 | Risk: {review['risk_level']} ({review['risk_score']} / 100)", 'Heading3')])
        if review.get('ai'):
            story.extend([p('AI advisory recommendation', 'Heading2'), p(review['ai']['summary']),
                          p(review['ai']['recommended_action'], 'Heading3')])
        for decision in review.get('decisions', [])[:3]:
            story.extend([p('Officer decision: '+decision['decision'], 'Heading2'),
                          p('Reason: '+decision['reason']), p('Reviewer: '+decision['reviewer'], 'Small'),
                          p(f"Recorded: {decision['created_at']} | Run: {decision['run_id']}", 'Small')])
        if review.get('risk'):
            story.append(p('Transparent compliance breakdown', 'Heading2'))
            data = [[p('Component'), p('Earned / weight')]] + [[p(x['component']), p(f"{x['earned']} / {x['weight']}")] for x in review['risk']['compliance']['breakdown']]
            table = Table(data, colWidths=[115*mm, 50*mm], repeatRows=1)
            table.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), colors.HexColor('#eaf0f5')), ('VALIGN',(0,0),(-1,-1),'TOP'),
                                       ('LINEBELOW',(0,0),(-1,-1),.3,colors.HexColor('#d9e1e8')), ('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7)]))
            story.append(table)
        for result in review.get('compliance', []):
            story.append(KeepTogether([p(f"{result['rule_code']} - {result['name']} - {result['status']}", 'Heading3'), p(result['explanation'])]))
    story.extend([Spacer(1, 6*mm), p('Append-only event record', 'Heading1')])
    for event in events:
        import json
        story.append(KeepTogether([p(f"#{event['sequence']}  {event['action'].replace('_', ' ')}", 'Heading3'),
                                   p(f"{event['created_at']} | {event['actor']}", 'Small'),
                                   p('Object: '+event['object_id'], 'Small')]))
        story.extend([p('Evidence: '+json.dumps(event['details'], ensure_ascii=True, default=str), 'Small'),
                      p('Previous hash: '+event['previous_hash'], 'Small'), p('Current hash: '+event['current_hash'], 'Small'), Spacer(1, 3*mm)])
    def footer(canvas, doc):
        canvas.setFont('Helvetica', 8)
        canvas.setFillColor(colors.HexColor('#546578'))
        canvas.drawString(22*mm, 12*mm, 'ByteCode Verify | SIH 2026 | Fictional demonstration | Officer decision support')
        canvas.drawRightString(188*mm, 12*mm, f'Page {doc.page}')
    SimpleDocTemplate(buffer, pagesize=(210*mm, 297*mm), leftMargin=22*mm, rightMargin=22*mm,
                      topMargin=20*mm, bottomMargin=23*mm).build(story, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()
