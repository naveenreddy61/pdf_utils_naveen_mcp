# md-render pipeline

Convert Markdown to PDF with Pandoc and Typst. The directory is
self-contained: copy it as one unit into your web app.

## Usage

```bash
./render.sh input.md output.pdf
```

## Necessary tools on the server

| Tool | Version | Purpose |
|---|---|---|
| pandoc | >= 3.x | Markdown parse + Typst code generation |
| typst | >= 0.12 | PDF engine (single binary, no browser, no TeX) |
| perl | any | pre-clean step (part of macOS and most Linux images) |
| node + `npm install` | optional | math auto-fix (KaTeX validation) |

If node or the `katex` package is absent, the script skips the math
auto-fix and continues. Run `npm install` in this directory once to
enable it.

## Fonts

The style uses **New Computer Modern** for body and headings (Typst
embeds this Computer Modern successor, so the page reads like a LaTeX
article), **New Computer Modern Math** for equations, and
**JetBrainsMono NF** for code (falls back to DejaVu Sans Mono). If a
font is absent, Typst falls back and shows a warning. Change the names
in `typst-header.typ` and the `mainfont` variable in `render.sh` if
you want a different family.

## What the script does

1. Copies the input to a temp file. The input is never changed.
2. Removes private-use Unicode glyphs (U+E000–F8FF) and
   `citeturn…` citation artifacts that AI tools put in Markdown.
   Order is important: the private-use glyphs sit between the letters
   of the citation tokens, so they must go first.
3. Applies the safe math auto-fix: empty `\sqrt{}` → `\sqrt{\,}`
   (Typst rejects an empty radicand; LaTeX tolerates it).
4. Runs pandoc with `--pdf-engine=typst` and these assets (`bar-to-overline.lua`
   rewrites TeX `\bar{x}` before the Typst writer, which would otherwise emit
   a superscript dash):

| File | Purpose |
|---|---|
| `table-widths.lua` | Proportional column widths (sqrt-scaled) so wide tables do not overflow. |
| `bar-to-overline.lua` | Rewrites TeX `\bar{x}` so Pandoc 3.1 does not emit a superscript dash. |
| `typst-header.typ` | Style: booktabs tables, breakable figures, fonts, code and quote backgrounds. Remaps Pandoc `\bar{x}` (`x^(‾)`) and compact `\overline` to a TeX-style macron so the bar sits on the letter. |
| `typst-meta.yaml` | A4 paper, 22 mm margins. (`-V margin=22mm` does not work; a metadata file is necessary.) |
| `mdlint.mjs` / `mdlint-cli.mjs` | KaTeX-based math validator and auto-fixer. |

## Known limits

- The `stray-backslash-eol` fix in `mdlint.mjs` is NOT applied by the
  script: it would remove `\\` line breaks inside multi-line display
  equations.
- `▢` (U+25A1) placeholders are kept — they can be intentional
  fill-in-the-blank markers.
- Pandoc wraps tables in `#figure`. The header sets
  `breakable: true` on figures; without it, long tables get crushed
  at the page bottom.

## Web-app integration

Call the script from your server code, for example:

```python
subprocess.run(
    ["/path/to/pipeline/render.sh", md_path, pdf_path],
    check=True, timeout=120,
)
```

Render time on an M-series Mac: ~1 s for a 25-page report,
~3 s for a 53-page math chapter.
