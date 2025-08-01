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