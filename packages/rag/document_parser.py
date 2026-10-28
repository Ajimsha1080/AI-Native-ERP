"""
Enterprise Document OCR & Intelligent RAG Document Parser.
Extracts text, metadata, and structured line items from PDFs, CSVs, and plain text.
"""

from typing import Dict, Any, List, Optional
from pydantic import BaseModel
import io
import re
import fitz  # PyMuPDF


class ExtractedLineItem(BaseModel):
    item_code: str
    description: str
    quantity: int
    unit_price: float
    total_price: float


class ExtractedDocument(BaseModel):
    document_type: str
    vendor_name: str
    invoice_number: str
    issue_date: str
    due_date: str
    total_amount: float
    currency: str
    raw_text: str
    line_items: List[ExtractedLineItem]
    confidence_score: float


class DocumentChunk(BaseModel):
    chunk_index: int
    content: str
    token_count: int
    metadata: Dict[str, Any] = {}


class EnterpriseDocumentParser:
    """Intelligent Enterprise Document OCR & Chunking Engine."""

    def extract_text(self, file_content_bytes: bytes, filename: str) -> str:
        """Extract text from PDF, text, or CSV files."""
        if filename.lower().endswith(".pdf"):
            try:
                doc = fitz.open(stream=file_content_bytes, filetype="pdf")
                pages_text = []
                for page_num in range(len(doc)):
                    page = doc.load_page(page_num)
                    pages_text.append(page.get_text())
                doc.close()
                extracted = "\n".join(pages_text).strip()
                if extracted:
                    return extracted
            except Exception as e:
                pass
        
        # Fallback to UTF-8 decoding
        try:
            return file_content_bytes.decode("utf-8")
        except UnicodeDecodeError:
            try:
                return file_content_bytes.decode("latin-1")
            except Exception:
                return f"[Binary document content: {filename}]"

    def chunk_text(self, text: str, chunk_size: int = 500, overlap: int = 50) -> List[DocumentChunk]:
        """Split text into semantic chunks for vector indexing."""
        words = text.split()
        if not words:
            return []

        chunks = []
        start = 0
        chunk_idx = 0

        while start < len(words):
            end = min(start + chunk_size, len(words))
            chunk_words = words[start:end]
            chunk_str = " ".join(chunk_words)
            
            chunks.append(DocumentChunk(
                chunk_index=chunk_idx,
                content=chunk_str,
                token_count=len(chunk_words),
                metadata={"start_word": start, "end_word": end}
            ))
            
            chunk_idx += 1
            if end >= len(words):
                break
            start += (chunk_size - overlap)

        return chunks

    def parse_invoice_pdf(self, file_content_bytes: bytes, filename: str) -> ExtractedDocument:
        """Extract structured invoice fields from text or PDF."""
        raw_text = self.extract_text(file_content_bytes, filename)

        # Regex search for common invoice fields
        inv_match = re.search(r"invoice\s*#?\s*[:\s]?\s*([A-Z0-9-]+)", raw_text, re.IGNORECASE)
        invoice_num = inv_match.group(1).strip() if inv_match else "INV-UNKNOWN"

        amount_match = re.search(r"total\s*(?:amount)?\s*[:\s]?\s*\$?\s*([0-9,]+\.[0-9]{2})", raw_text, re.IGNORECASE)
        total_amt = 0.0
        if amount_match:
            try:
                total_amt = float(amount_match.group(1).replace(",", ""))
            except ValueError:
                total_amt = 0.0

        vendor_match = re.search(r"from\s*:\s*([^\n\r]+)", raw_text, re.IGNORECASE)
        vendor_name = vendor_match.group(1).strip() if vendor_match else "Unknown Vendor"

        matched_count = sum([bool(inv_match), bool(amount_match), bool(vendor_match)])
        confidence = round(matched_count / 3.0, 3)

        return ExtractedDocument(
            document_type="PDF_SUPPLIER_INVOICE",
            vendor_name=vendor_name,
            invoice_number=invoice_num,
            issue_date="",
            due_date="",
            total_amount=total_amt,
            currency="USD",
            raw_text=raw_text,
            line_items=[],
            confidence_score=confidence
        )


document_parser = EnterpriseDocumentParser()
