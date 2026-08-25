// typst-header.typ — styling overrides for pandoc -> typst
// Pass via: pandoc -H typst-header.typ ...
//
// New Computer Modern is Typst's embedded Computer Modern successor,
// so body, headings, and math match a LaTeX article. Libertinus Serif
// is the fallback if someone strips embedded fonts.

// ---- page & text ----
#set page(paper: "a4")
#set par(justify: true)
#set text(
  font: ("New Computer Modern", "Libertinus Serif"),
  lang: "en",
  hyphenate: true,
)
#show math.equation: set text(font: "New Computer Modern Math")

// ---- headings ----
#show heading: it => {
  set text(font: ("New Computer Modern", "Libertinus Serif"), weight: "bold")
  v(1.1em, weak: true)
  it
  v(0.45em, weak: true)
}

// ---- tables: booktabs-style rules + repeat header ----
// Pandoc wraps tables in #figure; figures do not break across pages
// by default, so long tables get crushed at the page bottom.
#show figure: set block(breakable: true)


#set table(
  inset: (x: 7pt, y: 4.5pt),
  stroke: (x: none, y: 0.5pt),
  fill: none,
  align: (auto, auto, auto),
)

#show table: it => {
  set text(size: 8.8pt)
  it
}

// thin top rule + heavier rule under header: achieved via hline in
// pandoc output; add a solid top border on the table itself.
#show table.cell.where(y: 0): set text(
  weight: "bold",
  font: ("New Computer Modern", "Libertinus Serif"),
)

// ---- code ----
#show raw: set text(font: ("JetBrainsMono NF", "DejaVu Sans Mono"), size: 8.4pt)
#show raw.where(block: true): it => {
  block(
    fill: rgb("#f6f8fa"),
    radius: 3pt,
    inset: (x: 9pt, y: 7pt),
    width: 100%,
    it,
  )
}

// ---- blockquote ----
#show quote: it => block(
  fill: rgb("#f6f8fa"),
  inset: (left: 12pt, right: 8pt, top: 6pt, bottom: 6pt),
  radius: 3pt,
  it,
)
