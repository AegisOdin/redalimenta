// Convierte informe.md (Markdown acotado) a Informe-RedAlimenta.docx con imágenes, tablas y TOC.
const fs = require('fs'), path = require('path');
const d = require('docx');
const { Document, Packer, Paragraph, TextRun, HeadingLevel, ImageRun, Table, TableRow, TableCell, WidthType, ShadingType,
  AlignmentType, TableOfContents, PageBreak, Footer, Header, PageNumber, LevelFormat, BorderStyle } = d;
const BASE = path.resolve(__dirname, '..', '..');
const ANCHO = 9638; // A4 con márgenes de 2 cm (DXA)
const md = fs.readFileSync(path.join(__dirname, 'informe.md'), 'utf8').split('\n');

function runs(txt, extra = {}) {
  const out = []; const re = /(\*\*[^*]+\*\*|`[^`]+`)/g; let last = 0, m;
  while ((m = re.exec(txt))) {
    if (m.index > last) out.push(new TextRun({ text: txt.slice(last, m.index), ...extra }));
    const t = m[0];
    if (t.startsWith('**')) out.push(new TextRun({ text: t.slice(2, -2), bold: true, ...extra }));
    else out.push(new TextRun({ text: t.slice(1, -1), font: 'Consolas', size: 18, color: '1F4E3D', ...extra }));
    last = m.index + t.length;
  }
  if (last < txt.length) out.push(new TextRun({ text: txt.slice(last), ...extra }));
  return out;
}
function celdas(l) { const out = []; let cur = '', code = false; const t = l.trim().slice(1, -1);
  for (const ch of t) { if (ch === '`') code = !code; if (ch === '|' && !code) { out.push(cur); cur = ''; } else cur += ch; }
  out.push(cur); return out; }
function pngSize(buf) { return { w: buf.readUInt32BE(16), h: buf.readUInt32BE(20) }; }
function imagen(rel, cap) {
  const p = path.join(BASE, rel); const buf = fs.readFileSync(p); const { w, h } = pngSize(buf);
  const maxW = 620, maxH = 820; let ww = Math.min(maxW, w), hh = ww * h / w; if (hh > maxH) { hh = maxH; ww = hh * w / h; }
  return [new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 120 }, keepNext: true,
            children: [new ImageRun({ type: 'png', data: buf, transformation: { width: Math.round(ww), height: Math.round(hh) },
              altText: { title: cap, description: cap, name: path.basename(p) } })] }),
          new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200 }, children: runs(cap, { italics: true, size: 18, color: '52514E' }) })];
}
function tabla(filas) {
  const n = filas[0].length; filas = filas.map(f => f.length > n ? [...f.slice(0, n - 1), f.slice(n - 1).join('|')] : f.concat(Array(n - f.length).fill(''))); const largo = Array(n).fill(0).map((_, j) => Math.min(60, Math.max(...filas.map(f => (f[j] || '').trim().length)))); const peso = largo.map(x => Math.max(x, 6) ** 0.8); const tot = peso.reduce((a, b) => a + b, 0);
  const cols = peso.map(x => Math.max(700, Math.floor(ANCHO * x / tot))); const ajuste = ANCHO - cols.reduce((a, b) => a + b, 0); cols[cols.indexOf(Math.max(...cols))] += ajuste;
  const borde = { style: BorderStyle.SINGLE, size: 4, color: 'C9D3CD' };
  return new Table({ width: { size: ANCHO, type: WidthType.DXA }, columnWidths: cols,
    rows: filas.map((f, i) => new TableRow({ tableHeader: i === 0, children: f.map((c, j) => new TableCell({
      width: { size: cols[j], type: WidthType.DXA }, borders: { top: borde, bottom: borde, left: borde, right: borde },
      shading: i === 0 ? { type: ShadingType.CLEAR, fill: '1F6F4A', color: 'auto' } : (i % 2 === 0 ? { type: ShadingType.CLEAR, fill: 'F3F7F5', color: 'auto' } : undefined),
      margins: { top: 50, bottom: 50, left: 80, right: 80 },
      children: [new Paragraph({ children: runs(c.trim(), i === 0 ? { bold: true, color: 'FFFFFF', size: 18 } : { size: 18 }) })] })) })) });
}
const hijos = []; let i = 0;
while (i < md.length) {
  const l = md[i];
  if (l.startsWith('```')) { const code = []; i++; while (i < md.length && !md[i].startsWith('```')) code.push(md[i++]); i++;
    code.forEach((c, k) => hijos.push(new Paragraph({ shading: { type: ShadingType.CLEAR, fill: 'F4F4F2', color: 'auto' },
      spacing: { before: k === 0 ? 80 : 0, after: k === code.length - 1 ? 120 : 0 }, indent: { left: 120 },
      children: [new TextRun({ text: c || ' ', font: 'Consolas', size: 16 })] }))); continue; }
  if (l.startsWith('|')) { const f = []; while (i < md.length && md[i].startsWith('|')) { if (!/^\|[\s:-]+\|/.test(md[i])) f.push(celdas(md[i])); i++; }
    hijos.push(tabla(f)); hijos.push(new Paragraph({ text: '' })); continue; }
  const im = l.match(/^!\[(.*)\]\((.*)\)$/); if (im) { hijos.push(...imagen(im[2], im[1])); i++; continue; }
  if (l.trim() === '\\pagebreak') { hijos.push(new Paragraph({ children: [new PageBreak()] })); i++; continue; }
  if (l.trim() === '[TOC]') { hijos.push(new TableOfContents('Contenido', { hyperlink: true, headingStyleRange: '1-2' })); i++; continue; }
  const h = l.match(/^(#{1,3}) (.*)/);
  if (h) { const lv = [HeadingLevel.HEADING_1, HeadingLevel.HEADING_2, HeadingLevel.HEADING_3][h[1].length - 1];
    hijos.push(new Paragraph({ heading: lv, pageBreakBefore: h[1].length === 1 && hijos.length > 3, children: runs(h[2]) })); i++; continue; }
  if (/^\s*- /.test(l)) { hijos.push(new Paragraph({ numbering: { reference: 'vinetas', level: l.startsWith('  ') ? 1 : 0 }, children: runs(l.replace(/^\s*- /, '')) })); i++; continue; }
  if (/^\d+\. /.test(l)) { hijos.push(new Paragraph({ numbering: { reference: 'numeros', level: 0 }, children: runs(l.replace(/^\d+\. /, '')) })); i++; continue; }
  if (l.trim() === '') { i++; continue; }
  const p = [l]; i++; while (i < md.length && md[i].trim() !== '' && !/^(#|\||!\[|```|\s*- |\d+\. |\\pagebreak)/.test(md[i])) p.push(md[i++]);
  hijos.push(new Paragraph({ spacing: { after: 120 }, alignment: AlignmentType.JUSTIFIED, children: runs(p.join(' ')) }));
}
const doc = new Document({
  creator: 'Neftali Odin Garcia Ramirez', title: 'RedAlimenta — Infraestructura Kubernetes para desarrollo y producción',
  features: { updateFields: true },
  styles: { default: { document: { run: { font: 'Calibri', size: 21 } } },
    paragraphStyles: [
      { id: 'Heading1', name: 'Heading 1', basedOn: 'Normal', next: 'Normal', quickFormat: true, run: { size: 32, bold: true, color: '1F6F4A' }, paragraph: { spacing: { before: 240, after: 160 }, outlineLevel: 0 } },
      { id: 'Heading2', name: 'Heading 2', basedOn: 'Normal', next: 'Normal', quickFormat: true, run: { size: 26, bold: true, color: '1D2521' }, paragraph: { spacing: { before: 220, after: 100 }, outlineLevel: 1, keepNext: true } },
      { id: 'Heading3', name: 'Heading 3', basedOn: 'Normal', next: 'Normal', quickFormat: true, run: { size: 22, bold: true, color: '1F6F4A' }, paragraph: { spacing: { before: 160, after: 80 }, outlineLevel: 2, keepNext: true } }] },
  numbering: { config: [
    { reference: 'vinetas', levels: [{ level: 0, format: LevelFormat.BULLET, text: '•', alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 500, hanging: 260 } } } },
                                     { level: 1, format: LevelFormat.BULLET, text: '◦', alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 900, hanging: 260 } } } }] },
    { reference: 'numeros', levels: [{ level: 0, format: LevelFormat.DECIMAL, text: '%1.', alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 500, hanging: 300 } } } }] }] },
  sections: [{ properties: { page: { margin: { top: 1134, bottom: 1134, left: 1134, right: 1134 } } },
    headers: { default: new Header({ children: [new Paragraph({ alignment: AlignmentType.RIGHT, children: [new TextRun({ text: 'RedAlimenta · Infraestructura Kubernetes dev/prod', size: 16, color: '8A958F' })] })] }) },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ children: ['Página ', PageNumber.CURRENT, ' de ', PageNumber.TOTAL_PAGES], size: 16, color: '8A958F' })] })] }) },
    children: hijos }] });
Packer.toBuffer(doc).then(b => { fs.writeFileSync(path.join(__dirname, 'Informe-RedAlimenta.docx'), b); console.log('docx ok', hijos.length, 'bloques'); });
