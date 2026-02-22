"""PDF processing operations."""

from pathlib import Path
from typing import List, Tuple, Optional, Dict
import pymupdf
import pymupdf4llm
import base64
import io
from PIL import Image
from pdf_utils.config import (
    UPLOAD_DIR, IMAGE_COMPRESSION_QUALITY,
    MIN_IMAGE_SIZE, MAX_IMAGES_PER_PAGE
)


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


def extract_images_from_pages(
    source_path: Path, 
    start_page: int, 
    end_page: int
) -> Dict[int, List[Dict[str, str]]]:
    """
    Extract images from specified pages, filter and compress them.
    
    Args:
        source_path: Path to the source PDF file
        start_page: Starting page number (1-based)
        end_page: Ending page number (1-based)
        
    Returns:
        Dictionary with page numbers as keys and lists of image data as values.
        Each image data contains 'data' (base64) and 'filename'.
    """
    doc = pymupdf.open(source_path)
    result = {}
    base_name = source_path.stem
    
    for page_num in range(start_page, end_page + 1):
        page = doc[page_num - 1]
        image_list = page.get_images()
        
        if not image_list:
            continue
            
        # Extract all images with their dimensions
        page_images = []
        for img_index, img_info in enumerate(image_list):
            xref = img_info[0]
            
            try:
                # Extract image data
                img_data = doc.extract_image(xref)
                if not img_data:
                    continue
                
                width = img_data.get('width', 0)
                height = img_data.get('height', 0)
                
                # Filter out small images
                if width < MIN_IMAGE_SIZE or height < MIN_IMAGE_SIZE:
                    continue
                
                # Calculate area for sorting
                area = width * height
                
                page_images.append({
                    'data': img_data['image'],
                    'width': width,
                    'height': height,
                    'area': area,
                    'index': img_index,
                    'ext': img_data.get('ext', 'png')
                })
            except Exception as e:
                print(f"Error extracting image {xref}: {e}")
                continue
        
        # Sort by area (largest first) and take top MAX_IMAGES_PER_PAGE
        page_images.sort(key=lambda x: x['area'], reverse=True)
        page_images = page_images[:MAX_IMAGES_PER_PAGE]
        
        # Convert to compressed JPEG and base64 encode
        processed_images = []
        for img in page_images:
            try:
                # Open image with PIL
                pil_image = Image.open(io.BytesIO(img['data']))
                
                # Convert RGBA to RGB if necessary
                if pil_image.mode in ('RGBA', 'LA', 'P'):
                    # Create a white background
                    bg = Image.new('RGB', pil_image.size, (255, 255, 255))
                    if pil_image.mode == 'P':
                        pil_image = pil_image.convert('RGBA')
                    if pil_image.mode in ('RGBA', 'LA'):
                        bg.paste(pil_image, mask=pil_image.split()[-1])
                    else:
                        bg.paste(pil_image)
                    pil_image = bg
                elif pil_image.mode != 'RGB':
                    pil_image = pil_image.convert('RGB')
                
                # Compress to JPEG
                output_buffer = io.BytesIO()
                pil_image.save(output_buffer, format='JPEG', 
                              quality=IMAGE_COMPRESSION_QUALITY, 
                              optimize=True)
                output_buffer.seek(0)
                
                # Convert to base64
                base64_data = base64.b64encode(output_buffer.read()).decode('utf-8')
                
                # Create filename
                filename = f"{base_name}_page_{page_num}_img_{img['index']}.jpg"
                
                processed_images.append({
                    'data': f"data:image/jpeg;base64,{base64_data}",
                    'filename': filename,
                    'raw_data': output_buffer.getvalue()  # Keep raw data for ZIP download
                })
                
                # Clean up
                pil_image.close()
                output_buffer.close()
                
            except Exception as e:
                print(f"Error processing image on page {page_num}: {e}")
                continue
        
        if processed_images:
            result[page_num] = processed_images
    
    doc.close()
    return result