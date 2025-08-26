"""OCR service for extracting text from PDF pages using Google GenAI with native PDF processing and caching."""

import os
import io
import asyncio
import time
import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Callable, Any
import pymupdf
import pymupdf4llm
from dotenv import load_dotenv

from google import genai
from google.genai import types

from config import (
    OCR_MODEL, 
    OCR_TEMPERATURE, 
    OCR_TIMEOUT, 
    OCR_MAX_TOKENS,
    OCR_PAGES_PER_CHUNK,
    OCR_CONCURRENT_REQUESTS,
    OCR_MAX_RETRIES,
    OCR_RETRY_DELAY_BASE,
    OCR_BATCH_TIMEOUT
)
from .ocr_cache import (
    compute_content_hash,
    get_cached_ocr,
    save_ocr_to_cache,
    clean_old_cache_entries,
    init_cache_database
)

# Load environment variables and initialize the GenAI client
load_dotenv()
client = genai.Client()


def load_ocr_prompt() -> str:
    """Load the OCR extraction prompt from prompts folder."""
    prompt_path = Path(__file__).parent.parent / "prompts" / "ocr_prompt_pdf.txt"
    try:
        with open(prompt_path, 'r', encoding='utf-8') as f:
            return f.read().strip()
    except FileNotFoundError:
        return (
            "Extract all text from this PDF document accurately. "
            "The document may contain one or two pages. "
            "Clearly separate the transcribed text for each page using '--- Page [Page Number] ---' as a header."
        )


def create_pdf_subset_bytes(pdf_path: Path, page_nums: List[int]) -> bytes:
    """
    Create an in-memory PDF containing only the specified pages.
    
    Args:
        pdf_path: Path to the source PDF file
        page_nums: List of 1-based page numbers to include
        
    Returns:
        The content of the new PDF as bytes
    """
    doc = pymupdf.open(pdf_path)
    new_doc = pymupdf.open()  # Create a new empty PDF
    
    # Convert to 0-based page numbers and validate
    zero_based_pages = [p - 1 for p in page_nums if 0 <= p - 1 < len(doc)]
    
    if not zero_based_pages:
        doc.close()
        new_doc.close()
        raise ValueError(f"Page numbers {page_nums} are out of range for the document.")
    
    # Insert pages into new document
    for page_idx in zero_based_pages:
        new_doc.insert_pdf(doc, from_page=page_idx, to_page=page_idx)
    
    # Save to an in-memory buffer
    buffer = io.BytesIO()
    new_doc.save(buffer)
    buffer.seek(0)
    pdf_bytes = buffer.getvalue()
    
    # Clean up
    new_doc.close()
    doc.close()
    buffer.close()
    
    return pdf_bytes


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


def create_cache_key(pdf_path: Path, page_nums: List[int]) -> str:
    """
    Create a stable cache key based on PDF file and page numbers.
    This avoids issues with non-deterministic PDF subset generation.
    
    Args:
        pdf_path: Path to the original PDF file
        page_nums: List of page numbers being processed
        
    Returns:
        Hash string for cache key
    """
    # Get file stats for uniqueness (size + modification time)
    stats = pdf_path.stat()
    key_data = f"{pdf_path.name}:{stats.st_size}:{stats.st_mtime}:{sorted(page_nums)}"
    return compute_content_hash(key_data.encode('utf-8'))


def parse_llm_response(response_text: str, page_nums: List[int]) -> Dict[int, str]:
    """
    Parse the LLM response into a dictionary mapping page number to text.
    
    Args:
        response_text: The LLM's response text
        page_nums: List of page numbers that were processed
        
    Returns:
        Dictionary mapping page number to extracted text
    """
    page_texts = {}
    
    # If only one page, return the entire response
    if len(page_nums) == 1:
        page_texts[page_nums[0]] = response_text.strip()
        return page_texts
    
    # Split by page headers
    parts = re.split(r'--- Page \d+ ---', response_text)
    headers = re.findall(r'--- Page (\d+) ---', response_text)
    
    # Clean up parts (remove empty strings)
    cleaned_parts = [p.strip() for p in parts if p.strip()]
    
    # Match headers with parts
    if len(headers) == len(cleaned_parts):
        for i, header_num_str in enumerate(headers):
            header_num = int(header_num_str)
            if header_num in page_nums:
                page_texts[header_num] = cleaned_parts[i]
    else:
        # Fallback: distribute text evenly or assign to first page
        print(f"Warning: Could not parse LLM response for pages {page_nums}.")
        page_texts[page_nums[0]] = response_text.strip()
        for i in range(1, len(page_nums)):
            page_texts[page_nums[i]] = "[OCR Parsing Failed]"
    
    return page_texts


async def ocr_pdf_subset_with_llm(
    pdf_subset_bytes: bytes,
    page_nums: List[int],
    pdf_filename: Optional[str] = None,
    pdf_path: Optional[Path] = None
) -> Tuple[str, int, int, str]:
    """
    Perform OCR on a PDF subset using Google GenAI with caching support.
    
    Args:
        pdf_subset_bytes: The byte content of the PDF subset
        page_nums: The corresponding page numbers
        pdf_filename: The name of the source PDF for debugging/caching
        pdf_path: Path to original PDF (for stable cache key)
        
    Returns:
        Tuple of (combined_extracted_text, input_tokens, output_tokens, method)
        method is "cached" or "llm"
    """
    # Create stable cache key based on original file + pages
    if pdf_path:
        cache_key = create_cache_key(pdf_path, page_nums)
    else:
        # Fallback to content hash if no path available
        cache_key = compute_content_hash(pdf_subset_bytes)
    
    # Check cache first
    cached_result = await get_cached_ocr(cache_key)
    
    if cached_result:
        text, input_tokens, output_tokens = cached_result
        return text, input_tokens, output_tokens, "cached"
    
    try:
        # Load OCR prompt
        prompt = load_ocr_prompt()
        full_prompt = f"{prompt}\nThe document contains pages: {', '.join(map(str, page_nums))}."
        
        # Create a Part object with the PDF data directly
        pdf_part = types.Part(
            inline_data=types.Blob(mime_type='application/pdf', data=pdf_subset_bytes)
        )
        
        contents = [full_prompt, pdf_part]
        
        # Make the async API call
        response = await asyncio.wait_for(
            client.aio.models.generate_content(
                model=OCR_MODEL,
                contents=contents,
                config=types.GenerateContentConfig(
                    temperature=OCR_TEMPERATURE,
                    max_output_tokens=OCR_MAX_TOKENS * len(page_nums)
                )
            ),
            timeout=OCR_TIMEOUT
        )
        
        # Extract response
        extracted_text = response.text
        
        # Get token usage from GenAI response
        usage = response.usage_metadata
        input_tokens = usage.prompt_token_count if usage else 0
        output_tokens = usage.candidates_token_count if usage else 0
        
        # Save to cache
        await save_ocr_to_cache(
            cache_key,
            extracted_text,
            input_tokens,
            output_tokens,
            pdf_filename,
            page_nums[0]  # Use first page number for reference
        )
        
        return extracted_text, input_tokens, output_tokens, "llm"
        
    except Exception as e:
        print(f"Error in GenAI OCR for pages {page_nums}: {str(e)}")
        raise e


async def process_page_chunk(
    pdf_path: Path,
    page_nums: List[int],
    semaphore: asyncio.Semaphore,
    pdf_filename: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Process a chunk of pages by creating and sending an in-memory PDF subset.
    
    Args:
        pdf_path: Path to PDF file
        page_nums: List of page numbers (1-based) to process as a chunk
        semaphore: Semaphore for rate limiting
        pdf_filename: PDF filename for caching/debugging
        
    Returns:
        List of dictionaries with page processing results
    """
    async with semaphore:
        try:
            # Create an in-memory PDF with just the required pages
            pdf_subset_bytes = create_pdf_subset_bytes(pdf_path, page_nums)
            
            # Perform OCR on the PDF subset
            combined_text, input_tokens, output_tokens, method = await ocr_pdf_subset_with_llm(
                pdf_subset_bytes, page_nums, pdf_filename, pdf_path
            )
            
            # Parse the response into individual page texts
            parsed_texts = parse_llm_response(combined_text, page_nums)
            
            # Create results for each page
            results = []
            num_pages = len(page_nums)
            for page_num in page_nums:
                results.append({
                    "page": page_num,
                    "text": parsed_texts.get(page_num, "[OCR Parsing Error]"),
                    "input_tokens": input_tokens // num_pages,  # Distribute tokens evenly
                    "output_tokens": output_tokens // num_pages,
                    "method": method,
                    "success": True,
                    "error": None,
                    "retry_count": 0
                })
            
            return results
            
        except Exception as e:
            # Return failed results for all pages in the chunk
            return [{
                "page": page_num,
                "text": None,
                "input_tokens": 0,
                "output_tokens": 0,
                "method": "failed",
                "success": False,
                "error": str(e),
                "retry_count": 0
            } for page_num in page_nums]


async def retry_failed_chunks(
    failed_pages: List[Dict],
    attempt: int,
    pdf_path: Path,
    semaphore: asyncio.Semaphore,
    pdf_filename: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Retry processing failed pages by regrouping them into chunks with exponential backoff.
    
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
    
    # Group failed pages into chunks
    failed_page_nums = sorted([r['page'] for r in failed_pages])
    page_chunks = []
    
    # Group pages into chunks of OCR_PAGES_PER_CHUNK
    i = 0
    while i < len(failed_page_nums):
        chunk_end = min(i + OCR_PAGES_PER_CHUNK, len(failed_page_nums))
        chunk = failed_page_nums[i:chunk_end]
        page_chunks.append(chunk)
        i = chunk_end
    
    # Create retry tasks for chunks
    retry_tasks = [
        process_page_chunk(pdf_path, chunk, semaphore, pdf_filename)
        for chunk in page_chunks
    ]
    
    # Process retries
    retry_results_list = await asyncio.gather(*retry_tasks, return_exceptions=True)
    
    # Flatten results and update retry count
    processed_results = []
    for result_list in retry_results_list:
        if isinstance(result_list, Exception):
            # Convert exception to failed results for all pages in this chunk
            chunk_idx = retry_results_list.index(result_list)
            chunk = page_chunks[chunk_idx]
            for page_num in chunk:
                processed_results.append({
                    "page": page_num,
                    "text": None,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "method": "failed",
                    "success": False,
                    "error": str(result_list),
                    "retry_count": attempt
                })
        else:
            # Update retry count for successful results
            for result in result_list:
                result["retry_count"] = attempt
                processed_results.append(result)
    
    return processed_results


async def process_document_async(
    pdf_path: Path,
    start_page: int,
    end_page: int,
    progress_callback: Optional[Callable[[str], None]] = None
) -> Dict:
    """
    Process a document with async chunked processing, native PDF handling, caching, and retries.
    
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
    
    # Group pages into chunks
    total_pages = end_page - start_page + 1
    page_list = list(range(start_page, end_page + 1))
    page_chunks = []
    
    # Create chunks based on OCR_PAGES_PER_CHUNK
    i = 0
    while i < len(page_list):
        chunk_end = min(i + OCR_PAGES_PER_CHUNK, len(page_list))
        chunk = page_list[i:chunk_end]
        page_chunks.append(chunk)
        i = chunk_end
    
    num_api_calls = len(page_chunks)
    
    if progress_callback:
        progress_callback(f"Processing {total_pages} pages in {num_api_calls} API calls")
    
    # Create semaphore for rate limiting
    semaphore = asyncio.Semaphore(OCR_CONCURRENT_REQUESTS)
    
    # Process all chunks initially
    chunk_tasks = [
        process_page_chunk(pdf_path, chunk, semaphore, pdf_filename)
        for chunk in page_chunks
    ]
    
    # Process initial chunks
    chunk_results_list = await asyncio.gather(*chunk_tasks, return_exceptions=True)
    
    # Flatten results and handle exceptions
    all_results = []
    for i, result_list in enumerate(chunk_results_list):
        if isinstance(result_list, Exception):
            # Convert exception to failed results for all pages in this chunk
            chunk = page_chunks[i]
            for page_num in chunk:
                all_results.append({
                    "page": page_num,
                    "text": None,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "method": "failed",
                    "success": False,
                    "error": str(result_list),
                    "retry_count": 0
                })
        else:
            all_results.extend(result_list)
    
    # Retry failed pages
    failed_pages = [r for r in all_results if not r["success"]]
    
    for retry_attempt in range(1, OCR_MAX_RETRIES + 1):
        if not failed_pages:
            break
            
        retry_results = await retry_failed_chunks(
            failed_pages, retry_attempt, pdf_path, semaphore, pdf_filename
        )
        
        # Update results and prepare for next retry
        successful_retries = []
        still_failed = []
        
        for retry_result in retry_results:
            if retry_result["success"]:
                successful_retries.append(retry_result)
                # Replace the failed result with successful one
                for j, original_result in enumerate(all_results):
                    if original_result["page"] == retry_result["page"]:
                        all_results[j] = retry_result
                        break
            else:
                still_failed.append(retry_result)
        
        failed_pages = still_failed
        
        if progress_callback and successful_retries:
            progress_callback(f"Recovered {len(successful_retries)} pages on retry {retry_attempt}")
    
    # Apply PyMuPDF fallback to still failed pages
    final_failed_pages = [r for r in all_results if not r["success"]]
    if final_failed_pages:
        if progress_callback:
            progress_callback(f"Applying offline extraction to {len(final_failed_pages)} pages")
        
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
    
    # Sort results by page number
    all_results.sort(key=lambda x: x["page"])
    
    # Compile final results
    text_parts = []
    total_input_tokens = 0
    total_output_tokens = 0
    cached_pages = []
    llm_pages = []
    fallback_pages = []
    tokens_saved = 0
    
    for result in all_results:
        # Add text with page header
        if result["text"]:
            text_parts.append(f"--- Page {result['page']} ---\n{result['text']}")
        
        # Accumulate tokens
        total_input_tokens += result["input_tokens"]
        total_output_tokens += result["output_tokens"]
        
        # Track tokens saved from cache
        if result["method"] == "cached":
            tokens_saved += result["input_tokens"] + result["output_tokens"]
        
        # Categorize pages
        if result["method"] == "cached":
            cached_pages.append(result["page"])
        elif result["method"] == "llm":
            llm_pages.append(result["page"])
        elif result["method"] == "pymupdf_fallback":
            fallback_pages.append(result["page"])
    
    processing_time = time.time() - start_time
    
    # Clean old cache entries in background
    asyncio.create_task(clean_old_cache_entries())
    
    # Create token usage summary
    token_summary = f"Used {total_input_tokens:,} input + {total_output_tokens:,} output tokens"
    if tokens_saved > 0:
        token_summary += f" (saved {tokens_saved:,} tokens from cache)"
    
    if progress_callback:
        progress_callback(f"✅ Complete: {token_summary}")
    
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
        "pages_processed": len(all_results),
        "retry_count": sum(r["retry_count"] for r in all_results),
        "tokens_saved": tokens_saved,
        "summary": token_summary
    }


# Backward compatibility alias
process_pages_async_batch = process_document_async