import pdf_inspector, pymupdf4llm, pymupdf, sys, re

path = sys.argv[1]
pages = [int(x) for x in sys.argv[2].split(",")]
pm = pdf_inspector.extract_pages_markdown(path, pages)
md_pi = "\n".join(p.markdown or "" for p in pm.pages)
md_mu = pymupdf4llm.to_markdown(path, pages=pages, show_progress=False)
raw = "\n".join(pymupdf.open(path)[p].get_text() for p in pages)

def words(s):
    return set(w.lower() for w in re.findall(r"[A-Za-z]{4,}", s))
wr, wi, wm = words(raw), words(md_pi), words(md_mu)
print(f"raw pymupdf words={len(wr)}  pi covers {len(wr&wi)/max(len(wr),1):.1%}  "
      f"mu4llm covers {len(wr&wm)/max(len(wr),1):.1%}")
print("missing from pdf-inspector (sample):", sorted(wr - wi)[:25])
print("\n--- pdf-inspector (first 1200) ---\n", md_pi[:1200])
print("\n--- pymupdf4llm (first 1200) ---\n", md_mu[:1200])
