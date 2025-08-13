"""UI components for the web application."""

from fasthtml.common import *
from config import MAX_FILE_SIZE_MB


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


def file_info_display(file_info, is_existing=False):
    """Display file information."""
    return Div(
        H3("File Information"),
        P(f"Original name: {file_info.original_filename}"),
        P(f"Size: {file_info.file_size / 1024 / 1024:.2f} MB"),
        P(f"Pages: {file_info.page_count}"),
        P("File uploaded successfully!" if not is_existing else "File already exists, using cached version.", 
          cls="success" if not is_existing else "warning"),
        cls="file-info"
    )


def operation_buttons(file_hash):
    """Display operation buttons."""
    return Div(
        H3("Available Operations"),
        # First row of buttons
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
        ),
        # Second row with Extract Images button
        Div(
            Button("Extract Images", 
                   hx_get=f"/extract-images-form/{file_hash}",
                   hx_target="#operation-result",
                   cls="button",
                   style="background-color: #28a745;"),
            
            Button("Extract Text LLM OCR", 
                   hx_get=f"/extract-text-llm-form/{file_hash}",
                   hx_target="#operation-result",
                   cls="button",
                   style="background-color: #6610f2;"),
            
            cls="operation-buttons",
            style="margin-top: 10px;"
        )
    )


def toc_display(toc):
    """Display table of contents."""
    if not toc:
        return Div(
            H3("Table of Contents"),
            P("This PDF has no table of contents.", cls="warning"),
            cls="result-area"
        )
    
    # Create a structured list
    toc_list_items = []
    for level, title, page in toc:
        # Apply different styles based on level
        style = f"list-style: none; padding: 5px 0; padding-left: {level * 30}px; border-bottom: 1px solid #eee;"
        if level == 0:
            style += " font-weight: bold; font-size: 1.1em;"
        
        toc_list_items.append(
            Li(
                Span(title, style="flex-grow: 1;"),
                Span(f"Page {page}", style="color: #666; margin-left: 10px;"),
                style=style + " display: flex; justify-content: space-between; align-items: center;"
            )
        )
    
    return Div(
        H3("Table of Contents"),
        Ul(
            *toc_list_items,
            style="margin: 0; padding: 0;"
        ),
        cls="result-area"
    )


def error_message(message):
    """Display an error message."""
    return P(message, cls="error")


def success_message(message):
    """Display a success message."""
    return P(message, cls="success")


def warning_message(message):
    """Display a warning message."""
    return P(message, cls="warning")


def image_extraction_gallery(images_data, file_hash, start_page, end_page):
    """Display extracted images in a gallery grid."""
    if not images_data:
        return Div(
            H3("No Images Found"),
            P("No images were found in the specified page range.", cls="warning"),
            cls="result-area"
        )
    
    # Create gallery elements
    gallery_elements = []
    total_images = 0
    
    for page_num in sorted(images_data.keys()):
        page_images = images_data[page_num]
        if not page_images:
            continue
            
        # Add page separator
        gallery_elements.append(
            Div(
                H4(f"Page {page_num}", style="margin: 20px 0 10px 0; clear: both;"),
                cls="page-separator"
            )
        )
        
        # Create image grid for this page
        image_items = []
        for img_data in page_images:
            total_images += 1
            # Create downloadable image element
            image_items.append(
                Div(
                    A(
                        Img(
                            src=img_data['data'],
                            alt=img_data['filename'],
                            cls="image-thumbnail",
                            style="width: 300px; height: 300px; object-fit: contain; border: 1px solid #ddd; cursor: pointer;"
                        ),
                        href=img_data['data'],
                        download=img_data['filename'],
                        title=f"Click to download {img_data['filename']}"
                    ),
                    cls="image-item"
                )
            )
        
        # Add image grid for this page
        gallery_elements.append(
            Div(
                *image_items,
                cls="image-extraction-grid",
                style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin-bottom: 20px;"
            )
        )
    
    # Create the complete gallery
    return Div(
        H3("Extracted Images"),
        P(f"Found {total_images} images from pages {start_page} to {end_page}"),
        P("Click on any image to download it", style="color: #666; font-style: italic;"),
        
        # Download all button
        Div(
            Button(
                "Download All as ZIP",
                onclick=f"""
                    this.textContent='Preparing ZIP...'; 
                    this.disabled=true;
                    window.location.href='/download-image-zip/{file_hash}/{start_page}/{end_page}';
                    setTimeout(() => {{
                        this.textContent='Download All as ZIP';
                        this.disabled=false;
                    }}, 2000);
                """,
                cls="button",
                style="background-color: #007bff; margin: 15px 0;"
            ),
            style="margin: 20px 0;"
        ),
        
        # Image gallery
        Div(
            *gallery_elements,
            cls="image-gallery-container"
        ),
        
        cls="result-area"
    )


def ocr_result_display(results, file_hash, start_page, end_page, text_filename):
    """Display OCR extraction results with token usage and processing details."""
    # Generate unique ID for the preview content
    preview_id = f"ocr-preview-{file_hash}-{start_page}-{end_page}"
    
    # Create processing details display
    page_details = []
    for detail in results["processing_details"]:
        method_color = "#28a745" if detail["method"].startswith("LLM") else "#6c757d"
        page_details.append(
            Li(
                f"Page {detail['page']}: {detail['method']}",
                style=f"color: {method_color}; padding: 2px 0;"
            )
        )
    
    return Div(
        H3("Text Extracted with LLM OCR"),
        
        # Summary section
        Div(
            P(results["summary"], style="font-weight: bold; color: #155724;"),
            cls="alert",
            style="background-color: #d4edda; border: 1px solid #c3e6cb; padding: 10px; border-radius: 4px; margin-bottom: 15px;"
        ),
        
        # Token usage section
        Div(
            H4("Token Usage", style="margin-bottom: 10px;"),
            P(f"Input tokens: {results['total_input_tokens']:,}", style="margin: 5px 0;"),
            P(f"Output tokens: {results['total_output_tokens']:,}", style="margin: 5px 0;"),
            P(f"Total tokens: {results['total_input_tokens'] + results['total_output_tokens']:,}", 
              style="margin: 5px 0; font-weight: bold;"),
            cls="token-usage",
            style="background-color: #f8f9fa; padding: 15px; border-radius: 4px; margin-bottom: 15px;"
        ),
        
        # Processing details
        Div(
            H4("Processing Details", style="margin-bottom: 10px;"),
            Ul(*page_details, style="list-style-type: none; padding-left: 0;"),
            cls="processing-details",
            style="background-color: #f8f9fa; padding: 15px; border-radius: 4px; margin-bottom: 15px;"
        ),
        
        # Text info
        P(f"Total characters: {len(results['full_text'])}"),
        
        # Action buttons
        Div(
            A("Download Full Text", 
              href=f"/{text_filename}",
              download=text_filename,
              cls="button",
              style="margin-right: 10px;"),
            Button("Copy to Clipboard", 
                   onclick=f"""
                       const text = document.getElementById('{preview_id}').textContent;
                       navigator.clipboard.writeText(text).then(() => {{
                           this.textContent = 'Copied!';
                           this.style.backgroundColor = '#28a745';
                           setTimeout(() => {{
                               this.textContent = 'Copy to Clipboard';
                               this.style.backgroundColor = '#007bff';
                           }}, 2000);
                       }}).catch(err => {{
                           console.error('Failed to copy: ', err);
                           this.textContent = 'Copy failed';
                           this.style.backgroundColor = '#dc3545';
                       }});
                   """,
                   cls="button"),
            style="display: flex; align-items: center; margin: 1rem 0;"
        ),
        
        # Text preview
        H4("Preview:"),
        Pre(results["full_text"], 
            id=preview_id, 
            style="white-space: pre-wrap; word-wrap: break-word; max-height: 400px; overflow-y: auto; background-color: #f8f9fa; padding: 15px; border-radius: 4px;"),
        
        cls="result-area"
    )