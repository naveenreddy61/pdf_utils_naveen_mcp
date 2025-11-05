"""Main routes for the web application."""

import os
from datetime import datetime
from fasthtml.common import *
from starlette.requests import Request
from google import genai
from config import UPLOAD_DIR, MAX_FILE_SIZE_BYTES, MAX_FILE_SIZE_MB, ALLOWED_EXTENSIONS
from src.web_app.core.database import (
    FileRecord, get_file_info, update_last_accessed, insert_file_record
)
from src.web_app.core.session_settings import get_session_settings, update_session_settings, save_available_models
from src.web_app.core.utils import calculate_file_hash, sanitize_filename
from src.web_app.services.pdf_service import get_page_count
from src.web_app.ui.components import (
    upload_form, page_with_result, file_info_display,
    operation_buttons, error_message
)


def setup_routes(app, rt):
    """Set up main routes for the application."""
    
    @rt('/')
    def index():
        """Main page with file upload form."""
        return Titled("PDF Utilities",
            Div(
                # Header with settings button
                Div(
                    H2("PDF Processing Tools", style="display: inline-block; margin-right: 20px;"),
                    A("⚙️ Settings",
                      href="/settings",
                      cls="button",
                      style="background-color: #6c757d; padding: 8px 16px; text-decoration: none; display: inline-block; font-size: 0.9em;"),
                    style="margin-bottom: 1rem; display: flex; align-items: center;"
                ),
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
                    error_message("Error: No file was uploaded.")
                )
            
            # Check if it's a valid file upload
            if not hasattr(pdf_file, 'filename'):
                return page_with_result(
                    error_message(f"Error: Invalid file upload. Received type: {type(pdf_file)}")
                )
            
            # Check file extension
            if not pdf_file.filename.lower().endswith('.pdf'):
                return page_with_result(
                    error_message("Error: Only PDF files are allowed.")
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
                
                # Get PDF info
                page_count = get_page_count(file_path)
                
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
                insert_file_record(file_info)
                is_existing = False
            
            # Return file info and operation buttons
            return page_with_result(
                Div(
                    file_info_display(file_info, is_existing),
                    operation_buttons(file_hash),
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


    @rt('/settings')
    def settings_page(session):
        """Settings page for configuring Gemini API and models (session-based)."""
        user_settings = get_session_settings(session)
        has_env_key = bool(os.getenv('GOOGLE_API_KEY') or os.getenv('GEMINI_API_KEY'))

        return Titled("Settings - PDF Utilities",
            Div(
                # Header
                Div(
                    H2("Settings", style="display: inline-block; margin-right: 20px;"),
                    A("← Back to Home",
                      href="/",
                      cls="button",
                      style="background-color: #6c757d; padding: 8px 16px; text-decoration: none; display: inline-block; font-size: 0.9em;"),
                    style="margin-bottom: 1rem; display: flex; align-items: center;"
                ),

                # Settings form
                Div(
                    H3("Gemini API Configuration"),

                    # Session notice
                    Div(
                        P("⚠️ Note: Settings are stored in your session only and will be lost when you close the browser.",
                          style="color: #856404; margin: 0;"),
                        style="background-color: #fff3cd; border: 1px solid #ffeaa7; padding: 10px; border-radius: 4px; margin-bottom: 15px;"
                    ),

                    # API Key status
                    Div(
                        P("API Key Status:", style="font-weight: bold; margin-bottom: 5px;"),
                        P(
                            f"✅ Environment variable {'GOOGLE_API_KEY' if os.getenv('GOOGLE_API_KEY') else 'GEMINI_API_KEY'} is set" if has_env_key else "❌ No environment variable set",
                            style=f"color: {'#28a745' if has_env_key else '#dc3545'}; margin-bottom: 10px;"
                        ),
                        P(
                            f"✅ Session API key configured" if user_settings['gemini_api_key'] else "ℹ️ No session API key (using environment variable)" if has_env_key else "⚠️ No API key configured",
                            style=f"color: {'#28a745' if user_settings['gemini_api_key'] else '#17a2b8' if has_env_key else '#ffc107'};"
                        ),
                        style="background-color: #f8f9fa; padding: 15px; border-radius: 4px; margin-bottom: 20px;"
                    ),

                    # API Key input
                    Form(
                        Div(
                            Label("Gemini API Key (optional - session only)", _for="api-key-input", style="display: block; margin-bottom: 5px; font-weight: bold;"),
                            P("Leave empty to use environment variable. Get your API key from ",
                              A("Google AI Studio", href="https://aistudio.google.com/app/apikey", target="_blank"),
                              style="font-size: 0.9em; color: #6c757d; margin-bottom: 10px;"),
                            Input(
                                type="password",
                                id="api-key-input",
                                name="gemini_api_key",
                                placeholder="Enter your Gemini API key (session only)",
                                value="••••••••" if user_settings['gemini_api_key'] else "",
                                style="width: 100%; padding: 10px; margin-bottom: 15px; border: 1px solid #ccc; border-radius: 4px;"
                            ),
                            style="margin-bottom: 20px;"
                        ),

                        # Model selection
                        Div(
                            Label("OCR Model", _for="model-select", style="display: block; margin-bottom: 5px; font-weight: bold;"),
                            P("Select the Gemini model to use for OCR processing",
                              style="font-size: 0.9em; color: #6c757d; margin-bottom: 10px;"),
                            Div(
                                Select(
                                    # If we have available models in session, populate dropdown
                                    *([Option(
                                        f"{model['display_name']} ({model['name']})",
                                        value=model['name'],
                                        selected=(model['name'] == user_settings['ocr_model'])
                                    ) for model in user_settings['available_models']]
                                    if user_settings['available_models']
                                    else [Option(user_settings['ocr_model'], value=user_settings['ocr_model'], selected=True)]),
                                    id="model-select",
                                    name="ocr_model",
                                    style="width: 100%; padding: 10px; margin-bottom: 10px; border: 1px solid #ccc; border-radius: 4px;"
                                ),
                                id="model-select-container"
                            ),
                            Button(
                                "🔄 Fetch Available Models",
                                hx_post="/fetch-models",
                                hx_target="#model-select-container",
                                hx_swap="innerHTML",
                                hx_indicator=".htmx-indicator",
                                cls="button",
                                style="background-color: #17a2b8; margin-bottom: 15px;"
                            ),
                            Span("⏳ Fetching...", cls="htmx-indicator", style="display: none; margin-left: 10px; color: #17a2b8;"),
                            Div(
                                P(f"ℹ️ {len(user_settings['available_models'])} models loaded from session",
                                  style="color: #28a745; font-size: 0.9em; margin: 0;")
                                if user_settings['available_models']
                                else P("Click 'Fetch Available Models' to populate the dropdown",
                                      style="color: #6c757d; font-size: 0.9em; margin: 0;"),
                                id="model-status"
                            ),
                            style="margin-bottom: 20px;"
                        ),

                        # Save button
                        Button(
                            "💾 Save Settings",
                            hx_post="/save-settings",
                            hx_include="#api-key-input, #model-select",
                            hx_target="#save-status",
                            cls="button",
                            style="background-color: #28a745; padding: 12px 24px; font-size: 1em;"
                        ),

                        Div(id="save-status", style="margin-top: 15px;"),

                        id="settings-form"
                    ),

                    cls="settings-container",
                    style="max-width: 800px;"
                ),

                cls="container"
            )
        )


    @rt('/fetch-models', methods=['POST'])
    async def fetch_models(session):
        """Fetch available Gemini models and update the dropdown."""
        try:
            # Get API key from session or environment
            user_settings = get_session_settings(session)
            api_key = user_settings['gemini_api_key'] or os.getenv('GOOGLE_API_KEY') or os.getenv('GEMINI_API_KEY')

            if not api_key:
                return Div(
                    P("❌ Error: No API key configured. Please set an API key first.",
                      style="color: #dc3545; font-size: 0.9em; margin: 0;")
                )

            # Initialize client with user's API key
            client = genai.Client(api_key=api_key)

            # Fetch models
            models_list = []
            models = client.models.list()

            # Iterate directly over the Pager object
            for model in models:
                # Only include models that support generateContent
                if "generateContent" in model.supported_actions:
                    models_list.append({
                        "name": model.name,
                        "display_name": model.display_name,
                        "description": model.description or "",
                        "input_token_limit": model.input_token_limit,
                        "output_token_limit": model.output_token_limit
                    })

            # Save models to session
            save_available_models(session, models_list)

            # Get current selected model
            current_model = user_settings['ocr_model']

            # Return updated dropdown HTML with success indicator
            return Div(
                Select(
                    *[Option(
                        f"{model['display_name']} ({model['name']})",
                        value=model['name'],
                        selected=(model['name'] == current_model)
                    ) for model in models_list],
                    id="model-select",
                    name="ocr_model",
                    style="width: 100%; padding: 10px; margin-bottom: 10px; border: 1px solid #ccc; border-radius: 4px;"
                ),
                P(f"✅ Found {len(models_list)} models",
                  style="color: #28a745; font-size: 0.9em; margin-top: 5px;",
                  hx_swap_oob="true",
                  id="model-status")
            )

        except Exception as e:
            return Div(
                Select(
                    Option(user_settings['ocr_model'], value=user_settings['ocr_model'], selected=True),
                    id="model-select",
                    name="ocr_model",
                    style="width: 100%; padding: 10px; margin-bottom: 10px; border: 1px solid #ccc; border-radius: 4px;"
                ),
                P(f"❌ Error: {str(e)}",
                  style="color: #dc3545; font-size: 0.9em; margin-top: 5px;",
                  hx_swap_oob="true",
                  id="model-status")
            )


    @rt('/save-settings', methods=['POST'])
    async def save_settings_route(request: Request, session):
        """Save settings to session."""
        try:
            form = await request.form()

            # Get values from form
            api_key = form.get('gemini_api_key', '').strip()
            ocr_model = form.get('ocr_model', '').strip()

            # Handle masked API key (don't update if still masked)
            if api_key == '••••••••':
                api_key = None

            # Update session settings
            update_session_settings(
                session,
                gemini_api_key=api_key,
                ocr_model=ocr_model if ocr_model else None
            )

            return P("✅ Settings saved for this session",
                    style="color: #28a745; font-weight: bold;")

        except Exception as e:
            return P(f"❌ Error: {str(e)}",
                    style="color: #dc3545; font-weight: bold;")