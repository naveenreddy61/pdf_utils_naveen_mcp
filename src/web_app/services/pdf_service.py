"""PDF processing operations."""

from pathlib import Path
from typing import List, Tuple, Optional
import pymupdf
import pymupdf4llm
from config import UPLOAD_DIR


def extract_toc(file_path: Path) -> List[Tuple[int, str, int]]:
    """
    Extract table of contents from a PDF file.
    
    Args:
        file_path: Path to the PDF file
        
    Returns:
        List of tuples (level, title, page_number)
    """
    doc = pymupdf.open(file_path)
    toc = doc.get_toc()
    doc.close()
    return toc


def extract_pages(source_path: Path, start_page: int, end_page: int, output_filename: str) -> Path:
    """
    Extract specified pages from a PDF file.
    
    Args:
        source_path: Path to the source PDF file
        start_page: Starting page number (1-based)
        end_page: Ending page number (1-based)
        output_filename: Name for the output file
        
    Returns:
        Path to the created PDF file
    """
    source_doc = pymupdf.open(source_path)
    new_doc = pymupdf.open()
    new_doc.insert_pdf(source_doc, from_page=start_page - 1, to_page=end_page - 1)
    
    output_path = UPLOAD_DIR / output_filename
    new_doc.save(str(output_path), garbage=4, deflate=True)
    
    new_doc.close()
    source_doc.close()
    
    return output_path


def convert_pages_to_images(
    source_path: Path, 
    start_page: int, 
    end_page: int,
    dpi: int = 150,
    image_format: str = "png"
) -> List[str]:
    """
    Convert specified pages to images.
    
    Args:
        source_path: Path to the source PDF file
        start_page: Starting page number (1-based)
        end_page: Ending page number (1-based)
        dpi: Resolution for the images
        image_format: Image format ('png' or 'jpg')
        
    Returns:
        List of created image filenames
    """
    doc = pymupdf.open(source_path)
    image_files = []
    base_name = source_path.stem
    
    for page_num in range(start_page, end_page + 1):
        page = doc[page_num - 1]
        pix = page.get_pixmap(dpi=dpi)
        
        output_filename = f"mcp_{base_name}_page_{page_num}.{image_format}"
        output_path = UPLOAD_DIR / output_filename
        
        pix.save(str(output_path))
        image_files.append(output_filename)
        pix = None
    
    doc.close()
    return image_files


def extract_text_plain(source_path: Path, start_page: int, end_page: int) -> str:
    """
    Extract plain text from specified pages.
    
    Args:
        source_path: Path to the source PDF file
        start_page: Starting page number (1-based)
        end_page: Ending page number (1-based)
        
    Returns:
        Extracted text content
    """
    doc = pymupdf.open(source_path)
    text_parts = []
    
    for page_num in range(start_page - 1, end_page):
        page = doc[page_num]
        text = page.get_text()
        text_parts.append(f"--- Page {page_num + 1} ---\n{text}")
    
    doc.close()
    return "\n\n".join(text_parts)


def extract_text_markdown(source_path: Path, start_page: int, end_page: int) -> str:
    """
    Extract text as Markdown from specified pages.
    
    Args:
        source_path: Path to the source PDF file
        start_page: Starting page number (1-based)
        end_page: Ending page number (1-based)
        
    Returns:
        Extracted text content in Markdown format
    """
    pages_list = list(range(start_page - 1, end_page))
    return pymupdf4llm.to_markdown(source_path, pages=pages_list)


def get_page_count(file_path: Path) -> int:
    """Get the number of pages in a PDF file."""
    doc = pymupdf.open(file_path)
    page_count = doc.page_count
    doc.close()
    return page_count