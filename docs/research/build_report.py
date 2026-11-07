"""Rebuild the reviewed Word report using the bundled document runtime."""
import json
from pathlib import Path
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

ROOT = Path(__file__).resolve().parent
pages = json.loads((ROOT / 'report_content.json').read_text(encoding='utf-8'))
doc = Document()
sec = doc.sections[0]
sec.page_width, sec.page_height = Inches(8.5), Inches(11)
sec.top_margin, sec.bottom_margin = Inches(.7), Inches(.65)
sec.left_margin = sec.right_margin = Inches(.75)
sec.header_distance = sec.footer_distance = Inches(.3)
for name in ['Normal', 'Title', 'Subtitle', 'Heading 1', 'Heading 2', 'List Bullet']:
    style = doc.styles[name]
    style.font.name = 'Calibri'
    style._element.get_or_add_rPr().rFonts.set(qn('w:eastAsia'), 'Microsoft YaHei')
    style.font.color.rgb = RGBColor(0, 0, 0)
    style.font.size = Pt(11)
    style.paragraph_format.line_spacing = 1.2
    style.paragraph_format.space_after = Pt(8)
doc.styles['Title'].font.size = Pt(24)
doc.styles['Heading 1'].font.size = Pt(20)
doc.styles['Heading 2'].font.size = Pt(13)
doc.styles['Heading 2'].paragraph_format.space_before = Pt(12)
doc.styles['Subtitle'].font.size = Pt(12)
doc.styles['Subtitle'].font.italic = False
for style in doc.styles:
    for border in list(style.element.iter(qn('w:pBdr'))):
        border.getparent().remove(border)
header = sec.header.paragraphs[0]
header.text = 'InfoExplorer  开源工程调研'
header.runs[0].font.size = Pt(9)
footer = sec.footer.paragraphs[0]
footer.alignment = 2
footer.add_run('2026-10-15   ·   ')
field = OxmlElement('w:fldSimple'); field.set(qn('w:instr'), 'PAGE'); footer._p.append(field)
for run in footer.runs: run.font.size = Pt(9)

def link(label, url):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(4)
    h = OxmlElement('w:hyperlink')
    rid = p.part.relate_to(url, 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink', is_external=True)
    h.set(qn('r:id'), rid)
    r = OxmlElement('w:r'); props = OxmlElement('w:rPr')
    color = OxmlElement('w:color'); color.set(qn('w:val'), '1D5B82'); props.append(color)
    size = OxmlElement('w:sz'); size.set(qn('w:val'), '20'); props.append(size)
    r.append(props); t = OxmlElement('w:t'); t.text = label + '  ↗'; r.append(t); h.append(r); p._p.append(h)

def table(headers, rows):
    t = doc.add_table(rows=1, cols=len(headers))
    t.autofit = False
    widths = [1.65, 2.05, 3.3] if headers[0] == '项目' else [1.0, 2.3, 3.7]
    for col, width in zip(t.columns, widths): col.width = Inches(width)
    for c, text in zip(t.rows[0].cells, headers): c.text = text
    repeat = OxmlElement('w:tblHeader'); t.rows[0]._tr.get_or_add_trPr().append(repeat)
    for row in rows:
        for c, text in zip(t.add_row().cells, row): c.text = text
    for i, row in enumerate(t.rows):
        no_split = OxmlElement('w:cantSplit'); row._tr.get_or_add_trPr().append(no_split)
        for j, c in enumerate(row.cells):
            c.width = Inches(widths[j]); c.vertical_alignment = 1
            pr = c._tc.get_or_add_tcPr()
            shade = OxmlElement('w:shd'); shade.set(qn('w:fill'), '36454F' if i == 0 else ('F5F6F7' if i % 2 == 0 else 'FFFFFF')); pr.append(shade)
            margins = OxmlElement('w:tcMar')
            for edge in ['top', 'left', 'bottom', 'right']:
                el = OxmlElement('w:' + edge); el.set(qn('w:w'), '90'); el.set(qn('w:type'), 'dxa'); margins.append(el)
            pr.append(margins)
            borders = OxmlElement('w:tcBorders')
            for edge in ['top', 'left', 'bottom', 'right']:
                el = OxmlElement('w:' + edge); el.set(qn('w:val'), 'single'); el.set(qn('w:sz'), '4'); el.set(qn('w:color'), 'D9D9D9'); borders.append(el)
            pr.append(borders)
            for p in c.paragraphs:
                p.paragraph_format.space_after = Pt(1); p.paragraph_format.line_spacing = 1.1
                if j == 0 and headers[0] != '项目': p.alignment = 1
                for r in p.runs:
                    r.font.size = Pt(10.5)
                    if i == 0: r.bold = True; r.font.color.rgb = RGBColor(255,255,255)
    doc.add_paragraph().paragraph_format.space_after = Pt(0)

md = []
for i, page in enumerate(pages):
    if i: doc.add_page_break()
    doc.add_paragraph(page['title'], 'Title' if i == 0 else 'Heading 1')
    md.append('# ' + page['title'])
    if page.get('subtitle'): doc.add_paragraph(page['subtitle'], 'Subtitle')
    for block in page['blocks']:
        kind = block[0]
        if kind == 'h': doc.add_paragraph(block[1], 'Heading 2'); md.append('## ' + block[1])
        elif kind == 'p': doc.add_paragraph(block[1]); md.append(block[1])
        elif kind == 'b': doc.add_paragraph(block[1], 'List Bullet'); md.append('- ' + block[1])
        elif kind == 'ref': link(block[1], block[2]); md.append('[' + block[1] + '](' + block[2] + ')')
        elif kind == 'table':
            table(block[1], block[2]); md.extend(['| ' + ' | '.join(block[1]) + ' |', '| ' + ' | '.join(['---'] * len(block[1])) + ' |'] + ['| ' + ' | '.join(r) + ' |' for r in block[2]])
    md.append('')
out = ROOT / 'InfoExplorer_开源工程调研与实施建议_20261015.docx'
doc.save(out)
(ROOT / 'OPEN_SOURCE_REVIEW_20261015.md').write_text('\n\n'.join(md), encoding='utf-8')
print(out)
