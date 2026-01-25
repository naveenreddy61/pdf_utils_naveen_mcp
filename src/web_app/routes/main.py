"""Main routes for the web application."""

from datetime import datetime
from fasthtml.common import *
from starlette.requests import Request
from pdf_utils.config import UPLOAD_DIR, MAX_FILE_SIZE_BYTES, MAX_FILE_SIZE_MB, ALLOWED_EXTENSIONS
from web_app.core.database import (
    FileRecord, get_file_info, update_last_accessed, insert_file_record
)
from web_app.core.utils import calculate_file_hash, sanitize_filename
from web_app.services.pdf_service import get_page_count
from web_app.ui.components import (
    upload_form, page_with_result, file_info_display, 
    operation_buttons, error_message
)


def setup_routes(app, rt):
    """Set up main routes for the application."""
    
    @rt('/')
    def index():
        """Main page with file upload form."""
        return Titled("PDF & Image Utilities",
            Div(
                H2("PDF & Image Processing Tools"),
                P("Upload a PDF or image file to use various processing tools. Files are kept for 30 days."),
                P(f"Maximum file size: {MAX_FILE_SIZE_MB}MB"),
                P("Supported formats: PDF, JPG, JPEG, PNG, WEBP", style="color: #666; font-style: italic;"),

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
                    error_message("Error: No file was uploaded.")
                )
            
            # Check if it's a valid file upload
            if not hasattr(pdf_file, 'filename'):
                return page_with_result(
                    error_message(f"Error: Invalid file upload. Received type: {type(pdf_file)}")
                )
            
            # Check file extension and determine file type
            filename_lower = pdf_file.filename.lower()
            if filename_lower.endswith('.pdf'):
                file_type = 'pdf'
            elif any(filename_lower.endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.webp']):
                file_type = 'image'
            else:
                return page_with_result(
                    error_message("Error: Only PDF and image files (JPG, JPEG, PNG, WEBP) are allowed.")
                )
            
            # Read file content
            print(f"Reading file: {pdf_file.filename}")
            content = await pdf_file.read()
            print(f"File size: {len(content)} bytes")
            
            # Check file size
            if len(content) > MAX_FILE_SIZE_BYTES:
                return page_with_result(
                    error_message(f"Error: File size exceeds {MAX_FILE_SIZE_MB}MB limit.")
                )
            
            # Calculate hash
            file_hash = calculate_file_hash(content)
            
            # Check if file already exists
            existing = get_file_info(file_hash)
            
            if existing:
                # Update last accessed time
                update_last_accessed(file_hash)
                file_info = existing
                is_existing = True
            else:
                # Save new file
                safe_filename = sanitize_filename(pdf_file.filename)
                stored_filename = f"{file_hash[:8]}_{safe_filename}"
                file_path = UPLOAD_DIR / stored_filename
                
                print(f"Saving file to: {file_path}")
                file_path.write_bytes(content)
                print(f"File saved successfully")

                # Get file info based on type
                if file_type == 'pdf':
                    page_count = get_page_count(file_path)
                else:  # image
                    page_count = 1  # Images are treated as single page

                # Store in database
                file_info = FileRecord(
                    file_hash=file_hash,
                    original_filename=pdf_file.filename,
                    stored_filename=stored_filename,
                    file_size=len(content),
                    page_count=page_count,
                    file_type=file_type,
                    upload_date=datetime.now().isoformat(),
                    last_accessed=datetime.now().isoformat()
                )
                insert_file_record(file_info)
                is_existing = False
            
            # Return file info and operation buttons
            return page_with_result(
                Div(
                    file_info_display(file_info, is_existing),
                    operation_buttons(file_hash, file_info.file_type),
                    Div(id="operation-result")
                )
            )
            
        except Exception as e:
            print(f"Upload error: {str(e)}")
            import traceback
            traceback.print_exc()
            return page_with_result(
                error_message(f"Error uploading file: {str(e)}")
            )