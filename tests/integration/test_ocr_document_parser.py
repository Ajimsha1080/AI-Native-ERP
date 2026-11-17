"""
Integration Tests for Enterprise OCR and Intelligent Document Parser.

Verifies:
1. Digital PDF text extraction.
2. Scanned PDF page detection and OCR handling.
3. Direct Image OCR (.png, .jpg, .webp) with OpenCV preprocessing.
4. Structured Invoice & PO parsing (vendor, invoice#, po#, dates, amounts, line items).
5. Document chunking for vector and GraphRAG indexing.
6. Corrupt / empty file error resilience.
"""

import io
import pytest
from PIL import Image, ImageDraw
import fitz  # PyMuPDF

from packages.rag.document_parser import (
    document_parser,
    EnterpriseDocumentParser,
    ExtractedDocument,
    OCRResult,
    DocumentChunk,
)


def create_test_image(text: str = "INVOICE #INV-8821\nTOTAL: $4,500.00\nVENDOR: Apex Supply") -> bytes:
    """Helper to generate an in-memory PNG image containing text."""
    img = Image.new("RGB", (600, 300), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.text((20, 30), text, fill=(0, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def create_scanned_pdf_bytes(image_bytes: bytes) -> bytes:
    """Helper to create a PDF whose page contains an image without a digital text layer."""
    doc = fitz.open()
    page = doc.new_page(width=600, height=300)
    rect = fitz.Rect(0, 0, 600, 300)
    page.insert_image(rect, stream=image_bytes)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def create_digital_pdf_bytes(text: str) -> bytes:
    """Helper to create a digital PDF with a native text layer."""
    doc = fitz.open()
    page = doc.new_page(width=600, height=300)
    page.insert_text((30, 50), text, fontsize=12)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


# ─────────────────────────────────────────────────────────────────────────────
# 1. DIGITAL PDF EXTRACTION
# ─────────────────────────────────────────────────────────────────────────────

def test_digital_pdf_text_extraction():
    sample_text = (
        "Purchase Order PO-7710 issued to Vendor Nordic Logistics. "
        "Total Amount: $18,450.00 for SKU-NOR-99. Net 30 payment terms."
    )
    pdf_bytes = create_digital_pdf_bytes(sample_text)

    extracted = document_parser.extract_text(pdf_bytes, filename="test_po.pdf")
    assert "PO-7710" in extracted
    assert "Nordic Logistics" in extracted
    assert "18,450.00" in extracted


# ─────────────────────────────────────────────────────────────────────────────
# 2. SCANNED PDF OCR DETECTION & EXTRACTION
# ─────────────────────────────────────────────────────────────────────────────

def test_scanned_pdf_detection_and_ocr():
    img_bytes = create_test_image("Vendor Apex Supply\nInvoice #INV-8821\nTotal: $4,500.00")
    scanned_pdf = create_scanned_pdf_bytes(img_bytes)

    # Scanned PDF has 0 digital text characters, triggering the OCR pipeline
    extracted = document_parser.extract_text(scanned_pdf, filename="scanned_invoice.pdf")
    assert extracted is not None
    assert len(extracted) > 0


# ─────────────────────────────────────────────────────────────────────────────
# 3. DIRECT IMAGE OCR (.PNG, .JPG)
# ─────────────────────────────────────────────────────────────────────────────

def test_image_ocr_png_and_metadata():
    img_bytes = create_test_image("CONFIDENTIAL CONTRACT\nVendor: Global Metals\nPO-9002")

    ocr_res = document_parser.ocr_image(img_bytes, filename="contract_scan.png")
    assert isinstance(ocr_res, OCRResult)
    assert ocr_res.confidence >= 0.50
    assert ocr_res.metadata.get("width") == 600
    assert ocr_res.metadata.get("height") == 300

    # Direct extract_text on image file
    text = document_parser.extract_text(img_bytes, filename="contract_scan.png")
    assert text is not None
    assert len(text) > 0


def test_paddle_ocr_engine_active():
    """Validates that PaddleOCR executes locally without requiring API keys."""
    img_bytes = create_test_image("INVOICE: INV-9921\nVENDOR: GLOBAL METALS")
    ocr_res = document_parser.ocr_image(img_bytes, filename="invoice_scan.png")
    assert ocr_res.method == "paddle_ocr"
    assert "INV-9921" in ocr_res.text or "GLOBAL" in ocr_res.text
    assert ocr_res.confidence >= 0.70


def test_image_preprocessing_opencv():
    img_bytes = create_test_image("Test Preprocessing Document")
    binary_mat, meta = document_parser.preprocess_image(img_bytes)

    assert meta["width"] == 600
    assert meta["height"] == 300
    assert binary_mat is not None
    assert binary_mat.shape == (300, 600)


# ─────────────────────────────────────────────────────────────────────────────
# 4. STRUCTURED INVOICE & PO FIELD PARSER
# ─────────────────────────────────────────────────────────────────────────────

def test_parse_invoice_structured_fields():
    invoice_text = (
        "TAX INVOICE\n"
        "From: Acme Industrial Solutions Corp\n"
        "Invoice #: INV-2026-9041\n"
        "PO #: PO-88301\n"
        "Issue Date: 2026-08-15\n"
        "Due Date: 2026-09-15\n"
        "Subtotal: $4,000.00\n"
        "Tax: $500.00\n"
        "Total Amount: $4,500.00\n\n"
        "Line Items:\n"
        "SKU-8821 Heavy Duty Valve 10 $400.00 $4,000.00\n"
    )
    pdf_bytes = create_digital_pdf_bytes(invoice_text)

    doc: ExtractedDocument = document_parser.parse_invoice_pdf(pdf_bytes, filename="invoice_9041.pdf")

    assert doc.invoice_number == "INV-2026-9041"
    assert doc.po_number == "PO-88301"
    assert "Acme Industrial" in doc.vendor_name
    assert doc.total_amount == 4500.00
    assert doc.subtotal == 4000.00
    assert doc.tax_amount == 500.00
    assert doc.issue_date == "2026-08-15"
    assert doc.due_date == "2026-09-15"
    assert len(doc.line_items) >= 1
    assert doc.line_items[0].item_code == "SKU-8821"
    assert doc.line_items[0].quantity == 10
    assert doc.line_items[0].unit_price == 400.00
    assert doc.confidence_score >= 0.70


# ─────────────────────────────────────────────────────────────────────────────
# 5. SEMANTIC CHUNKING
# ─────────────────────────────────────────────────────────────────────────────

def test_document_chunking():
    text = "word " * 1200
    chunks = document_parser.chunk_text(text, chunk_size=500, overlap=50)

    assert len(chunks) == 3
    assert chunks[0].chunk_index == 0
    assert chunks[0].token_count == 500
    assert chunks[1].chunk_index == 1
    assert chunks[2].chunk_index == 2
    assert chunks[0].metadata["start_word"] == 0


# ─────────────────────────────────────────────────────────────────────────────
# 6. RESILIENCE ON EMPTY & CORRUPT DATA
# ─────────────────────────────────────────────────────────────────────────────

def test_corrupt_and_empty_file_resilience():
    empty_result = document_parser.extract_text(b"", filename="empty.pdf")
    assert empty_result == ""

    corrupt_image_result = document_parser.ocr_image(b"not_an_image_binary", filename="bad.png")
    assert corrupt_image_result.confidence == 0.0
    assert "Unreadable" in corrupt_image_result.text

    corrupt_pdf_result = document_parser.extract_text(b"%PDF-corrupt-data", filename="bad.pdf")
    assert corrupt_pdf_result is not None
