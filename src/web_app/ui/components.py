"""UI components for the web application."""

from fasthtml.common import *
from config import MAX_FILE_SIZE_MB, GCS_BUCKET_NAME


def upload_form():
    """Return the upload form component.

    When GCS is configured the form uses a JavaScript-driven direct-upload flow
    that bypasses Cloudflare entirely.  Otherwise it falls back to a plain
    multipart POST to /upload.
    """
    if GCS_BUCKET_NAME:
        return _gcs_upload_form()
    return _local_upload_form()


def _local_upload_form():
    """Classic multipart upload (no GCS)."""
    return Form(
        Input(type="file", name="pdf_file", accept=".pdf,.jpg,.jpeg,.png,.webp",
              onchange="this.form.submit()",
              style="margin-bottom: 1rem;"),
        method="post",
        action="/upload",
        enctype="multipart/form-data",
    )


def _gcs_upload_form():
    """Direct-to-GCS upload with a progress bar.

    Flow:
      1. User picks file → JS asks server for a signed PUT URL.
      2. JS uploads directly to GCS (no Cloudflare proxy).
      3. JS notifies server (/api/confirm-upload) to pull the file and register it.
      4. Server returns the usual HTMX HTML fragment into #upload-result.
    """
    js = """
(function () {
  var input = document.getElementById('gcs-file-input');
  if (!input) return;

  input.addEventListener('change', function () {
    var file = input.files[0];
    if (!file) return;

    var bar        = document.getElementById('upload-progress-bar');
    var barWrap    = document.getElementById('upload-progress-wrap');
    var statusMsg  = document.getElementById('upload-status-msg');
    var result     = document.getElementById('upload-result');

    function setStatus(msg) { statusMsg.textContent = msg; }
    function setProgress(pct) {
      bar.style.width = pct + '%';
      bar.textContent = pct + '%';
    }

    barWrap.style.display = 'block';
    setProgress(0);
    setStatus('Requesting upload URL…');
    result.innerHTML = '';

    // Step 1 – get signed URL from server
    fetch('/api/request-upload', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        filename: file.name,
        size: file.size,
        content_type: file.type || 'application/octet-stream'
      })
    })
    .then(function (r) { return r.json(); })
    .then(function (data) {
      if (data.error) { setStatus('Error: ' + data.error); barWrap.style.display='none'; return; }

      // Step 2 – PUT directly to GCS
      setStatus('Uploading to cloud storage…');
      var xhr = new XMLHttpRequest();
      xhr.open('PUT', data.signed_url, true);
      xhr.setRequestHeader('Content-Type', data.content_type);

      xhr.upload.onprogress = function (e) {
        if (e.lengthComputable) setProgress(Math.round(e.loaded / e.total * 90));
      };

      xhr.onload = function () {
        if (xhr.status < 200 || xhr.status >= 300) {
          setStatus('Upload to GCS failed (HTTP ' + xhr.status + ').');
          barWrap.style.display = 'none';
          return;
        }
        // Step 3 – tell server to pull the file
        setProgress(92);
        setStatus('Processing file…');
        fetch('/api/confirm-upload', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({
            gcs_object_name: data.gcs_object_name,
            original_filename: file.name
          })
        })
        .then(function (r) { return r.text(); })
        .then(function (html) {
          setProgress(100);
          setStatus('Done!');
          result.innerHTML = html;
          // Let htmx process any hx-* attributes in the injected HTML
          if (window.htmx) htmx.process(result);
          setTimeout(function () { barWrap.style.display = 'none'; setProgress(0); }, 1500);
        })
        .catch(function (err) {
          setStatus('Server error: ' + err);
          barWrap.style.display = 'none';
        });
      };

      xhr.onerror = function () {
        setStatus('Network error during upload.');
        barWrap.style.display = 'none';
      };

      xhr.send(file);
    })
    .catch(function (err) {
      setStatus('Could not reach server: ' + err);
      barWrap.style.display = 'none';
    });
  });
})();
"""
    return Div(
        # File picker
        Input(
            type="file",
            id="gcs-file-input",
            accept=".pdf,.jpg,.jpeg,.png,.webp",
            style="margin-bottom: 0.75rem; display: block;",
        ),
        # Progress bar (hidden until upload starts)
        Div(
            Div(
                id="upload-progress-bar",
                style=(
                    "width:0%; height:100%; background:#007bff; color:#fff;"
                    " text-align:center; line-height:22px; font-size:0.8rem;"
                    " transition:width 0.2s ease; border-radius:4px;"
                ),
            ),
            id="upload-progress-wrap",
            style=(
                "display:none; width:100%; height:22px; background:#e9ecef;"
                " border-radius:4px; margin-bottom:0.5rem; overflow:hidden;"
            ),
        ),
        # Status text
        Span(id="upload-status-msg", style="font-size:0.85rem; color:#555;"),
        # Inline script (runs once after DOM insertion)
        Script(js),
    )


def page_with_result(result_content):
    """Return a full page with upload form and result content."""
    return Titled("PDF & Image Utilities",
        Div(
            H2("PDF & Image Processing Tools"),
            P("Upload a PDF or image file to use various processing tools. Files are kept for 30 days."),
            P(f"Maximum file size: {MAX_FILE_SIZE_MB}MB"),
            P("Supported formats: PDF, JPG, JPEG, PNG, WEBP", style="color: #666; font-style: italic;"),
            upload_form(),
            result_content,
            cls="container"
        )
    )


def file_info_display(file_info, is_existing=False):
    """Display file information."""
    file_type_display = "PDF Document" if file_info.file_type == 'pdf' else "Image File"

    info_items = [
        H3("File Information"),
        P(f"Type: {file_type_display}"),
        P(f"Original name: {file_info.original_filename}"),
        P(f"Size: {file_info.file_size / 1024 / 1024:.2f} MB"),
    ]

    # Only show pages for PDFs
    if file_info.file_type == 'pdf':
        info_items.append(P(f"Pages: {file_info.page_count}"))

    info_items.append(
        P("File uploaded successfully!" if not is_existing else "File already exists, using cached version.",
          cls="success" if not is_existing else "warning")
    )

    return Div(*info_items, cls="file-info")


def operation_buttons(file_hash, file_type='pdf'):
    """Display operation buttons based on file type."""
    if file_type == 'image':
        # Only show OCR for images
        return Div(
            H3("Available Operations"),
            P("Image files support OCR text extraction only.",
              style="color: #666; font-style: italic; margin-bottom: 15px;"),
            Div(
                Button("Extract Text LLM OCR",
                       hx_get=f"/extract-text-llm-image/{file_hash}",
                       hx_target="#operation-result",
                       cls="button",
                       style="background-color: #6610f2;"),
                cls="operation-buttons"
            )
        )
    else:
        # Show all PDF operations
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
    """Display async OCR extraction results with caching metrics and processing details."""
    # Generate unique ID for the preview content
    preview_id = f"ocr-preview-{file_hash}-{start_page}-{end_page}"
    
    # Create detailed page statistics
    cached_pages = results.get("cached_pages", [])
    llm_pages = results.get("llm_pages", [])
    fallback_pages = results.get("fallback_pages", [])
    
    # Calculate performance metrics
    pages_processed = results.get("pages_processed", 0)
    cache_hit_rate = (len(cached_pages) / pages_processed) * 100 if pages_processed > 0 else 0
    processing_time = results.get("processing_time", 0)
    
    # Create processing details display with icons and colors
    page_details = []
    
    # Check if we have the old processing_details format or new page lists format
    if "processing_details" in results:
        # Old format - use existing logic
        for detail in results["processing_details"]:
            if detail["method"] == "Cached":
                icon = "💾"
                method_color = "#17a2b8"  # Info blue
            elif detail["method"] == "LLM OCR":
                icon = "🤖"
                method_color = "#28a745"  # Success green
            elif detail["method"] == "PyMuPDF Fallback":
                icon = "📄"
                method_color = "#fd7e14"  # Warning orange
            else:
                icon = "❌"
                method_color = "#dc3545"  # Danger red
            
            retry_text = f" (retry {detail['retry_count']})" if detail.get('retry_count', 0) > 0 else ""
            token_info = f" | {detail['tokens']['input']+detail['tokens']['output']} tokens" if detail['tokens']['input']+detail['tokens']['output'] > 0 else ""
            
            page_details.append(
                Li(
                    f"{icon} Page {detail['page']}: {detail['method']}{retry_text}{token_info}",
                    style=f"color: {method_color}; padding: 2px 0; font-size: 0.9em;"
                )
            )
    else:
        # New format - use page lists
        # Add cached pages
        for page in cached_pages:
            page_details.append(
                Li(
                    f"💾 Page {page}: Cached",
                    style="color: #17a2b8; padding: 2px 0; font-size: 0.9em;"
                )
            )
        
        # Add LLM processed pages
        for page in llm_pages:
            page_details.append(
                Li(
                    f"🤖 Page {page}: LLM OCR",
                    style="color: #28a745; padding: 2px 0; font-size: 0.9em;"
                )
            )
        
        # Add fallback pages
        for page in fallback_pages:
            page_details.append(
                Li(
                    f"📄 Page {page}: PyMuPDF Fallback",
                    style="color: #fd7e14; padding: 2px 0; font-size: 0.9em;"
                )
            )
    
    # Progress messages display
    progress_section = []
    if results.get("progress_messages"):
        progress_section = [
            Div(
                H4("Processing Progress", style="margin-bottom: 10px;"),
                Ul(
                    *[Li(msg, style="padding: 2px 0; font-size: 0.9em; color: #6c757d;") 
                      for msg in results["progress_messages"]],
                    style="list-style-type: none; padding-left: 0;"
                ),
                cls="progress-messages",
                style="background-color: #f8f9fa; padding: 15px; border-radius: 4px; margin-bottom: 15px;"
            )
        ]
    
    return Div(
        H3("✨ Async OCR Processing Complete"),
        
        # Summary section with performance highlights
        Div(
            P(results["summary"], style="font-weight: bold; color: #155724; margin-bottom: 10px;"),
            Div(
                f"⚡ Processed in {processing_time:.1f}s | " +
                f"💾 {cache_hit_rate:.1f}% cache hit rate | " + 
                f"🔄 {results.get('retry_count', 0)} retries",
                style="font-size: 0.9em; color: #6c757d;"
            ),
            cls="alert",
            style="background-color: #d4edda; border: 1px solid #c3e6cb; padding: 15px; border-radius: 4px; margin-bottom: 15px;"
        ),
        
        # Performance metrics section
        Div(
            H4("Performance Metrics", style="margin-bottom: 10px;"),
            Div(
                # Cache performance
                Div(
                    Div("💾 Cache Performance", style="font-weight: bold; margin-bottom: 5px;"),
                    P(f"Hit rate: {cache_hit_rate:.1f}% ({len(cached_pages)} of {results.get('pages_processed', 0)} pages)", style="margin: 2px 0;"),
                    P(f"Fresh LLM calls: {len(llm_pages)} pages", style="margin: 2px 0;"),
                    P(f"Fallback used: {len(fallback_pages)} pages", style="margin: 2px 0;"),
                    style="flex: 1; margin-right: 15px;"
                ),
                # Token usage
                Div(
                    Div("🪙 Token Usage", style="font-weight: bold; margin-bottom: 5px;"),
                    P(f"Input tokens: {results['total_input_tokens']:,}", style="margin: 2px 0;"),
                    P(f"Output tokens: {results['total_output_tokens']:,}", style="margin: 2px 0;"),
                    P(f"Total tokens: {results['total_input_tokens'] + results['total_output_tokens']:,}", 
                      style="margin: 2px 0; font-weight: bold;"),
                    style="flex: 1;"
                ),
                style="display: flex; align-items: flex-start;"
            ),
            cls="metrics",
            style="background-color: #f8f9fa; padding: 15px; border-radius: 4px; margin-bottom: 15px;"
        ),
        
        # Progress messages (if any)
        *progress_section,
        
        # Processing details
        Div(
            H4("Page-by-Page Details", style="margin-bottom: 10px;"),
            Ul(*page_details, style="list-style-type: none; padding-left: 0; max-height: 200px; overflow-y: auto;"),
            cls="processing-details",
            style="background-color: #f8f9fa; padding: 15px; border-radius: 4px; margin-bottom: 15px;"
        ),
        
        # Text info and failed pages (if any)
        Div(
            P(f"📄 Total characters: {len(results['full_text']):,}"),
            *([P(f"⚠️ {len(results.get('failed_pages', []))} pages failed completely", 
                 style="color: #dc3545; font-weight: bold;")] 
              if results.get('failed_pages') else []),
            style="margin-bottom: 15px;"
        ),
        
        # Action buttons
        Div(
            A("📥 Download Full Text", 
              href=f"/{text_filename}",
              download=text_filename,
              cls="button",
              style="margin-right: 10px; background-color: #28a745;"),
            Button("📋 Copy to Clipboard", 
                   onclick=f"""
                       const text = document.getElementById('{preview_id}').textContent;
                       navigator.clipboard.writeText(text).then(() => {{
                           this.textContent = '✅ Copied!';
                           this.style.backgroundColor = '#28a745';
                           setTimeout(() => {{
                               this.textContent = '📋 Copy to Clipboard';
                               this.style.backgroundColor = '#007bff';
                           }}, 2000);
                       }}).catch(err => {{
                           console.error('Failed to copy: ', err);
                           this.textContent = '❌ Copy failed';
                           this.style.backgroundColor = '#dc3545';
                       }});
                   """,
                   cls="button"),
            style="display: flex; align-items: center; margin: 1rem 0;"
        ),
        
        # Text preview
        H4("📖 Text Preview:"),
        Pre(results["full_text"], 
            id=preview_id, 
            style="white-space: pre-wrap; word-wrap: break-word; max-height: 400px; overflow-y: auto; background-color: #f8f9fa; padding: 15px; border-radius: 4px; border-left: 4px solid #007bff;"),
        
        cls="result-area"
    )