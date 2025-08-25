"""OCR service for extracting text from PDF pages using async LLM processing with caching."""

import os
import base64
import io
import asyncio
import time
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Callable
import pymupdf
import pymupdf4llm
import litellm
from PIL import Image
from dotenv import load_dotenv

from config import (
    OCR_MODEL, 
    OCR_TEMPERATURE, 
    OCR_TIMEOUT, 
    OCR_DPI, 
    OCR_MAX_TOKENS,
    OCR_CONCURRENT_REQUESTS,
    OCR_MAX_RETRIES,
    OCR_RETRY_DELAY_BASE,
    OCR_BATCH_TIMEOUT
)
from .ocr_cache import (
    compute_image_hash,
    get_cached_ocr,
    save_ocr_to_cache,
    clean_old_cache_entries,
    init_cache_database
)

# Load environment variables
load_dotenv()


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


def extract_with_pymupdf_fallback(pdf_path: Path, page_num: int) -> str:
    """
    Extract text from a page using PyMuPDF as fallback.
    
    Args:
        pdf_path: Path to PDF file
        page_num: Page number (1-based)
        
    Returns:
        Extracted text
    """
    try:
        # Try pymupdf4llm first for better formatting
        page_text = pymupdf4llm.to_markdown(pdf_path, pages=[page_num - 1])
        return page_text
    except Exception:
        # Fallback to basic extraction
        try:
            doc = pymupdf.open(pdf_path)
            page = doc[page_num - 1]
            page_text = page.get_text()
            doc.close()
            return page_text
        except Exception as e:
            return f"[Error extracting text from page {page_num}: {str(e)}]"


async def ocr_page_with_llm(
    page_image_base64: str, 
    page_num: int,
    pdf_filename: Optional[str] = None
) -> Tuple[str, int, int, str]:
    """
    Perform OCR on a page using LLM with caching support.
    
    Args:
        page_image_base64: Base64 encoded image of the page
        page_num: Page number for debugging
        pdf_filename: PDF filename for debugging
        
    Returns:
        Tuple of (extracted_text, input_tokens, output_tokens, method)
        method is "cached" or "llm"
    """
    # Check cache first
    image_hash = compute_image_hash(page_image_base64)
    cached_result = await get_cached_ocr(image_hash)
    
    if cached_result:
        text, input_tokens, output_tokens = cached_result
        return text, input_tokens, output_tokens, "cached"
    
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
        
        # Make async API call
        response = await litellm.acompletion(
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
        
        # Save to cache
        await save_ocr_to_cache(
            image_hash, 
            extracted_text, 
            input_tokens, 
            output_tokens,
            pdf_filename,
            page_num
        )
        
        return extracted_text, input_tokens, output_tokens, "llm"
        
    except Exception as e:
        print(f"Error in LLM OCR for page {page_num}: {str(e)}")
        raise e


async def process_single_page(
    pdf_path: Path,
    page_num: int,
    semaphore: asyncio.Semaphore,
    pdf_filename: Optional[str] = None
) -> Dict:
    """
    Process a single page with semaphore rate limiting.
    
    Args:
        pdf_path: Path to PDF file
        page_num: Page number (1-based)
        semaphore: Semaphore for rate limiting
        pdf_filename: PDF filename for caching/debugging
        
    Returns:
        Dictionary with page processing result
    """
    async with semaphore:
        try:
            # Convert page to base64
            page_image_base64 = convert_page_to_base64(pdf_path, page_num)
            
            # Perform OCR with caching
            text, input_tokens, output_tokens, method = await ocr_page_with_llm(
                page_image_base64, page_num, pdf_filename
            )
            
            return {
                "page": page_num,
                "text": text,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "method": method,
                "success": True,
                "error": None,
                "retry_count": 0
            }
            
        except Exception as e:
            return {
                "page": page_num,
                "text": None,
                "input_tokens": 0,
                "output_tokens": 0,
                "method": "failed",
                "success": False,
                "error": str(e),
                "retry_count": 0
            }


async def retry_failed_pages(
    failed_pages: List[Dict],
    attempt: int,
    pdf_path: Path,
    semaphore: asyncio.Semaphore,
    pdf_filename: Optional[str] = None
) -> List[Dict]:
    """
    Retry processing failed pages with exponential backoff.
    
    Args:
        failed_pages: List of failed page results
        attempt: Current retry attempt number
        pdf_path: Path to PDF file
        semaphore: Semaphore for rate limiting
        pdf_filename: PDF filename for caching/debugging
        
    Returns:
        List of retry results
    """
    # Exponential backoff delay
    delay = OCR_RETRY_DELAY_BASE * (2 ** (attempt - 1))
    await asyncio.sleep(delay)
    
    print(f"Retrying {len(failed_pages)} failed pages (attempt {attempt})")
    
    # Create retry tasks
    retry_tasks = []
    for failed_page in failed_pages:
        page_num = failed_page["page"]
        task = process_single_page(pdf_path, page_num, semaphore, pdf_filename)
        retry_tasks.append(task)
    
    # Process retries
    retry_results = await asyncio.gather(*retry_tasks, return_exceptions=True)
    
    # Update retry count and handle exceptions
    processed_results = []
    for i, result in enumerate(retry_results):
        if isinstance(result, Exception):
            # Convert exception to failed result
            result = {
                "page": failed_pages[i]["page"],
                "text": None,
                "input_tokens": 0,
                "output_tokens": 0,
                "method": "failed",
                "success": False,
                "error": str(result),
                "retry_count": attempt
            }
        else:
            result["retry_count"] = attempt
        
        processed_results.append(result)
    
    return processed_results


async def process_pages_async_batch(
    pdf_path: Path,
    start_page: int,
    end_page: int,
    progress_callback: Optional[Callable[[str], None]] = None
) -> Dict:
    """
    Process pages with async batch processing, caching, and intelligent retries.
    
    Args:
        pdf_path: Path to PDF file
        start_page: Starting page number (1-based)
        end_page: Ending page number (1-based)
        progress_callback: Optional callback for progress updates
        
    Returns:
        Dictionary with processing results and statistics
    """
    # Initialize cache database
    await init_cache_database()
    
    start_time = time.time()
    pdf_filename = pdf_path.name
    
    # Calculate batch information
    total_pages = end_page - start_page + 1
    batch_size = OCR_CONCURRENT_REQUESTS
    num_batches = (total_pages + batch_size - 1) // batch_size
    
    if progress_callback:
        progress_callback(
            f"Your request will be processed in {num_batches} batches of up to {batch_size} pages each"
        )
    
    # Create semaphore for rate limiting
    semaphore = asyncio.Semaphore(OCR_CONCURRENT_REQUESTS)
    
    # Process pages in batches
    all_results = []
    pages = list(range(start_page, end_page + 1))
    
    for batch_idx in range(num_batches):
        batch_start = batch_idx * batch_size
        batch_end = min(batch_start + batch_size, len(pages))
        batch_pages = pages[batch_start:batch_end]
        
        if progress_callback:
            progress_callback(f"Starting batch {batch_idx + 1} of {num_batches} ({len(batch_pages)} pages)")
        
        # Create tasks for this batch
        batch_tasks = []
        for page_num in batch_pages:
            task = process_single_page(pdf_path, page_num, semaphore, pdf_filename)
            batch_tasks.append(task)
        
        # Process batch
        batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
        
        # Handle exceptions
        processed_batch_results = []
        for i, result in enumerate(batch_results):
            if isinstance(result, Exception):
                result = {
                    "page": batch_pages[i],
                    "text": None,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "method": "failed",
                    "success": False,
                    "error": str(result),
                    "retry_count": 0
                }
            processed_batch_results.append(result)
        
        # Retry failed pages
        failed_pages = [r for r in processed_batch_results if not r["success"]]
        
        for retry_attempt in range(1, OCR_MAX_RETRIES + 1):
            if not failed_pages:
                break
                
            retry_results = await retry_failed_pages(
                failed_pages, retry_attempt, pdf_path, semaphore, pdf_filename
            )
            
            # Update results and prepare for next retry
            successful_retries = []
            still_failed = []
            
            for retry_result in retry_results:
                if retry_result["success"]:
                    successful_retries.append(retry_result)
                    # Replace the failed result with successful one
                    for j, original_result in enumerate(processed_batch_results):
                        if original_result["page"] == retry_result["page"]:
                            processed_batch_results[j] = retry_result
                            break
                else:
                    still_failed.append(retry_result)
            
            failed_pages = still_failed
            
            if progress_callback and successful_retries:
                progress_callback(f"Batch {batch_idx + 1}: Recovered {len(successful_retries)} pages on retry {retry_attempt}")
        
        # Apply PyMuPDF fallback to still failed pages
        final_failed_pages = [r for r in processed_batch_results if not r["success"]]
        if final_failed_pages:
            if progress_callback:
                progress_callback(f"Batch {batch_idx + 1}: Applying fallback extraction to {len(final_failed_pages)} pages")
            
            for failed_result in final_failed_pages:
                try:
                    fallback_text = extract_with_pymupdf_fallback(pdf_path, failed_result["page"])
                    failed_result.update({
                        "text": fallback_text,
                        "method": "pymupdf_fallback",
                        "success": True,
                        "error": None
                    })
                except Exception as e:
                    failed_result["error"] = f"Fallback failed: {str(e)}"
        
        all_results.extend(processed_batch_results)
        
        if progress_callback:
            progress_callback(f"Batch {batch_idx + 1} of {num_batches} completed")
    
    # Sort results by page number
    all_results.sort(key=lambda x: x["page"])
    
    # Compile final results
    text_parts = []
    total_input_tokens = 0
    total_output_tokens = 0
    cached_pages = []
    llm_pages = []
    fallback_pages = []
    processing_details = []
    
    for result in all_results:
        # Add text with page header
        if result["text"]:
            text_parts.append(f"--- Page {result['page']} ---\n{result['text']}")
        
        # Accumulate tokens
        total_input_tokens += result["input_tokens"]
        total_output_tokens += result["output_tokens"]
        
        # Categorize pages
        if result["method"] == "cached":
            cached_pages.append(result["page"])
        elif result["method"] == "llm":
            llm_pages.append(result["page"])
        elif result["method"] == "pymupdf_fallback":
            fallback_pages.append(result["page"])
        
        # Processing details
        processing_details.append({
            "page": result["page"],
            "method": {
                "cached": "Cached",
                "llm": "LLM OCR",
                "pymupdf_fallback": "PyMuPDF Fallback"
            }.get(result["method"], "Failed"),
            "tokens": {"input": result["input_tokens"], "output": result["output_tokens"]},
            "cached": result["method"] == "cached",
            "retry_count": result["retry_count"]
        })
    
    processing_time = time.time() - start_time
    cache_hit_rate = len(cached_pages) / len(all_results) * 100 if all_results else 0
    
    # Clean old cache entries in background
    asyncio.create_task(clean_old_cache_entries())
    
    # Create summary
    summary_parts = []
    if llm_pages:
        summary_parts.append(f"{len(llm_pages)} pages with fresh LLM OCR")
    if cached_pages:
        summary_parts.append(f"{len(cached_pages)} pages from cache")
    if fallback_pages:
        summary_parts.append(f"{len(fallback_pages)} pages with fallback extraction")
    
    summary = f"Processed pages {start_page}-{end_page}: " + ", ".join(summary_parts)
    
    if progress_callback:
        progress_callback(f"✅ Processing complete! {cache_hit_rate:.1f}% cache hit rate")
    
    return {
        "full_text": "\n\n".join(text_parts),
        "text_parts": text_parts,
        "total_input_tokens": total_input_tokens,
        "total_output_tokens": total_output_tokens,
        "successful_pages": [r["page"] for r in all_results if r["success"]],
        "failed_pages": [{"page": r["page"], "error": r["error"]} for r in all_results if not r["success"]],
        "cached_pages": cached_pages,
        "llm_pages": llm_pages,
        "fallback_pages": fallback_pages,
        "processing_time": processing_time,
        "cache_hit_rate": cache_hit_rate,
        "pages_processed": len(all_results),
        "retry_count": sum(r["retry_count"] for r in all_results),
        "processing_details": processing_details,
        "summary": summary
    }