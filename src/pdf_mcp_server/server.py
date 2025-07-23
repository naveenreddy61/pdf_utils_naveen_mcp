#!/usr/bin/env python3
"""PDF MCP Server - A Model Context Protocol server for PDF manipulation.

This server provides tools for interacting with PDF files using PyMuPDF,
allowing LLMs to read and extract content from PDF documents.
"""

import sys
import logging
from typing import List, Any

from fastmcp import FastMCP
from .tools import PdfTools

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastMCP server
mcp = FastMCP(
    name="pdf-tool-server",
    instructions="""This server provides tools for interacting with PDF files using PyMuPDF.

Available tools:
- get_table_of_contents: Extracts the Table of Contents (bookmarks) from a PDF.
- get_pages_from_pdf: Extracts a range of pages from a PDF into a new file and returns the path.
- get_pages_as_images: Converts a range of pages from a PDF to image files (PNG or JPG).
- extract_text_from_pages: Extracts text from a range of pages in a PDF, optionally as Markdown.
"""
)

# Initialize PDF tools
pdf_tools = PdfTools()


@mcp.tool
def get_table_of_contents(path: str) -> List[List[Any]]:
    """Extracts the table of contents (TOC) from a PDF file.
    
    Args:
        path: The absolute file path to the PDF document.
        
    Returns:
        A list of lists representing the TOC. Each inner list contains
        [level, title, page_number].
    """
    try:
        logger.info(f"Executing get_table_of_contents for: {path}")
        return pdf_tools.get_table_of_contents(path)
    except Exception as e:
        logger.error(f"Error in get_table_of_contents: {e}")
        # Re-raising the exception to be sent back to the MCP client
        raise


@mcp.tool
def get_pages_from_pdf(pdf_path: str, start_page: int, end_page: int) -> str:
    """Extracts a range of pages from a PDF and saves them to a new file.
    
    Args:
        pdf_path: The absolute file path to the source PDF.
        start_page: The starting page number (1-based, inclusive).
        end_page: The ending page number (1-based, inclusive).
        
    Returns:
        The absolute file path to the newly created PDF containing the extracted pages.
    """
    try:
        logger.info(f"Executing get_pages_from_pdf for '{pdf_path}' (pages {start_page}-{end_page})")
        result_path = pdf_tools.get_pages_from_pdf(pdf_path, start_page, end_page)
        logger.info(f"Extracted pages saved to: {result_path}")
        return result_path
    except Exception as e:
        logger.error(f"Error in get_pages_from_pdf: {e}")
        raise


@mcp.tool
def get_pages_as_images(pdf_path: str, start_page: int, end_page: int, dpi: int = 150, image_format: str = "png") -> List[str]:
    """Converts a range of pages from a PDF to image files.
    
    Args:
        pdf_path: The absolute file path to the source PDF.
        start_page: The starting page number (1-based, inclusive).
        end_page: The ending page number (1-based, inclusive).
        dpi: The resolution in dots per inch (default: 150).
        image_format: The image format - "png" or "jpg" (default: "png").
        
    Returns:
        A list of absolute file paths to the created image files.
    """
    try:
        logger.info(f"Executing get_pages_as_images for '{pdf_path}' (pages {start_page}-{end_page}, {dpi} DPI, {image_format} format)")
        result_paths = pdf_tools.get_pages_as_images(pdf_path, start_page, end_page, dpi, image_format)
        logger.info(f"Created {len(result_paths)} image files")
        return result_paths
    except Exception as e:
        logger.error(f"Error in get_pages_as_images: {e}")
        raise


@mcp.tool
def extract_text_from_pages(pdf_path: str, start_page: int, end_page: int, markdown: bool = True) -> str:
    """Extracts text from a range of pages in a PDF.
    
    Args:
        pdf_path: The absolute file path to the PDF document.
        start_page: The starting page number (1-based, inclusive).
        end_page: The ending page number (1-based, inclusive).
        markdown: Whether to return text in Markdown format (default: True).
        
    Returns:
        Extracted text as a string, optionally formatted as Markdown.
    """
    try:
        logger.info(f"Executing extract_text_from_pages for '{pdf_path}' (pages {start_page}-{end_page}, markdown={markdown})")
        text = pdf_tools.extract_text_from_pages(pdf_path, start_page, end_page, markdown)
        logger.info(f"Extracted {len(text)} characters of text")
        return text
    except Exception as e:
        logger.error(f"Error in extract_text_from_pages: {e}")
        raise


def main():
    """Main entry point for the PDF MCP server."""
    try:
        logger.info("Starting PDF MCP Server...")
        mcp.run()
    except KeyboardInterrupt:
        logger.info("Server shutdown requested.")
        sys.exit(0)
    except Exception as e:
        logger.error(f"A critical error occurred: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()