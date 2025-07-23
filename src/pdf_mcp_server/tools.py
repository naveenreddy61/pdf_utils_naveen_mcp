"""MCP tools for PDF operations using PyMuPDF."""

import pymupdf
import pymupdf4llm
import os
from pathlib import Path
from typing import List, Dict, Any


class PdfTools:
    """Collection of MCP tools for PDF operations."""

    def get_table_of_contents(self, path: str) -> List[List[Any]]:
        """
        Extracts the table of contents (TOC) from a PDF file.

        Args:
            path: The file path to the PDF document.

        Returns:
            A list of lists representing the TOC. Each inner list contains
            [level, title, page_number].

        Raises:
            Exception: If the file is not found, not a valid PDF, or has no TOC.
        """
        if not os.path.exists(path):
            raise FileNotFoundError(f"The file was not found at path: {path}")

        try:
            doc = pymupdf.open(path)
            toc = doc.get_toc()
            doc.close()
            if not toc:
                raise ValueError("PDF has no table of contents.")
            return toc
        except Exception as e:
            raise Exception(f"Failed to get TOC from '{path}': {e}")

    def get_pages_from_pdf(self, pdf_path: str, start_page: int, end_page: int) -> str:
        """
        Extracts a range of pages from a PDF and saves them to a new file.

        Args:
            pdf_path: The file path to the source PDF.
            start_page: The starting page number (1-based).
            end_page: The ending page number (1-based).

        Returns:
            The file path to the newly created PDF containing the extracted pages.

        Raises:
            Exception: If the file is not found, the page range is invalid, or extraction fails.
        """
        # Convert to Path object for cross-platform compatibility
        pdf_path_obj = Path(pdf_path).resolve()
        
        if not pdf_path_obj.exists():
            raise FileNotFoundError(f"The file was not found at path: {pdf_path}")
            
        try:
            source_doc = pymupdf.open(str(pdf_path_obj))

            # Validate page numbers
            if not (1 <= start_page <= end_page <= source_doc.page_count):
                raise ValueError(
                    f"Invalid page range. Start: {start_page}, End: {end_page}. "
                    f"Document has {source_doc.page_count} pages."
                )

            new_doc = pymupdf.open()  # Create a new, empty PDF
            # PyMuPDF uses 0-based indexing for pages
            new_doc.insert_pdf(source_doc, from_page=start_page - 1, to_page=end_page - 1)

            # Save to the same directory as the source file
            source_dir = pdf_path_obj.parent
            base_name = pdf_path_obj.stem
            # Add 'mcp' prefix to the output filename
            output_filename = f"mcp_{base_name}_pages_{start_page}_to_{end_page}.pdf"
            output_path = source_dir / output_filename
            
            new_doc.save(str(output_path), garbage=4, deflate=True)
            new_doc.close()
            source_doc.close()

            return str(output_path)
        except Exception as e:
            raise Exception(f"Failed to extract pages from '{pdf_path}': {e}")

    def get_pages_as_images(self, pdf_path: str, start_page: int, end_page: int, dpi: int = 150, image_format: str = "png") -> List[str]:
        """
        Converts a range of pages from a PDF to image files.

        Args:
            pdf_path: The file path to the source PDF.
            start_page: The starting page number (1-based).
            end_page: The ending page number (1-based).
            dpi: The resolution in dots per inch (default: 150).
            image_format: The image format - "png" or "jpg" (default: "png").

        Returns:
            A list of file paths to the created image files.

        Raises:
            Exception: If the file is not found, the page range is invalid, or conversion fails.
        """
        # Convert to Path object for cross-platform compatibility
        pdf_path_obj = Path(pdf_path).resolve()
        
        if not pdf_path_obj.exists():
            raise FileNotFoundError(f"The file was not found at path: {pdf_path}")
            
        if image_format.lower() not in ["png", "jpg", "jpeg"]:
            raise ValueError(f"Unsupported image format: {image_format}. Use 'png' or 'jpg'.")
            
        try:
            doc = pymupdf.open(str(pdf_path_obj))
            
            # Validate page numbers
            if not (1 <= start_page <= end_page <= doc.page_count):
                raise ValueError(
                    f"Invalid page range. Start: {start_page}, End: {end_page}. "
                    f"Document has {doc.page_count} pages."
                )
            
            output_paths = []
            source_dir = pdf_path_obj.parent
            base_name = pdf_path_obj.stem
            
            # Process each page in the range
            for page_num in range(start_page, end_page + 1):
                # Get the page (0-based indexing)
                page = doc[page_num - 1]
                
                # Create a pixmap with the specified DPI
                pix = page.get_pixmap(dpi=dpi)
                
                # Create output filename
                output_filename = f"mcp_{base_name}_page_{page_num}.{image_format}"
                output_path = source_dir / output_filename
                
                # Save the image
                pix.save(str(output_path))
                output_paths.append(str(output_path))
                
                # Clean up pixmap
                pix = None
            
            doc.close()
            return output_paths
            
        except Exception as e:
            raise Exception(f"Failed to convert pages to images from '{pdf_path}': {e}")

    def extract_text_from_pages(self, pdf_path: str, start_page: int, end_page: int, markdown: bool = True) -> str:
        """
        Extracts text from a range of pages in a PDF.

        Args:
            pdf_path: The file path to the PDF document.
            start_page: The starting page number (1-based).
            end_page: The ending page number (1-based).
            markdown: Whether to return text in Markdown format (default: True).

        Returns:
            Extracted text as a string, optionally formatted as Markdown.

        Raises:
            Exception: If the file is not found, the page range is invalid, or extraction fails.
        """
        # Convert to Path object for cross-platform compatibility
        pdf_path_obj = Path(pdf_path).resolve()
        
        if not pdf_path_obj.exists():
            raise FileNotFoundError(f"The file was not found at path: {pdf_path}")
            
        try:
            # Open the document to validate page range
            doc = pymupdf.open(str(pdf_path_obj))
            
            # Validate page numbers
            if not (1 <= start_page <= end_page <= doc.page_count):
                doc.close()
                raise ValueError(
                    f"Invalid page range. Start: {start_page}, End: {end_page}. "
                    f"Document has {doc.page_count} pages."
                )
            
            doc.close()
            
            if markdown:
                # Use pymupdf4llm for Markdown extraction
                # Convert to 0-based page numbers for the pages list
                pages_list = list(range(start_page - 1, end_page))
                md_text = pymupdf4llm.to_markdown(str(pdf_path_obj), pages=pages_list)
                return md_text
            else:
                # Use regular PyMuPDF for plain text extraction
                doc = pymupdf.open(str(pdf_path_obj))
                text_content = []
                
                for page_num in range(start_page - 1, end_page):
                    page = doc[page_num]
                    text = page.get_text()
                    text_content.append(f"--- Page {page_num + 1} ---\n{text}")
                
                doc.close()
                return "\n\n".join(text_content)
                
        except Exception as e:
            raise Exception(f"Failed to extract text from '{pdf_path}': {e}")