---
name: docx
description: Use this skill whenever the user wants to create, read, edit, or manipulate Word documents (.docx files). Triggers include any mention of 'Word doc', '.docx', or requests to produce professional documents with formatting like tables of contents, headings, page numbers, or letterheads. Also use when extracting or reorganizing content from .docx files, working with tracked changes or comments, or converting content into a polished Word document. Do NOT use for PDFs, spreadsheets, or Google Docs.
---

<!-- Source: anthropics/skills@docx (source-available) via claudemarketplaces.com -->

# DOCX Creation, Editing, and Analysis

## Overview

A .docx file is a ZIP archive containing XML files.

## Quick Reference

| Task | Approach |
|------|----------|
| Read/analyze content | `pandoc` or unpack for raw XML |
| Create new document | Use `docx-js` (see Creating New Documents) |
| Edit existing document | Unpack → edit XML → repack (see Editing Existing Documents) |

### Converting .doc to .docx

```bash
python scripts/office/soffice.py --headless --convert-to docx document.doc
```

### Reading Content

```bash
pandoc --track-changes=all document.docx -o output.md   # Text extraction
python scripts/office/unpack.py document.docx unpacked/ # Raw XML access
```

### Converting to Images

```bash
python scripts/office/soffice.py --headless --convert-to pdf document.docx
pdftoppm -jpeg -r 150 document.pdf page
```

---

## Creating New Documents

Install: `npm install -g docx`

### Setup

```javascript
const { Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, ImageRun,
        Header, Footer, AlignmentType, PageOrientation, LevelFormat, ExternalHyperlink,
        HeadingLevel, BorderStyle, WidthType, ShadingType, PageNumber, PageBreak } = require('docx');

const doc = new Document({ sections: [{ children: [/* content */] }] });
Packer.toBuffer(doc).then(buffer => fs.writeFileSync("doc.docx", buffer));
```

### Page Size

```javascript
// CRITICAL: docx-js defaults to A4 — always set page size explicitly
sections: [{
  properties: {
    page: {
      size: { width: 12240, height: 15840 }, // US Letter (1440 DXA = 1 inch)
      margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 }
    }
  },
  children: [/* content */]
}]
```

### Styles

```javascript
const doc = new Document({
  styles: {
    default: { document: { run: { font: "Arial", size: 24 } } }, // 12pt default
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 32, bold: true, font: "Arial" },
        paragraph: { spacing: { before: 240, after: 240 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 28, bold: true, font: "Arial" },
        paragraph: { spacing: { before: 180, after: 180 }, outlineLevel: 1 } },
    ]
  },
  sections: [{ children: [] }]
});
```

### Lists (NEVER use unicode bullets)

```javascript
// ❌ WRONG
new Paragraph({ children: [new TextRun("• Item")] })

// ✅ CORRECT
const doc = new Document({
  numbering: {
    config: [
      { reference: "bullets",
        levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
    ]
  },
  sections: [{
    children: [
      new Paragraph({ numbering: { reference: "bullets", level: 0 },
        children: [new TextRun("Bullet item")] }),
    ]
  }]
});
```

### Tables

**CRITICAL: Tables need dual widths** — set both `columnWidths` on the table AND `width` on each cell.

```javascript
const border = { style: BorderStyle.SINGLE, size: 1, color: "CCCCCC" };
const borders = { top: border, bottom: border, left: border, right: border };

new Table({
  width: { size: 9360, type: WidthType.DXA }, // US Letter content width
  columnWidths: [4680, 4680], // Must sum to table width
  rows: [
    new TableRow({
      children: [
        new TableCell({
          borders,
          width: { size: 4680, type: WidthType.DXA },
          shading: { fill: "D5E8F0", type: ShadingType.CLEAR }, // CLEAR not SOLID
          margins: { top: 80, bottom: 80, left: 120, right: 120 },
          children: [new Paragraph({ children: [new TextRun("Cell")] })]
        })
      ]
    })
  ]
})
```

### Critical Rules

- **Set page size explicitly** — defaults to A4; use US Letter (12240 x 15840 DXA)
- **Landscape: pass portrait dimensions** — docx-js swaps internally; set `orientation: PageOrientation.LANDSCAPE`
- **Never use `\n`** — use separate Paragraph elements
- **Never use unicode bullets** — use `LevelFormat.BULLET` with numbering config
- **PageBreak must be in Paragraph** — standalone creates invalid XML
- **ImageRun requires `type`** — always specify png/jpg/etc
- **Always set table `width` with DXA** — never `WidthType.PERCENTAGE` (breaks in Google Docs)
- **Tables need dual widths** — `columnWidths` array AND cell `width`, both must match
- **Use `ShadingType.CLEAR`** — never SOLID for table shading
- **TOC requires HeadingLevel only** — no custom styles on heading paragraphs
- **Include `outlineLevel`** — required for TOC (0 for H1, 1 for H2)

---

## Editing Existing Documents

**Follow all 3 steps in order.**

### Step 1: Unpack

```bash
python scripts/office/unpack.py document.docx unpacked/
```

### Step 2: Edit XML

Edit files in `unpacked/word/`. Use smart quotes for new content:

```xml
<w:t>Here&#x2019;s a quote: &#x201C;Hello&#x201D;</w:t>
```

Use `comment.py` for adding review comments:

```bash
python scripts/comment.py unpacked/ 0 "Comment text"
python scripts/comment.py unpacked/ 1 "Reply" --parent 0
```

### Step 3: Pack

```bash
python scripts/office/pack.py unpacked/ output.docx --original document.docx
```

### Tracked Changes

```xml
<!-- Insertion -->
<w:ins w:id="1" w:author="Claude" w:date="2025-01-01T00:00:00Z">
  <w:r><w:t>inserted text</w:t></w:r>
</w:ins>

<!-- Deletion -->
<w:del w:id="2" w:author="Claude" w:date="2025-01-01T00:00:00Z">
  <w:r><w:delText>deleted text</w:delText></w:r>
</w:del>
```

## Dependencies

- **pandoc**: Text extraction
- **docx**: `npm install -g docx` (new documents)
- **LibreOffice**: PDF conversion
- **Poppler**: `pdftoppm` for images
