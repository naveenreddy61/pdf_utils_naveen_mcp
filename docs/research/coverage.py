"""How much of the PDF's own text layer does each markdown converter keep?"""
import glob, re, pdf_inspector, pymupdf, pymupdf4llm

def words(s):
    return set(w.lower() for w in re.findall(r"[A-Za-z]{4,}", s))

print(f"{'file':46} {'pg':>3} {'pi%':>6} {'mu%':>6}  worst pdf-inspector page")
for path in sorted(glob.glob("/root/projects/pdf_utils_naveen_mcp/uploads/*.pdf")):
    doc = pymupdf.open(path)
    pages = list(range(min(doc.page_count, 10)))
    raw = "\n".join(doc[p].get_text() for p in pages)
    if len(raw.strip()) < 200:
        continue
    try:
        pm = pdf_inspector.extract_pages_markdown(path, pages)
        per = [(len(pg.markdown or ""), len(doc[i].get_text())) for i, pg in zip(pages, pm.pages)]
        md_pi = "\n".join(pg.markdown or "" for pg in pm.pages)
    except Exception as e:
        print(f"{path.split('/')[-1][9:]:46.46} ERROR {type(e).__name__}"); continue
    md_mu = pymupdf4llm.to_markdown(path, pages=pages, show_progress=False)
    wr = words(raw)
    ratios = [(a / b if b > 40 else 1.0, i) for i, (a, b) in enumerate(per)]
    worst = min(ratios)
    print(f"{path.split('/')[-1][9:]:46.46} {len(pages):3} "
          f"{len(wr & words(md_pi)) / len(wr):6.1%} {len(wr & words(md_mu)) / len(wr):6.1%}"
          f"   p{worst[1]} keeps {worst[0]:.0%}")
