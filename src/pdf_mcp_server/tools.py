"""MCP tools for PDF operations using PyMuPDF."""

import pymupdf
import tempfile
import os
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
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"The file was not found at path: {pdf_path}")
            
        try:
            source_doc = pymupdf.open(pdf_path)

            # Validate page numbers
            if not (1 <= start_page <= end_page <= source_doc.page_count):
                raise ValueError(
                    f"Invalid page range. Start: {start_page}, End: {end_page}. "
                    f"Document has {source_doc.page_count} pages."
                )

            new_doc = pymupdf.open()  # Create a new, empty PDF
            # PyMuPDF uses 0-based indexing for pages
            new_doc.insert_pdf(source_doc, from_page=start_page - 1, to_page=end_page - 1)

            # Save to a temporary file
            temp_dir = tempfile.gettempdir()
            # Create a unique filename to avoid collisions
            base_name = os.path.splitext(os.path.basename(pdf_path))[0]
            output_filename = f"{base_name}_pages_{start_page}_to_{end_page}.pdf"
            output_path = os.path.join(temp_dir, output_filename)
            
            new_doc.save(output_path, garbage=4, deflate=True)
            new_doc.close()
            source_doc.close()

            return output_path
        except Exception as e:
            raise Exception(f"Failed to extract pages from '{pdf_path}': {e}")