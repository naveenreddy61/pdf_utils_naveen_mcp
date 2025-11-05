"""
Comprehensive test script for OCR service with Google GenAI integration.

This script tests:
1. Searchable PDF processing
2. Image-based PDF OCR extraction  
3. Caching functionality
4. Multi-page chunking (configurable page groups)
5. Token usage tracking and reporting
"""

import asyncio
import pymupdf
from pathlib import Path
import sys
import time
from typing import Optional

# Add both root and web_app directories to path to import our modules
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))  # For config.py
sys.path.insert(0, str(project_root / "src" / "web_app"))  # For services

TEST_PDF_DIR = Path(__file__).parent / "test_pdfs"


def create_test_content() -> str:
    """Generate test content with text, math, and structure."""
    return """
Introduction to Machine Learning

Machine learning represents a paradigm shift in how we approach problem-solving 
with computers. Instead of explicitly programming solutions, we enable systems 
to learn patterns from data and make predictions or decisions based on that learning.

Mathematical Foundations

The core of many machine learning algorithms relies on mathematical optimization. 
For example, linear regression seeks to minimize the cost function:

J(θ) = (1/2m) Σ(hθ(xi) - yi)²

where θ represents the parameters, m is the number of training examples, 
hθ(xi) is the hypothesis function, and yi is the actual output.

Types of Machine Learning

1. Supervised Learning: Uses labeled training data
   - Classification: Predicting discrete categories
   - Regression: Predicting continuous values

2. Unsupervised Learning: Finds patterns in unlabeled data
   - Clustering: Grouping similar data points
   - Dimensionality Reduction: Simplifying data representation

3. Reinforcement Learning: Learning through interaction
   - Agent learns from rewards and penalties
   - Used in game playing, robotics, and autonomous systems

Applications and Impact

Machine learning has transformed numerous industries:
- Healthcare: Disease diagnosis and drug discovery
- Finance: Fraud detection and algorithmic trading
- Technology: Search engines and recommendation systems
- Transportation: Autonomous vehicles and route optimization

The rapid advancement in computational power and data availability continues 
to drive innovation in this field, making previously impossible applications 
now achievable.
    """.strip()


def create_searchable_pdf(output_path: Path, content: str) -> None:
    """Create a PDF with searchable text."""
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)  # A4 size
    
    # Add text to PDF
    text_rect = pymupdf.Rect(50, 50, 545, 792)
    page.insert_textbox(
        text_rect,
        content,
        fontsize=11,
        fontname="helv",
        align=pymupdf.TEXT_ALIGN_LEFT
    )
    
    doc.save(output_path)
    doc.close()
    print(f"✅ Created searchable PDF: {output_path}")


def create_image_based_pdf(searchable_pdf_path: Path, output_path: Path) -> None:
    """Create a PDF with image of text (non-searchable)."""
    # Open the searchable PDF
    source_doc = pymupdf.open(searchable_pdf_path)
    target_doc = pymupdf.open()
    
    # Convert first page to image
    page = source_doc[0]
    pix = page.get_pixmap(dpi=150)
    img_data = pix.tobytes("png")
    
    # Create new page and insert image
    new_page = target_doc.new_page(width=595, height=842)
    img_rect = new_page.rect
    new_page.insert_image(img_rect, stream=img_data)
    
    target_doc.save(output_path)
    source_doc.close()
    target_doc.close()
    print(f"✅ Created image-based PDF: {output_path}")


def create_multipage_pdf(output_path: Path, content: str, num_pages: int = 3) -> None:
    """Create a multi-page PDF for testing chunking."""
    doc = pymupdf.open()
    
    for i in range(num_pages):
        page = doc.new_page(width=595, height=842)
        page_content = f"=== PAGE {i+1} ===\n\n" + content[:800] + f"\n\n--- End of Page {i+1} ---"
        
        text_rect = pymupdf.Rect(50, 50, 545, 792)
        page.insert_textbox(
            text_rect,
            page_content,
            fontsize=11,
            fontname="helv",
            align=pymupdf.TEXT_ALIGN_LEFT
        )
    
    doc.save(output_path)
    doc.close()
    print(f"✅ Created {num_pages}-page PDF: {output_path}")


def setup_test_pdfs() -> tuple[Path, Path, Path]:
    """Create all test PDFs."""
    print("Setting up test PDFs...")
    TEST_PDF_DIR.mkdir(exist_ok=True)
    
    # Generate test content
    content = create_test_content()
    
    # Define file paths
    searchable_pdf = TEST_PDF_DIR / "test_searchable.pdf"
    image_pdf = TEST_PDF_DIR / "test_image_based.pdf"
    multipage_pdf = TEST_PDF_DIR / "test_multipage.pdf"
    
    # Create PDFs
    create_searchable_pdf(searchable_pdf, content)
    create_image_based_pdf(searchable_pdf, image_pdf)
    create_multipage_pdf(multipage_pdf, content, num_pages=3)
    
    return searchable_pdf, image_pdf, multipage_pdf


async def run_ocr_test(pdf_path: Path, test_name: str, start_page: int = 1, end_page: Optional[int] = None) -> dict:
    """Run OCR test on a PDF and return results."""
    from services.ocr_service import process_document_async
    
    if end_page is None:
        end_page = start_page
    
    print(f"\n🧪 {test_name}")
    print("-" * 50)
    
    progress_messages = []
    def progress_callback(msg):
        progress_messages.append(msg)
        print(f"   📊 {msg}")
    
    start_time = time.time()
    result = await process_document_async(
        pdf_path,
        start_page=start_page,
        end_page=end_page,
        progress_callback=progress_callback
    )
    test_time = time.time() - start_time
    
    print(f"\n   📈 Results:")
    print(f"   • Processing time: {result['processing_time']:.2f}s (total test time: {test_time:.2f}s)")
    print(f"   • Pages processed: {result['pages_processed']}")
    print(f"   • Token usage: {result['total_input_tokens']:,} input + {result['total_output_tokens']:,} output")
    
    if result.get('tokens_saved', 0) > 0:
        print(f"   • Tokens saved from cache: {result['tokens_saved']:,}")
    
    if result['cached_pages']:
        print(f"   • Cached pages: {result['cached_pages']}")
    if result['llm_pages']:
        print(f"   • LLM processed pages: {result['llm_pages']}")
    if result['fallback_pages']:
        print(f"   • Fallback pages: {result['fallback_pages']}")
    
    print(f"   • Text extracted: {len(result['full_text']):,} characters")
    print(f"   • Summary: {result['summary']}")
    
    # Show text sample
    if result['full_text']:
        sample = result['full_text'][:200].replace('\n', ' ').strip()
        print(f"   • Text sample: \"{sample}...\"")
    
    return result


async def main():
    """Main test runner."""
    print("🚀 Starting OCR Service Comprehensive Test")
    print("=" * 60)
    
    # Setup test PDFs
    searchable_pdf, image_pdf, multipage_pdf = setup_test_pdfs()
    
    print("\n📋 Test Configuration:")
    print(f"   • Test PDFs location: {TEST_PDF_DIR}")
    print(f"   • Searchable PDF: {searchable_pdf.name}")
    print(f"   • Image-based PDF: {image_pdf.name}")
    print(f"   • Multi-page PDF: {multipage_pdf.name}")
    
    # Import configuration to show settings
    try:
        from config import OCR_MODEL, OCR_CONCURRENT_REQUESTS
        print(f"   • OCR Model: {OCR_MODEL}")
        print(f"   • Pages per chunk: 1 (single page processing)")
        print(f"   • Concurrent requests: {OCR_CONCURRENT_REQUESTS}")
    except ImportError:
        print("   • Could not load configuration")
    
    results = {}
    
    # Test 1: Searchable PDF (first time - should use LLM)
    results['searchable_first'] = await run_ocr_test(
        searchable_pdf, 
        "Test 1: Searchable PDF (First Run)"
    )
    
    # Test 2: Image-based PDF (should use LLM for OCR)
    results['image_based'] = await run_ocr_test(
        image_pdf, 
        "Test 2: Image-based PDF (OCR Required)"
    )
    
    # Test 3: Searchable PDF again (should use cache)
    results['searchable_cached'] = await run_ocr_test(
        searchable_pdf, 
        "Test 3: Searchable PDF (Should Use Cache)"
    )
    
    # Test 4: Image-based PDF again (should use cache)
    results['image_cached'] = await run_ocr_test(
        image_pdf, 
        "Test 4: Image-based PDF (Should Use Cache)"
    )
    
    # Test 5: Multi-page PDF (test chunking)
    results['multipage'] = await run_ocr_test(
        multipage_pdf, 
        "Test 5: Multi-page PDF (Chunking Test)",
        start_page=1,
        end_page=3
    )
    
    # Summary Analysis
    print("\n📊 TEST SUMMARY")
    print("=" * 60)
    
    # Cache effectiveness
    first_run_tokens = results['searchable_first']['total_input_tokens'] + results['searchable_first']['total_output_tokens']
    cached_run_tokens = results['searchable_cached']['total_input_tokens'] + results['searchable_cached']['total_output_tokens']
    cache_savings = results['searchable_cached'].get('tokens_saved', 0)
    
    print(f"\n🎯 Caching Performance:")
    print(f"   • First run total tokens: {first_run_tokens:,}")
    print(f"   • Cached run total tokens: {cached_run_tokens:,}")
    print(f"   • Tokens saved from cache: {cache_savings:,}")
    print(f"   • Cache hit rate: {(cache_savings / max(first_run_tokens, 1)) * 100:.1f}%")
    
    # Processing speed comparison
    print(f"\n⚡ Processing Speed:")
    print(f"   • Searchable (first): {results['searchable_first']['processing_time']:.2f}s")
    print(f"   • Searchable (cached): {results['searchable_cached']['processing_time']:.2f}s")
    print(f"   • Image-based (first): {results['image_based']['processing_time']:.2f}s")
    print(f"   • Image-based (cached): {results['image_cached']['processing_time']:.2f}s")
    print(f"   • Multi-page (3 pages): {results['multipage']['processing_time']:.2f}s")
    
    # Text extraction quality
    print(f"\n📄 Text Extraction:")
    print(f"   • Searchable PDF: {len(results['searchable_first']['full_text']):,} chars")
    print(f"   • Image-based PDF: {len(results['image_based']['full_text']):,} chars")
    print(f"   • Multi-page PDF: {len(results['multipage']['full_text']):,} chars")
    
    # Token usage analysis
    total_tokens_used = sum(
        r['total_input_tokens'] + r['total_output_tokens'] 
        for r in results.values()
    )
    total_tokens_saved = sum(
        r.get('tokens_saved', 0) 
        for r in results.values()
    )
    
    print(f"\n💰 Token Usage Summary:")
    print(f"   • Total tokens used: {total_tokens_used:,}")
    print(f"   • Total tokens saved: {total_tokens_saved:,}")
    print(f"   • Net token efficiency: {((total_tokens_saved) / max(total_tokens_used + total_tokens_saved, 1)) * 100:.1f}%")
    
    # Method distribution
    methods_used = {}
    for result in results.values():
        for method in ['cached', 'llm', 'fallback']:
            pages = result.get(f'{method}_pages', [])
            if pages:
                methods_used[method] = methods_used.get(method, 0) + len(pages)
    
    print(f"\n🔧 Processing Methods Used:")
    for method, count in methods_used.items():
        print(f"   • {method.upper()}: {count} pages")
    
    print(f"\n✅ All tests completed successfully!")
    print("=" * 60)
    
    # Cleanup option (only in interactive mode)
    try:
        cleanup = input("\nClean up test PDFs? (y/N): ").lower().strip()
    except (EOFError, KeyboardInterrupt):
        cleanup = 'n'  # Default to no cleanup in non-interactive mode
    
    if cleanup == 'y':
        for pdf_path in [searchable_pdf, image_pdf, multipage_pdf]:
            if pdf_path.exists():
                pdf_path.unlink()
                print(f"🗑️  Deleted: {pdf_path.name}")
        
        # Try to remove test directory if empty
        try:
            TEST_PDF_DIR.rmdir()
            print(f"🗑️  Removed empty directory: {TEST_PDF_DIR}")
        except OSError:
            print(f"📁 Directory not empty, keeping: {TEST_PDF_DIR}")
    else:
        print(f"📁 Test PDFs preserved in: {TEST_PDF_DIR}")
        print(f"   You can manually delete them or run the test again to clean up.")


if __name__ == "__main__":
    print("🔬 OCR Service Test Suite")
    print("Testing Google GenAI integration with PDF processing")
    print()
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⚠️  Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()