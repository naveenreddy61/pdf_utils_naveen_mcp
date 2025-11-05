"""PDF processing routes."""

from typing import Optional
from pathlib import Path
import zipfile
import io
from fasthtml.common import *
from starlette.responses import StreamingResponse
from config import UPLOAD_DIR, MIN_DPI, MAX_DPI, DEFAULT_DPI
from src.web_app.core.database import get_file_info
from src.web_app.core.utils import count_tokens
from src.web_app.services import pdf_service
from src.web_app.ui.components import error_message, toc_display, image_extraction_gallery, ocr_result_display
from src.web_app.services import ocr_service


def setup_routes(app, rt):
    """Set up PDF processing routes."""
    
    @rt('/process/toc/{file_hash}')
    def process_toc(file_hash: str):
        """Extract and display table of contents."""
        try:
            file_info = get_file_info(file_hash)
            if not file_info:
                return Div(error_message("File not found."))
            
            file_path = UPLOAD_DIR / file_info.stored_filename
            
            # Extract TOC
            toc = pdf_service.extract_toc(file_path)
            return toc_display(toc)
            
        except Exception as e:
            return Div(error_message(f"Error extracting TOC: {str(e)}"))
    
    
    @rt('/extract-pages-form/{file_hash}')
    def extract_pages_form(file_hash: str):
        """Show form for page extraction."""
        file_info = get_file_info(file_hash)
        if not file_info:
            return Div(error_message("File not found."))
        
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
            file_info = get_file_info(file_hash)
            if not file_info:
                return Div(error_message("File not found."))
            
            file_path = UPLOAD_DIR / file_info.stored_filename
            
            # Validate page range
            if start_page < 1 or end_page > file_info.page_count or start_page > end_page:
                return Div(error_message("Invalid page range."))
            
            # Extract pages
            print(f"Extracting pages {start_page} to {end_page} from: {file_path}")
            print(f"Upload directory: {UPLOAD_DIR.resolve()}")
            
            output_filename = f"mcp_{file_info.stored_filename.replace('.pdf', '')}_pages_{start_page}_to_{end_page}.pdf"
            output_path = pdf_service.extract_pages(file_path, start_page, end_page, output_filename)
            
            # Verify file was created
            if output_path.exists():
                file_size = output_path.stat().st_size
                print(f"PDF saved successfully: {output_filename} ({file_size} bytes)")
            else:
                print(f"ERROR: Failed to create PDF file: {output_path}")
                return Div(error_message("Failed to create extracted PDF file."))
            
            return Div(
                H3("Pages Extracted Successfully"),
                P(f"Extracted pages {start_page} to {end_page}"),
                P(A("Download Extracted PDF", 
                    href=f"/{output_filename}",
                    download=output_filename,
                    cls="button")),
                cls="result-area"
            )
            
        except Exception as e:
            return Div(error_message(f"Error extracting pages: {str(e)}"))
    
    
    @rt('/convert-images-form/{file_hash}')
    def convert_images_form(file_hash: str):
        """Show form for image conversion."""
        file_info = get_file_info(file_hash)
        if not file_info:
            return Div(error_message("File not found."))
        
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
                                   min=str(MIN_DPI), max=str(MAX_DPI), 
                                   value=str(DEFAULT_DPI), required=True)),
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
                                    dpi: int = DEFAULT_DPI, image_format: str = "png"):
        """Convert specified pages to images."""
        try:
            file_info = get_file_info(file_hash)
            if not file_info:
                return Div(error_message("File not found."))
            
            file_path = UPLOAD_DIR / file_info.stored_filename
            
            # Validate page range
            if start_page < 1 or end_page > file_info.page_count or start_page > end_page:
                return Div(error_message("Invalid page range."))
            
            # Convert pages to images
            print(f"Converting pages {start_page} to {end_page} from: {file_path}")
            print(f"Upload directory: {UPLOAD_DIR.resolve()}")
            
            image_files = pdf_service.convert_pages_to_images(
                file_path, start_page, end_page, dpi, image_format
            )
            
            # Create image gallery
            image_elements = []
            for img_file in image_files:
                # Double-check file exists before adding to gallery
                img_path = UPLOAD_DIR / img_file
                if img_path.exists():
                    image_elements.append(
                        Div(
                            A(
                                Img(src=f"/{img_file}", cls="image-thumb"),
                                href=f"/{img_file}",
                                download=img_file
                            )
                        )
                    )
                else:
                    print(f"WARNING: Image file missing when creating gallery: {img_path}")
            
            if not image_elements:
                return Div(error_message("No image files were successfully created."))
            
            return Div(
                H3("Images Generated Successfully"),
                P(f"Converted {len(image_files)} pages to {image_format.upper()} format at {dpi} DPI"),
                Div(*image_elements, cls="image-gallery"),
                cls="result-area"
            )
            
        except Exception as e:
            return Div(error_message(f"Error converting to images: {str(e)}"))
    
    
    @rt('/extract-text-form/{file_hash}')
    def extract_text_form(file_hash: str):
        """Show form for text extraction."""
        file_info = get_file_info(file_hash)
        if not file_info:
            return Div(error_message("File not found."))
        
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
            file_info = get_file_info(file_hash)
            if not file_info:
                return Div(error_message("File not found."))
            
            file_path = UPLOAD_DIR / file_info.stored_filename
            
            # Validate page range
            if start_page < 1 or end_page > file_info.page_count or start_page > end_page:
                return Div(error_message("Invalid page range."))
            
            use_markdown = markdown == "on"
            
            # Extract text
            if use_markdown:
                text_content = pdf_service.extract_text_markdown(file_path, start_page, end_page)
            else:
                text_content = pdf_service.extract_text_plain(file_path, start_page, end_page)
            
            # Save text to file for download
            text_filename = f"mcp_{file_info.stored_filename.replace('.pdf', '')}_text_p{start_page}-{end_page}.txt"
            text_path = UPLOAD_DIR / text_filename
            
            # Debug logging
            print(f"Extracting text from pages {start_page} to {end_page} from: {file_path}")
            print(f"Upload directory: {UPLOAD_DIR.resolve()}")
            print(f"Generated text filename: {text_filename}")
            print(f"Saving text file to: {text_path.resolve()}")
            
            text_path.write_text(text_content, encoding='utf-8')
            
            # Verify file was created
            if text_path.exists():
                file_size = text_path.stat().st_size
                print(f"Text file saved successfully: {text_filename} ({file_size} bytes)")
            else:
                print(f"ERROR: Failed to create text file: {text_path}")
                return Div(error_message("Failed to create text file."))
            
            # Show full text in preview
            preview = text_content
            
            # Debug download link generation
            download_url = f"/{text_filename}"
            print(f"Creating download link with href: {download_url}")
            print(f"Download filename attribute: {text_filename}")
            
            # Generate unique ID for the preview content
            preview_id = f"preview-{file_hash}-{start_page}-{end_page}"
            
            return Div(
                H3("Text Extracted Successfully"),
                P(f"Extracted {'Markdown' if use_markdown else 'plain text'} from pages {start_page} to {end_page}"),
                P(f"Total characters: {len(text_content)}"),
                Div(
                    Button("Show Token Count", 
                           hx_post=f"/process/show-tokens/{file_hash}/{start_page}/{end_page}{'?markdown=on' if use_markdown else ''}",
                           hx_target=f"#token-count-{file_hash}-{start_page}-{end_page}",
                           cls="button",
                           style="font-size: 14px; padding: 8px 16px;"),
                    id=f"token-count-{file_hash}-{start_page}-{end_page}",
                    style="margin: 10px 0;"
                ),
                Div(
                    A("Download Full Text", 
                      href=download_url,
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
                H4("Preview:"),
                Pre(preview, id=preview_id, style="white-space: pre-wrap; word-wrap: break-word; max-height: 400px; overflow-y: auto;"),
                cls="result-area"
            )
            
        except Exception as e:
            return Div(error_message(f"Error extracting text: {str(e)}"))
    
    
    @rt('/process/show-tokens/{file_hash}/{start_page}/{end_page}')
    async def process_show_tokens(file_hash: str, start_page: int, end_page: int, 
                                 markdown: Optional[str] = None):
        """Calculate and display token count for extracted text."""
        try:
            file_info = get_file_info(file_hash)
            if not file_info:
                return P("File not found.", cls="error")
            
            file_path = UPLOAD_DIR / file_info.stored_filename
            
            # Validate page range
            if start_page < 1 or end_page > file_info.page_count or start_page > end_page:
                return P("Invalid page range.", cls="error")
            
            use_markdown = markdown == "on"
            
            # Extract the same text as in the original extraction
            if use_markdown:
                text_content = pdf_service.extract_text_markdown(file_path, start_page, end_page)
            else:
                text_content = pdf_service.extract_text_plain(file_path, start_page, end_page)

            # Calculate token count (runs in background thread to avoid blocking)
            token_count = await count_tokens(text_content)

            # Return the token count as a styled paragraph
            return P(f"Total tokens: {token_count} (using gpt-4o encoding)",
                    style="margin: 10px 0; color: #155724; font-weight: bold;")
            
        except Exception as e:
            return P(f"Error calculating tokens: {str(e)}", cls="error")
    
    
    @rt('/extract-images-form/{file_hash}')
    def extract_images_form(file_hash: str):
        """Show form for image extraction."""
        file_info = get_file_info(file_hash)
        if not file_info:
            return Div(error_message("File not found."))
        
        return Div(
            H3("Extract Images"),
            P(f"Total pages: {file_info.page_count}"),
            P("Images smaller than 25x25 pixels will be filtered out.", style="color: #666; font-size: 0.9em;"),
            P("Maximum 12 images per page (largest by area).", style="color: #666; font-size: 0.9em;"),
            Form(
                Label("Start Page:", Input(type="number", name="start_page", 
                                          min="1", max=str(file_info.page_count), 
                                          value="1", required=True)),
                Label("End Page:", Input(type="number", name="end_page", 
                                        min="1", max=str(file_info.page_count), 
                                        value=str(min(10, file_info.page_count)), required=True)),
                Button("Extract Images", type="submit"),
                hx_post=f"/process/extract-images/{file_hash}",
                hx_target="#operation-result",
                hx_indicator="#extract-spinner"
            ),
            Div(id="extract-spinner", cls="spinner", style="display: none;"),
            cls="result-area"
        )
    
    
    @rt('/process/extract-images/{file_hash}')
    async def process_extract_images(file_hash: str, start_page: int, end_page: int):
        """Extract images from specified pages."""
        try:
            file_info = get_file_info(file_hash)
            if not file_info:
                return Div(error_message("File not found."))
            
            file_path = UPLOAD_DIR / file_info.stored_filename
            
            # Validate page range
            if start_page < 1 or end_page > file_info.page_count or start_page > end_page:
                return Div(error_message("Invalid page range."))
            
            # Extract images
            print(f"Extracting images from pages {start_page} to {end_page} from: {file_path}")
            images_data = pdf_service.extract_images_from_pages(file_path, start_page, end_page)
            
            # Store images data in app context for ZIP download
            # Note: In production, consider using a cache with TTL
            if not hasattr(app, 'extracted_images_cache'):
                app.extracted_images_cache = {}
            
            cache_key = f"{file_hash}_{start_page}_{end_page}"
            app.extracted_images_cache[cache_key] = images_data
            
            # Return gallery view
            return image_extraction_gallery(images_data, file_hash, start_page, end_page)
            
        except Exception as e:
            print(f"Error extracting images: {str(e)}")
            import traceback
            traceback.print_exc()
            return Div(error_message(f"Error extracting images: {str(e)}"))
    
    
    @rt('/download-image-zip/{file_hash}/{start_page}/{end_page}')
    async def download_image_zip(file_hash: str, start_page: int, end_page: int):
        """Generate and download a ZIP file containing all extracted images."""
        try:
            # Check if images are in cache
            cache_key = f"{file_hash}_{start_page}_{end_page}"
            
            # If not in cache, extract them again
            if not hasattr(app, 'extracted_images_cache') or cache_key not in app.extracted_images_cache:
                file_info = get_file_info(file_hash)
                if not file_info:
                    return Div(error_message("File not found."))
                
                file_path = UPLOAD_DIR / file_info.stored_filename
                images_data = pdf_service.extract_images_from_pages(file_path, start_page, end_page)
            else:
                images_data = app.extracted_images_cache[cache_key]
            
            if not images_data:
                return Div(error_message("No images to download."))
            
            # Create ZIP file in memory
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                for page_num, page_images in images_data.items():
                    for img_data in page_images:
                        # Use raw_data if available, otherwise decode from base64
                        if 'raw_data' in img_data:
                            image_bytes = img_data['raw_data']
                        else:
                            # Extract base64 data and decode
                            base64_str = img_data['data'].split(',')[1]
                            import base64
                            image_bytes = base64.b64decode(base64_str)
                        
                        zip_file.writestr(img_data['filename'], image_bytes)
            
            zip_buffer.seek(0)
            
            # Return as streaming response
            return StreamingResponse(
                zip_buffer,
                media_type='application/zip',
                headers={
                    'Content-Disposition': f'attachment; filename="extracted_images_p{start_page}-{end_page}.zip"'
                }
            )
            
        except Exception as e:
            print(f"Error creating ZIP: {str(e)}")
            import traceback
            traceback.print_exc()
            return Div(error_message(f"Error creating ZIP file: {str(e)}"))
    
    
    @rt('/extract-text-llm-form/{file_hash}')
    def extract_text_llm_form(file_hash: str):
        """Show form for LLM-based text extraction with OCR."""
        file_info = get_file_info(file_hash)
        if not file_info:
            return Div(error_message("File not found."))
        
        return Div(
            H3("Extract Text with LLM OCR"),
            P(f"Total pages: {file_info.page_count}"),
            P("This feature uses AI to extract text, with special handling for mathematical content.", 
              style="color: #666; font-size: 0.9em;"),
            P("Pages with math will be processed using LLM OCR with LaTeX formatting.", 
              style="color: #666; font-size: 0.9em;"),
            Form(
                Label("Start Page:", Input(type="number", name="start_page", 
                                          min="1", max=str(file_info.page_count), 
                                          value="1", required=True)),
                Label("End Page:", Input(type="number", name="end_page", 
                                        min="1", max=str(file_info.page_count), 
                                        value=str(min(5, file_info.page_count)), required=True)),
                Button("Extract with OCR", type="submit"),
                hx_post=f"/process/extract-text-llm/{file_hash}",
                hx_target="#operation-result",
                hx_indicator="#ocr-spinner"
            ),
            Div(id="ocr-spinner", cls="spinner", style="display: none;"),
            cls="result-area"
        )
    
    
    @rt('/process/extract-text-llm/{file_hash}')
    async def process_extract_text_llm(file_hash: str, start_page: int, end_page: int):
        """Extract text using async LLM OCR with caching and batch processing."""
        try:
            file_info = get_file_info(file_hash)
            if not file_info:
                return Div(error_message("File not found."))
            
            file_path = UPLOAD_DIR / file_info.stored_filename
            
            # Validate page range
            if start_page < 1 or end_page > file_info.page_count or start_page > end_page:
                return Div(error_message("Invalid page range."))
            
            # Store progress messages
            progress_messages = []
            
            def progress_callback(message: str):
                progress_messages.append(message)
                print(f"OCR Progress: {message}")
            
            # Process pages with async OCR
            print(f"Starting async LLM OCR extraction for pages {start_page} to {end_page} from: {file_path}")
            results = await ocr_service.process_pages_async_batch(
                file_path, 
                start_page, 
                end_page,
                progress_callback=progress_callback
            )
            
            # Add progress messages to results for display
            results["progress_messages"] = progress_messages
            
            # Save text to file for download
            cache_info = f"_cache{results['cache_hit_rate']:.0f}pct" if results.get('cache_hit_rate', 0) > 0 else ""
            text_filename = f"mcp_{file_info.stored_filename.replace('.pdf', '')}_async_ocr_p{start_page}-{end_page}{cache_info}.txt"
            text_path = UPLOAD_DIR / text_filename
            text_path.write_text(results["full_text"], encoding='utf-8')
            
            # Return the formatted result display
            return ocr_result_display(
                results=results,
                file_hash=file_hash,
                start_page=start_page,
                end_page=end_page,
                text_filename=text_filename
            )
            
        except Exception as e:
            print(f"Error in async LLM OCR extraction: {str(e)}")
            import traceback
            traceback.print_exc()
            return Div(error_message(f"Error extracting text with LLM: {str(e)}"))