"""OCR service for extracting text from PDF pages using LLM."""

import os
import base64
import io
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import pymupdf
import pymupdf4llm
import litellm
from PIL import Image
from dotenv import load_dotenv
from config import OCR_MODEL, OCR_TEMPERATURE, OCR_TIMEOUT, OCR_DPI, OCR_MAX_TOKENS, MATH_DETECTION_MODEL

# Load environment variables
load_dotenv()


def load_classification_prompt() -> str:
    """Load the math classification prompt from prompts folder."""
    prompt_path = Path(__file__).parent.parent / "prompts" / "math_detection_prompt.txt"
    with open(prompt_path, 'r', encoding='utf-8') as f:
        return f.read().strip()


def load_ocr_prompt() -> str:
    """Load the OCR extraction prompt from prompts folder."""
    prompt_path = Path(__file__).parent.parent / "prompts" / "ocr_prompt.txt"
    with open(prompt_path, 'r', encoding='utf-8') as f:
        return f.read().strip()


def convert_page_to_base64(pdf_path: Path, page_num: int, dpi: int = OCR_DPI) -> str:
    """
    Convert a PDF page to base64 encoded image.
    
    Args:
        pdf_path: Path to PDF file
        page_num: Page number (1-based)
        dpi: DPI for image conversion
        
    Returns:
        Base64 encoded image string
    """
    doc = pymupdf.open(pdf_path)
    page = doc[page_num - 1]  # Convert to 0-based index
    pix = page.get_pixmap(dpi=dpi)
    
    # Convert to PIL Image for JPEG compression
    img_data = pix.tobytes("png")
    pil_image = Image.open(io.BytesIO(img_data))
    
    # Convert RGBA to RGB if necessary
    if pil_image.mode in ('RGBA', 'LA', 'P'):
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
    
    # Save as JPEG with compression
    output_buffer = io.BytesIO()
    pil_image.save(output_buffer, format='JPEG', quality=85, optimize=True)
    output_buffer.seek(0)
    
    # Convert to base64
    base64_data = base64.b64encode(output_buffer.read()).decode('utf-8')
    
    # Clean up
    doc.close()
    pil_image.close()
    output_buffer.close()
    
    return base64_data


def detect_math_content(page_image_base64: str) -> Tuple[bool, int, int]:
    """
    Detect if a page contains mathematical content.
    
    Args:
        page_image_base64: Base64 encoded image of the page
        
    Returns:
        Tuple of (has_math, input_tokens, output_tokens)
    """
    try:
        # Load classification prompt
        prompt = load_classification_prompt()
        
        # Prepare message for LiteLLM
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": prompt
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{page_image_base64}"
                        }
                    }
                ]
            }
        ]
        
        # Make API call
        response = litellm.completion(
            model=MATH_DETECTION_MODEL,
            messages=messages,
            temperature=OCR_TEMPERATURE,
            timeout=OCR_TIMEOUT
        )
        
        # Extract response
        response_text = response.choices[0].message.content
        
        # Parse classification
        has_math = "Classification: YES" in response_text or "YES" in response_text.upper()[:20]
        
        # Get token usage
        usage = response.usage
        input_tokens = usage.prompt_tokens if usage else 0
        output_tokens = usage.completion_tokens if usage else 0
        
        return has_math, input_tokens, output_tokens
        
    except Exception as e:
        print(f"Error in math detection: {str(e)}")
        # On error, default to using standard extraction
        return False, 0, 0


def ocr_page_with_llm(page_image_base64: str) -> Tuple[str, int, int]:
    """
    Perform OCR on a page using LLM with LaTeX formatting for math.
    
    Args:
        page_image_base64: Base64 encoded image of the page
        
    Returns:
        Tuple of (extracted_text, input_tokens, output_tokens)
    """
    try:
        # Load OCR prompt
        prompt = load_ocr_prompt()
        
        # Prepare message for LiteLLM
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": prompt
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{page_image_base64}"
                        }
                    }
                ]
            }
        ]
        
        # Make API call
        response = litellm.completion(
            model=OCR_MODEL,
            messages=messages,
            temperature=OCR_TEMPERATURE,
            timeout=OCR_TIMEOUT,
            max_tokens=OCR_MAX_TOKENS
        )
        
        # Extract response
        extracted_text = response.choices[0].message.content
        
        # Get token usage
        usage = response.usage
        input_tokens = usage.prompt_tokens if usage else 0
        output_tokens = usage.completion_tokens if usage else 0
        
        return extracted_text, input_tokens, output_tokens
        
    except Exception as e:
        print(f"Error in LLM OCR: {str(e)}")
        return f"[Error extracting text from page: {str(e)}]", 0, 0


def process_pages_with_smart_ocr(
    pdf_path: Path, 
    start_page: int, 
    end_page: int
) -> Dict:
    """
    Process pages with smart OCR - using LLM for math pages, pymupdf for others.
    
    Args:
        pdf_path: Path to PDF file
        start_page: Starting page number (1-based)
        end_page: Ending page number (1-based)
        
    Returns:
        Dictionary with extracted text, token usage, and processing details
    """
    results = {
        "text_parts": [],
        "total_input_tokens": 0,
        "total_output_tokens": 0,
        "pages_with_llm": [],
        "pages_offline": [],
        "processing_details": []
    }
    
    # Process each page
    for page_num in range(start_page, end_page + 1):
        print(f"Processing page {page_num}...")
        
        # Convert page to image
        page_image_base64 = convert_page_to_base64(pdf_path, page_num)
        
        # Step 1: Detect if page has math
        has_math, detect_input_tokens, detect_output_tokens = detect_math_content(page_image_base64)
        results["total_input_tokens"] += detect_input_tokens
        results["total_output_tokens"] += detect_output_tokens
        
        # Step 2: Extract text based on math detection
        if has_math:
            # Use LLM OCR for math pages
            print(f"Page {page_num}: Detected math content, using LLM OCR")
            print(f"  - Detection tokens: {detect_input_tokens} in, {detect_output_tokens} out")
            extracted_text, ocr_input_tokens, ocr_output_tokens = ocr_page_with_llm(page_image_base64)
            print(f"  - OCR tokens: {ocr_input_tokens} in, {ocr_output_tokens} out")
            results["total_input_tokens"] += ocr_input_tokens
            results["total_output_tokens"] += ocr_output_tokens
            results["pages_with_llm"].append(page_num)
            
            # Add page header
            results["text_parts"].append(f"--- Page {page_num} ---\n{extracted_text}")
            results["processing_details"].append({
                "page": page_num,
                "method": "LLM OCR",
                "has_math": True,
                "tokens": {
                    "detection": {"input": detect_input_tokens, "output": detect_output_tokens},
                    "ocr": {"input": ocr_input_tokens, "output": ocr_output_tokens}
                }
            })
        else:
            # Use pymupdf4llm for non-math pages
            print(f"Page {page_num}: No math content, using offline extraction")
            print(f"  - Detection tokens: {detect_input_tokens} in, {detect_output_tokens} out")
            try:
                # Extract just this page using pymupdf4llm
                page_text = pymupdf4llm.to_markdown(pdf_path, pages=[page_num - 1])
                results["text_parts"].append(f"--- Page {page_num} ---\n{page_text}")
                results["pages_offline"].append(page_num)
                results["processing_details"].append({
                    "page": page_num,
                    "method": "Offline (pymupdf4llm)",
                    "has_math": False,
                    "tokens": {
                        "detection": {"input": detect_input_tokens, "output": detect_output_tokens},
                        "ocr": {"input": 0, "output": 0}
                    }
                })
            except Exception as e:
                print(f"Error extracting page {page_num} with pymupdf4llm: {str(e)}")
                # Fallback to basic extraction
                doc = pymupdf.open(pdf_path)
                page = doc[page_num - 1]
                page_text = page.get_text()
                doc.close()
                results["text_parts"].append(f"--- Page {page_num} ---\n{page_text}")
                results["pages_offline"].append(page_num)
                results["processing_details"].append({
                    "page": page_num,
                    "method": "Offline (basic)",
                    "has_math": False,
                    "tokens": {
                        "detection": {"input": detect_input_tokens, "output": detect_output_tokens},
                        "ocr": {"input": 0, "output": 0}
                    }
                })
    
    # Combine all text
    results["full_text"] = "\n\n".join(results["text_parts"])
    
    # Create summary
    llm_count = len(results["pages_with_llm"])
    offline_count = len(results["pages_offline"])
    results["summary"] = f"Processed pages {start_page}-{end_page}: {llm_count} pages with LLM OCR, {offline_count} pages with offline extraction"
    
    return results