"""Main routes for the web application."""

import os
from datetime import datetime
from fasthtml.common import *
from starlette.requests import Request
from config import UPLOAD_DIR, MAX_FILE_SIZE_BYTES, MAX_FILE_SIZE_MB, ALLOWED_EXTENSIONS
from src.web_app.core.database import (
    FileRecord, get_file_info, update_last_accessed, insert_file_record
)
from src.web_app.core.session_settings import get_session_settings
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
                                style="width: 100%; padding: 10px; margin-bottom: 10px; border: 1px solid #ccc; border-radius: 4px;"
                            ),
                            Button(
                                "Clear API Key",
                                type="button",
                                onclick="document.getElementById('api-key-input').value = ''; saveSettings();",
                                style="background-color: #dc3545; margin-bottom: 15px;"
                            ) if user_settings['gemini_api_key'] else None,
                            style="margin-bottom: 20px;"
                        ),

                        # Model selection
                        Div(
                            Label("OCR Model", _for="model-select", style="display: block; margin-bottom: 5px; font-weight: bold;"),
                            P("Select the Gemini model to use for OCR processing",
                              style="font-size: 0.9em; color: #6c757d; margin-bottom: 10px;"),
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
                            Button(
                                "🔄 Fetch Available Models",
                                type="button",
                                onclick="fetchModels()",
                                id="fetch-models-btn",
                                style="background-color: #17a2b8; margin-bottom: 15px;"
                            ),
                            Div(
                                P(f"ℹ️ {len(user_settings['available_models'])} models loaded from session",
                                  style="color: #28a745; font-size: 0.9em; margin: 0;")
                                if user_settings['available_models']
                                else P("Click 'Fetch Available Models' to populate the dropdown",
                                      style="color: #6c757d; font-size: 0.9em; margin: 0;"),
                                id="model-status",
                                style="margin-top: 10px;"
                            ),
                            style="margin-bottom: 20px;"
                        ),

                        # Save button
                        Button(
                            "💾 Save Settings",
                            type="button",
                            onclick="saveSettings()",
                            style="background-color: #28a745; padding: 12px 24px; font-size: 1em;"
                        ),

                        Div(id="save-status", style="margin-top: 15px;"),

                        id="settings-form"
                    ),

                    cls="settings-container",
                    style="max-width: 800px;"
                ),

                # JavaScript for handling API calls
                Script("""
                    async function fetchModels() {
                        const btn = document.getElementById('fetch-models-btn');
                        const statusDiv = document.getElementById('model-status');
                        const modelSelect = document.getElementById('model-select');

                        btn.disabled = true;
                        btn.textContent = '⏳ Fetching models...';
                        statusDiv.innerHTML = '<p style="color: #17a2b8;">Fetching models from Gemini API...</p>';

                        try {
                            const response = await fetch('/api/models/list');
                            const data = await response.json();

                            if (data.error) {
                                statusDiv.innerHTML = `<p style="color: #dc3545;">❌ Error: ${data.error}</p>`;
                            } else {
                                // Clear existing options
                                modelSelect.innerHTML = '';

                                // Add models to dropdown
                                data.models.forEach(model => {
                                    const option = document.createElement('option');
                                    option.value = model.name;
                                    option.textContent = `${model.display_name} (${model.name})`;
                                    modelSelect.appendChild(option);
                                });

                                statusDiv.innerHTML = `<p style="color: #28a745;">✅ Found ${data.count} models</p>`;
                            }
                        } catch (error) {
                            statusDiv.innerHTML = `<p style="color: #dc3545;">❌ Error: ${error.message}</p>`;
                        } finally {
                            btn.disabled = false;
                            btn.textContent = '🔄 Fetch Available Models';
                        }
                    }

                    async function saveSettings() {
                        const statusDiv = document.getElementById('save-status');
                        const apiKeyInput = document.getElementById('api-key-input');
                        const modelSelect = document.getElementById('model-select');

                        statusDiv.innerHTML = '<p style="color: #17a2b8;">💾 Saving settings...</p>';

                        try {
                            // Only include API key if it's not the masked value
                            const apiKey = apiKeyInput.value === '••••••••' ? null : apiKeyInput.value;

                            const response = await fetch('/api/settings', {
                                method: 'POST',
                                headers: {
                                    'Content-Type': 'application/json',
                                },
                                body: JSON.stringify({
                                    gemini_api_key: apiKey,
                                    ocr_model: modelSelect.value
                                })
                            });

                            const data = await response.json();

                            if (data.error) {
                                statusDiv.innerHTML = `<p style="color: #dc3545;">❌ Error: ${data.error}</p>`;
                            } else {
                                statusDiv.innerHTML = `<p style="color: #28a745;">✅ ${data.message}</p>`;

                                // Reload page after 1 second to show updated status
                                setTimeout(() => {
                                    window.location.reload();
                                }, 1000);
                            }
                        } catch (error) {
                            statusDiv.innerHTML = `<p style="color: #dc3545;">❌ Error: ${error.message}</p>`;
                        }
                    }
                """),

                cls="container"
            )
        )