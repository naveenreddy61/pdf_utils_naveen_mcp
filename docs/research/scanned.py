"""Does classification actually catch a scanned PDF, and a mixed one?"""
import pymupdf, pdf_inspector, io, time

src = "/root/projects/pdf_utils_naveen_mcp/uploads/fa1a9191_w35559.pdf"

# 1. Fully "scanned": rasterise 6 pages, no text layer at all.
doc = pymupdf.open(src)
scan = pymupdf.open()
for i in range(6):
    pix = doc[i].get_pixmap(dpi=150)
    p = scan.new_page(width=doc[i].rect.width, height=doc[i].rect.height)
    p.insert_image(p.rect, pixmap=pix)
scan.save("/tmp/scan_only.pdf")

# 2. Mixed: 3 rasterised + 3 real text pages.
mix = pymupdf.open()
mix.insert_pdf(pymupdf.open("/tmp/scan_only.pdf"), from_page=0, to_page=2)
mix.insert_pdf(doc, from_page=0, to_page=2)
mix.save("/tmp/mixed.pdf")

for path in ("/tmp/scan_only.pdf", "/tmp/mixed.pdf", src):
    t = time.perf_counter()
    c = pdf_inspector.classify_pdf(path)
    dt = time.perf_counter() - t
    print(f"{path:24} -> {str(c.pdf_type):12} conf={c.confidence:.2f} "
          f"ocr_pages={c.pages_needing_ocr} ({dt*1000:.0f} ms)")
    print("   attrs:", {k: getattr(c, k) for k in dir(c)
                        if not k.startswith('_') and not callable(getattr(c, k))})
