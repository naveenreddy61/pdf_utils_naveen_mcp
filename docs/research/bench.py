"""Compare pdf-inspector vs the pymupdf/pymupdf4llm path already in the app."""
import glob, time, json, sys
import pdf_inspector, pymupdf, pymupdf4llm

rows = []
for path in sorted(glob.glob("/root/projects/pdf_utils_naveen_mcp/uploads/*.pdf")):
    name = path.split("/")[-1][9:][:48]
    doc = pymupdf.open(path)
    npages = doc.page_count
    row = {"file": name, "pages": npages}

    # 1. classification
    t = time.perf_counter()
    try:
        c = pdf_inspector.classify_pdf(path)
        row["cls"] = str(c.pdf_type)
        row["conf"] = round(float(c.confidence), 2)
        row["ocr_pages"] = len(c.pages_needing_ocr or [])
    except Exception as e:
        row["cls"] = f"ERR {type(e).__name__}"
    row["t_cls"] = round(time.perf_counter() - t, 3)

    # baseline "is there text" via pymupdf, whole doc
    t = time.perf_counter()
    empty = sum(1 for p in doc if len(p.get_text().strip()) < 20)
    row["mupdf_blank_pages"] = empty
    row["t_mupdf_scan"] = round(time.perf_counter() - t, 3)

    # 2. full markdown, first 10 pages only for a fair per-page compare
    lim = min(npages, 10)
    t = time.perf_counter()
    try:
        pm = pdf_inspector.extract_pages_markdown(path, list(range(lim)))
        md_pi = "\n".join(p.markdown or "" for p in pm.pages)
    except Exception as e:
        md_pi = ""
        row["pi_md_err"] = f"{type(e).__name__}: {e}"[:80]
    row["t_pi_md"] = round(time.perf_counter() - t, 3)
    row["len_pi_md"] = len(md_pi)

    t = time.perf_counter()
    try:
        md_mu = pymupdf4llm.to_markdown(path, pages=list(range(lim)), show_progress=False)
    except Exception as e:
        md_mu = ""
        row["mu_md_err"] = f"{type(e).__name__}"
    row["t_mu_md"] = round(time.perf_counter() - t, 3)
    row["len_mu_md"] = len(md_mu)

    rows.append(row)
    doc.close()
    print(json.dumps(row), flush=True)

print("\n=== SUMMARY ===")
print(f"{'file':50} {'pg':>4} {'class':16} {'conf':>5} {'t_cls':>6} {'t_pi':>7} {'t_mu':>7} {'md_pi':>7} {'md_mu':>7}")
for r in rows:
    print(f"{r['file']:50.50} {r['pages']:4} {r.get('cls','?'):16.16} {r.get('conf',0):5} "
          f"{r['t_cls']:6} {r.get('t_pi_md',0):7} {r.get('t_mu_md',0):7} "
          f"{r.get('len_pi_md',0):7} {r.get('len_mu_md',0):7}")
