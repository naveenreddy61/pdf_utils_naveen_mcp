#!/usr/bin/env python3
"""FastHTML Web Application for PDF Utilities."""

import hashlib
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Any, List
import asyncio

from fasthtml.common import *
from fastlite import *
import pymupdf
import pymupdf4llm
from dataclasses import dataclass
from starlette.requests import Request

# Constants
FILE_RETENTION_DAYS = 30
MAX_FILE_SIZE_MB = 100
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
UPLOAD_DIR = Path("uploads")
DB_PATH = "pdf_files.db"
ALLOWED_EXTENSIONS = {'.pdf'}

# Create upload directory if it doesn't exist
UPLOAD_DIR.mkdir(exist_ok=True)

# Initialize FastHTML app
app, rt = fast_app(
    hdrs=(
        Link(rel='stylesheet', href='https://cdn.jsdelivr.net/npm/normalize.css@8.0.1/normalize.min.css'),
        Script(src="https://unpkg.com/htmx.org@2.0.0"),
        Style("""
            body { font-family: system-ui, -apple-system, sans-serif; max-width: 1200px; margin: 0 auto; padding: 20px; }
            .container { background: #f5f5f5; padding: 2rem; border-radius: 8px; margin: 1rem 0; }
            .file-info { background: white; padding: 1rem; margin: 1rem 0; border-radius: 4px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
            .operation-buttons { display: flex; gap: 10px; flex-wrap: wrap; margin: 1rem 0; }
            .operation-buttons button { flex: 1; min-width: 150px; }
            button, .button {
                background-color: #007bff;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 4px;
                cursor: pointer;
                text-decoration: none;
                display: inline-block;
                font-size: 14px;
                transition: background-color 0.3s;
            }
            button:hover, .button:hover {
                background-color: #0056b3;
            }
            button:active, .button:active {
                transform: translateY(1px);
            }
            .result-area { background: white; padding: 1.5rem; margin: 1rem 0; border-radius: 4px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
            .error { color: #dc3545; padding: 1rem; background: #f8d7da; border-radius: 4px; margin: 1rem 0; }
            .success { color: #155724; padding: 1rem; background: #d4edda; border-radius: 4px; margin: 1rem 0; }
            .warning { color: #856404; padding: 1rem; background: #fff3cd; border-radius: 4px; margin: 1rem 0; }
            table { width: 100%; border-collapse: collapse; }
            th, td { text-align: left; padding: 8px; border-bottom: 1px solid #ddd; }
            th { background-color: #f2f2f2; }
            .image-gallery { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 1rem; }
            .image-thumb { max-width: 100%; height: auto; border: 1px solid #ddd; }
            .loading { opacity: 0.6; pointer-events: none; }
            .spinner { display: inline-block; width: 20px; height: 20px; border: 3px solid rgba(0,0,0,.1); border-radius: 50%; border-top-color: #007bff; animation: spin 1s ease-in-out infinite; }
            @keyframes spin { to { transform: rotate(360deg); } }
        """)
    )
)

# Define database model
@dataclass
class FileRecord:
    file_hash: str  # Primary key
    original_filename: str
    stored_filename: str
    file_size: int
    page_count: int
    upload_date: str
    last_accessed: str

# Initialize database
db = database(DB_PATH)
files = db.create(FileRecord, pk='file_hash')


def calculate_file_hash(file_content: bytes) -> str:
    """Calculate SHA-256 hash of file content."""
    return hashlib.sha256(file_content).hexdigest()


def sanitize_filename(filename: str) -> str:
    """Sanitize filename for safe storage."""
    # Keep only alphanumeric, dots, hyphens, and underscores
    import re
    name = Path(filename).stem
    ext = Path(filename).suffix
    safe_name = re.sub(r'[^\w\-_]', '_', name)
    return f"{safe_name}{ext}"


async def cleanup_old_files():
    """Remove files older than FILE_RETENTION_DAYS."""
    cutoff_date = datetime.now() - timedelta(days=FILE_RETENTION_DAYS)
    cutoff_str = cutoff_date.isoformat()
    
    # Find old files
    old_files = files(where=f"upload_date < '{cutoff_str}'")
    
    for file_record in old_files:
        # Delete the physical file
        file_path = UPLOAD_DIR / file_record.stored_filename
        if file_path.exists():
            file_path.unlink()
        
        # Delete processed files (with mcp_ prefix)
        for f in UPLOAD_DIR.glob(f"mcp_{file_record.stored_filename.replace('.pdf', '')}_*"):
            f.unlink()
        
        # Remove from database
        files.delete(file_record.file_hash)
    
    return len(old_files)


def upload_form():
    """Return the upload form component."""
    return Form(
        Input(type="file", name="pdf_file", accept=".pdf", 
              onchange="this.form.submit()", 
              style="margin-bottom: 1rem;"),
        method="post",
        action="/upload",
        enctype="multipart/form-data"
    )


def page_with_result(result_content):
    """Return a full page with upload form and result content."""
    return Titled("PDF Utilities",
        Div(
            H2("PDF Processing Tools"),
            P("Upload a PDF file to use various processing tools. Files are kept for 30 days."),
            P(f"Maximum file size: {MAX_FILE_SIZE_MB}MB"),
            upload_form(),
            result_content,
            cls="container"
        )
    )


@rt('/')
def index():
    """Main page with file upload form."""
    return Titled("PDF Utilities",
        Div(
            H2("PDF Processing Tools"),
            P("Upload a PDF file to use various processing tools. Files are kept for 30 days."),
            P(f"Maximum file size: {MAX_FILE_SIZE_MB}MB"),
            
            upload_form(),
            
            Div(id="upload-result"),
            
            cls="container"
        )
    )


@rt('/upload', methods=['POST'])
async def upload(request: Request):
    """Handle file upload with deduplication."""
    try:
        # Get form data
        form = await request.form()
        pdf_file = form.get('pdf_file')
        
        # Debug logging
        print(f"Form keys: {list(form.keys())}")
        print(f"pdf_file type: {type(pdf_file)}")
        
        # Check if file was uploaded
        if not pdf_file:
            return page_with_result(
                P("Error: No file was uploaded.", cls="error")
            )
        
        # Check if it's a valid file upload
        if not hasattr(pdf_file, 'filename'):
            return page_with_result(
                P(f"Error: Invalid file upload. Received type: {type(pdf_file)}", cls="error")
            )
        
        # Check file extension
        if not pdf_file.filename.lower().endswith('.pdf'):
            return page_with_result(
                P("Error: Only PDF files are allowed.", cls="error")
            )
        
        # Read file content
        print(f"Reading file: {pdf_file.filename}")
        content = await pdf_file.read()
        print(f"File size: {len(content)} bytes")
        
        # Check file size
        if len(content) > MAX_FILE_SIZE_BYTES:
            return page_with_result(
                P(f"Error: File size exceeds {MAX_FILE_SIZE_MB}MB limit.", cls="error")
            )
        
        # Calculate hash
        file_hash = calculate_file_hash(content)
        
        # Check if file already exists
        existing = files.get(file_hash)
        
        if existing:
            # Update last accessed time
            files.update({'last_accessed': datetime.now().isoformat()}, file_hash)
            stored_filename = existing.stored_filename
            page_count = existing.page_count
            file_info = existing
        else:
            # Save new file
            safe_filename = sanitize_filename(pdf_file.filename)
            stored_filename = f"{file_hash[:8]}_{safe_filename}"
            file_path = UPLOAD_DIR / stored_filename
            
            print(f"Saving file to: {file_path}")
            file_path.write_bytes(content)
            print(f"File saved successfully")
            
            # Get PDF info
            doc = pymupdf.open(file_path)
            page_count = doc.page_count
            doc.close()
            
            # Store in database
            file_info = FileRecord(
                file_hash=file_hash,
                original_filename=pdf_file.filename,
                stored_filename=stored_filename,
                file_size=len(content),
                page_count=page_count,
                upload_date=datetime.now().isoformat(),
                last_accessed=datetime.now().isoformat()
            )
            files.insert(file_info)
        
        # Return file info and operation buttons
        return page_with_result(
            Div(
                Div(
                    H3("File Information"),
                    P(f"Original name: {file_info.original_filename}"),
                    P(f"Size: {file_info.file_size / 1024 / 1024:.2f} MB"),
                    P(f"Pages: {page_count}"),
                    P("File uploaded successfully!" if not existing else "File already exists, using cached version.", 
                      cls="success" if not existing else "warning"),
                    cls="file-info"
                ),
                
                Div(
                    H3("Available Operations"),
                    Div(
                        Button("Extract Table of Contents", 
                               hx_post=f"/process/toc/{file_hash}",
                               hx_target="#operation-result",
                               cls="button"),
                        
                        Button("Extract Pages", 
                               hx_get=f"/extract-pages-form/{file_hash}",
                               hx_target="#operation-result",
                               cls="button"),
                        
                        Button("Convert to Images", 
                               hx_get=f"/convert-images-form/{file_hash}",
                               hx_target="#operation-result",
                               cls="button"),
                        
                        Button("Extract Text", 
                               hx_get=f"/extract-text-form/{file_hash}",
                               hx_target="#operation-result",
                               cls="button"),
                        
                        cls="operation-buttons"
                    )
                ),
                
                Div(id="operation-result")
            )
        )
        
    except Exception as e:
        print(f"Upload error: {str(e)}")
        import traceback
        traceback.print_exc()
        return page_with_result(
            P(f"Error uploading file: {str(e)}", cls="error")
        )


@rt('/process/toc/{file_hash}')
def process_toc(file_hash: str):
    """Extract and display table of contents."""
    try:
        file_info = files.get(file_hash)
        if not file_info:
            return Div(P("File not found.", cls="error"))
        
        file_path = UPLOAD_DIR / file_info.stored_filename
        
        # Extract TOC
        doc = pymupdf.open(file_path)
        toc = doc.get_toc()
        doc.close()
        
        if not toc:
            return Div(
                H3("Table of Contents"),
                P("This PDF has no table of contents.", cls="warning"),
                cls="result-area"
            )
        
        # Build TOC display
        toc_items = []
        for level, title, page in toc:
            indent = "&nbsp;" * (level * 4)
            toc_items.append(
                Tr(
                    Td(NotStr(indent + title)),
                    Td(str(page))
                )
            )
        
        return Div(
            H3("Table of Contents"),
            Table(
                Thead(
                    Tr(Th("Title"), Th("Page"))
                ),
                Tbody(*toc_items)
            ),
            cls="result-area"
        )
        
    except Exception as e:
        return Div(P(f"Error extracting TOC: {str(e)}", cls="error"))


@rt('/extract-pages-form/{file_hash}')
def extract_pages_form(file_hash: str):
    """Show form for page extraction."""
    file_info = files.get(file_hash)
    if not file_info:
        return Div(P("File not found.", cls="error"))
    
    return Div(
        H3("Extract Pages"),
        P(f"Total pages: {file_info.page_count}"),
        Form(
            Label("Start Page:", Input(type="number", name="start_page", 
                                      min="1", max=str(file_info.page_count), 
                                      value="1", required=True)),
            Label("End Page:", Input(type="number", name="end_page", 
                                    min="1", max=str(file_info.page_count), 
                                    value=str(file_info.page_count), required=True)),
            Button("Extract Pages", type="submit"),
            hx_post=f"/process/extract-pages/{file_hash}",
            hx_target="#operation-result"
        ),
        cls="result-area"
    )


@rt('/process/extract-pages/{file_hash}')
async def process_extract_pages(file_hash: str, start_page: int, end_page: int):
    """Extract specified pages from PDF."""
    try:
        file_info = files.get(file_hash)
        if not file_info:
            return Div(P("File not found.", cls="error"))
        
        file_path = UPLOAD_DIR / file_info.stored_filename
        
        # Validate page range
        if start_page < 1 or end_page > file_info.page_count or start_page > end_page:
            return Div(P("Invalid page range.", cls="error"))
        
        # Extract pages
        source_doc = pymupdf.open(file_path)
        new_doc = pymupdf.open()
        new_doc.insert_pdf(source_doc, from_page=start_page - 1, to_page=end_page - 1)
        
        # Save extracted pages
        output_filename = f"mcp_{file_info.stored_filename.replace('.pdf', '')}_pages_{start_page}_to_{end_page}.pdf"
        output_path = UPLOAD_DIR / output_filename
        
        new_doc.save(output_path, garbage=4, deflate=True)
        new_doc.close()
        source_doc.close()
        
        return Div(
            H3("Pages Extracted Successfully"),
            P(f"Extracted pages {start_page} to {end_page}"),
            P(A("Download Extracted PDF", 
                href=f"/download/{output_filename}",
                download=output_filename,
                cls="button")),
            cls="result-area"
        )
        
    except Exception as e:
        return Div(P(f"Error extracting pages: {str(e)}", cls="error"))


@rt('/convert-images-form/{file_hash}')
def convert_images_form(file_hash: str):
    """Show form for image conversion."""
    file_info = files.get(file_hash)
    if not file_info:
        return Div(P("File not found.", cls="error"))
    
    return Div(
        H3("Convert Pages to Images"),
        P(f"Total pages: {file_info.page_count}"),
        Form(
            Label("Start Page:", Input(type="number", name="start_page", 
                                      min="1", max=str(file_info.page_count), 
                                      value="1", required=True)),
            Label("End Page:", Input(type="number", name="end_page", 
                                    min="1", max=str(file_info.page_count), 
                                    value=str(min(5, file_info.page_count)), required=True)),
            Label("DPI:", Input(type="number", name="dpi", 
                               min="72", max="300", value="150", required=True)),
            Label("Format:", 
                  Select(
                      Option("PNG", value="png", selected=True),
                      Option("JPG", value="jpg"),
                      name="image_format"
                  )),
            Button("Convert to Images", type="submit"),
            hx_post=f"/process/convert-images/{file_hash}",
            hx_target="#operation-result",
            hx_indicator="#convert-spinner"
        ),
        Div(id="convert-spinner", cls="spinner", style="display: none;"),
        cls="result-area"
    )


@rt('/process/convert-images/{file_hash}')
async def process_convert_images(file_hash: str, start_page: int, end_page: int, 
                                dpi: int = 150, image_format: str = "png"):
    """Convert specified pages to images."""
    try:
        file_info = files.get(file_hash)
        if not file_info:
            return Div(P("File not found.", cls="error"))
        
        file_path = UPLOAD_DIR / file_info.stored_filename
        
        # Validate page range
        if start_page < 1 or end_page > file_info.page_count or start_page > end_page:
            return Div(P("Invalid page range.", cls="error"))
        
        # Convert pages to images
        doc = pymupdf.open(file_path)
        image_files = []
        
        for page_num in range(start_page, end_page + 1):
            page = doc[page_num - 1]
            pix = page.get_pixmap(dpi=dpi)
            
            output_filename = f"mcp_{file_info.stored_filename.replace('.pdf', '')}_page_{page_num}.{image_format}"
            output_path = UPLOAD_DIR / output_filename
            
            pix.save(output_path)
            image_files.append(output_filename)
            pix = None
        
        doc.close()
        
        # Create image gallery
        image_elements = []
        for img_file in image_files:
            image_elements.append(
                Div(
                    A(
                        Img(src=f"/download/{img_file}", cls="image-thumb"),
                        href=f"/download/{img_file}",
                        download=img_file
                    )
                )
            )
        
        return Div(
            H3("Images Generated Successfully"),
            P(f"Converted {len(image_files)} pages to {image_format.upper()} format at {dpi} DPI"),
            Div(*image_elements, cls="image-gallery"),
            cls="result-area"
        )
        
    except Exception as e:
        return Div(P(f"Error converting to images: {str(e)}", cls="error"))


@rt('/extract-text-form/{file_hash}')
def extract_text_form(file_hash: str):
    """Show form for text extraction."""
    file_info = files.get(file_hash)
    if not file_info:
        return Div(P("File not found.", cls="error"))
    
    return Div(
        H3("Extract Text"),
        P(f"Total pages: {file_info.page_count}"),
        Form(
            Label("Start Page:", Input(type="number", name="start_page", 
                                      min="1", max=str(file_info.page_count), 
                                      value="1", required=True)),
            Label("End Page:", Input(type="number", name="end_page", 
                                    min="1", max=str(file_info.page_count), 
                                    value=str(file_info.page_count), required=True)),
            Label(Input(type="checkbox", name="markdown", checked=True),
                  " Extract as Markdown"),
            Button("Extract Text", type="submit"),
            hx_post=f"/process/extract-text/{file_hash}",
            hx_target="#operation-result",
            hx_indicator="#text-spinner"
        ),
        Div(id="text-spinner", cls="spinner", style="display: none;"),
        cls="result-area"
    )


@rt('/process/extract-text/{file_hash}')
async def process_extract_text(file_hash: str, start_page: int, end_page: int, 
                              markdown: Optional[str] = None):
    """Extract text from specified pages."""
    try:
        file_info = files.get(file_hash)
        if not file_info:
            return Div(P("File not found.", cls="error"))
        
        file_path = UPLOAD_DIR / file_info.stored_filename
        
        # Validate page range
        if start_page < 1 or end_page > file_info.page_count or start_page > end_page:
            return Div(P("Invalid page range.", cls="error"))
        
        use_markdown = markdown == "on"
        
        if use_markdown:
            # Use pymupdf4llm for Markdown extraction
            pages_list = list(range(start_page - 1, end_page))
            text_content = pymupdf4llm.to_markdown(file_path, pages=pages_list)
        else:
            # Use regular PyMuPDF for plain text extraction
            doc = pymupdf.open(file_path)
            text_parts = []
            
            for page_num in range(start_page - 1, end_page):
                page = doc[page_num]
                text = page.get_text()
                text_parts.append(f"--- Page {page_num + 1} ---\n{text}")
            
            doc.close()
            text_content = "\n\n".join(text_parts)
        
        # Save text to file for download
        text_filename = f"mcp_{file_info.stored_filename.replace('.pdf', '')}_text_p{start_page}-{end_page}.{'md' if use_markdown else 'txt'}"
        text_path = UPLOAD_DIR / text_filename
        text_path.write_text(text_content, encoding='utf-8')
        
        # Show preview (first 1000 characters)
        preview = text_content[:1000] + "..." if len(text_content) > 1000 else text_content
        
        return Div(
            H3("Text Extracted Successfully"),
            P(f"Extracted {'Markdown' if use_markdown else 'plain text'} from pages {start_page} to {end_page}"),
            P(f"Total characters: {len(text_content)}"),
            P(A("Download Full Text", 
                href=f"/download/{text_filename}",
                download=text_filename,
                cls="button")),
            H4("Preview:"),
            Pre(preview, style="white-space: pre-wrap; word-wrap: break-word; max-height: 400px; overflow-y: auto;"),
            cls="result-area"
        )
        
    except Exception as e:
        return Div(P(f"Error extracting text: {str(e)}", cls="error"))


@rt('/download/{filename}')
async def download(filename: str):
    """Serve files for download."""
    file_path = UPLOAD_DIR / filename
    if not file_path.exists() or not file_path.is_file():
        return Response(content="File not found", status_code=404)
    
    return FileResponse(file_path)


@rt('/cleanup')
async def manual_cleanup():
    """Manual trigger for cleanup (protected endpoint)."""
    # In production, this should be protected with authentication
    # For now, it's a simple endpoint for testing
    try:
        deleted_count = await cleanup_old_files()
        return Div(
            P(f"Cleanup completed. Deleted {deleted_count} old files.", cls="success")
        )
    except Exception as e:
        return Div(
            P(f"Error during cleanup: {str(e)}", cls="error")
        )


# Background task for daily cleanup
async def daily_cleanup():
    """Run cleanup daily."""
    while True:
        await asyncio.sleep(86400)  # 24 hours
        try:
            await cleanup_old_files()
        except Exception as e:
            print(f"Error in daily cleanup: {e}")


# Start background cleanup task when the app starts
@app.on_event("startup")
async def startup_event():
    """Start background tasks on app startup."""
    asyncio.create_task(daily_cleanup())


if __name__ == "__main__":
    serve(port=8000)