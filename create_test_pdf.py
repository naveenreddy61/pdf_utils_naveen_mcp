"""Create a simple test PDF for testing the async OCR system."""

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
import os

def create_test_pdf():
    filename = "test_ocr_document.pdf"
    doc = canvas.Canvas(filename, pagesize=letter)
    width, height = letter
    
    # Page 1: Simple text
    doc.setFont("Helvetica-Bold", 16)
    doc.drawString(100, height - 100, "Page 1: Simple Text Content")
    doc.setFont("Helvetica", 12)
    doc.drawString(100, height - 150, "This is regular text that should be easy to extract.")
    doc.drawString(100, height - 180, "It includes some numbers: 123, 456, and 789.")
    doc.drawString(100, height - 210, "And some special characters: @#$%^&*()")
    doc.showPage()
    
    # Page 2: Text with pseudo-math (using regular text)
    doc.setFont("Helvetica-Bold", 16)
    doc.drawString(100, height - 100, "Page 2: Mathematical-like Content")
    doc.setFont("Helvetica", 12)
    doc.drawString(100, height - 150, "Mathematical expressions (as text):")
    doc.drawString(100, height - 180, "y = mx + b")
    doc.drawString(100, height - 210, "∫ f(x) dx = F(x) + C")
    doc.drawString(100, height - 240, "∑(i=1 to n) xi = x1 + x2 + ... + xn")
    doc.drawString(100, height - 270, "α + β = γ")
    doc.showPage()
    
    # Page 3: Mixed content
    doc.setFont("Helvetica-Bold", 16)
    doc.drawString(100, height - 100, "Page 3: Mixed Content")
    doc.setFont("Helvetica", 12)
    doc.drawString(100, height - 150, "This page combines regular text with formulas.")
    doc.drawString(100, height - 180, "The quadratic formula is: x = (-b ± √(b²-4ac)) / 2a")
    doc.drawString(100, height - 210, "Einstein's famous equation: E = mc²")
    doc.drawString(100, height - 240, "And some regular text to test mixed processing.")
    doc.showPage()
    
    doc.save()
    print(f"Created test PDF: {filename}")
    return filename

if __name__ == "__main__":
    create_test_pdf()