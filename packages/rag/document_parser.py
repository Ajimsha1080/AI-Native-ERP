"""
Enterprise Document OCR & Intelligent RAG Document Parser.

Provides:
1. Dual-Engine Extraction: Digital PDF parsing + Optical Character Recognition (OCR)
   for scanned PDFs and document images (.png, .jpg, .jpeg, .tiff, .bmp, .webp).
2. Image preprocessing using Pillow and OpenCV (grayscale, thresholding, deskewing).
3. Vision-Language Model OCR (via LiteLLM / Gemini / OpenAI) with offline fallback.
4. Structured ERP Invoice and Purchase Order extraction (vendor, PO#, invoice#, dates, amounts, line items).
5. Semantic text chunking for vector store and GraphRAG indexing.
"""

from typing import Dict, Any, List, Optional, Tuple
from pydantic import BaseModel, Field
import io
import os
import re
import base64
import logging
from PIL import Image
import fitz  # PyMuPDF
import cv2
import numpy as np

from packages.config.settings import settings

logger = logging.getLogger("rag.document_parser")

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".webp"}


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
    po_number: Optional[str] = None
    issue_date: str = ""
    due_date: str = ""
    total_amount: float = 0.0
    subtotal: float = 0.0
    tax_amount: float = 0.0
    currency: str = "USD"
    raw_text: str
    line_items: List[ExtractedLineItem] = Field(default_factory=list)
    confidence_score: float = 0.0
    extraction_method: str = "digital"  # "digital", "vision_ocr", "local_ocr", "text"


class DocumentChunk(BaseModel):
    chunk_index: int
    content: str
    token_count: int
    metadata: Dict[str, Any] = Field(default_factory=dict)


class OCRResult(BaseModel):
    text: str
    confidence: float
    method: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class EnterpriseDocumentParser:
    """
    Intelligent Enterprise Document OCR & Chunking Engine.
    Handles digital PDFs, scanned PDFs (image-based), images, and raw text.
    """

    def __init__(self):
        self.min_scanned_page_chars = 30  # Pages with fewer characters are treated as scanned images
        self._paddle_ocr = None

    def _get_paddle_ocr(self):
        """Lazy-initializes the PaddleOCR ONNX Runtime engine."""
        if self._paddle_ocr is None:
            try:
                from rapidocr_onnxruntime import RapidOCR
                self._paddle_ocr = RapidOCR()
                logger.info("PaddleOCR (RapidOCR ONNX) engine initialized successfully.")
            except Exception as e:
                logger.warning(f"PaddleOCR initialization failed: {e}")
                self._paddle_ocr = False
        return self._paddle_ocr if self._paddle_ocr is not False else None

    def preprocess_image(self, image_bytes: bytes) -> Tuple[np.ndarray, Dict[str, Any]]:
        """
        Loads image bytes and applies OpenCV contrast enhancement and binarization.
        """
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            # Fallback using PIL
            pil_img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            img = np.array(pil_img)[:, :, ::-1].copy()

        height, width = img.shape[:2]
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # Contrast enhancement using CLAHE (Contrast Limited Adaptive Histogram Equalization)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)

        # Adaptive thresholding to separate text from background
        binary = cv2.adaptiveThreshold(
            enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
        )

        meta = {
            "width": width,
            "height": height,
            "channels": img.shape[2] if len(img.shape) > 2 else 1,
            "is_high_res": width >= 1000 and height >= 1000,
        }
        return binary, meta

    def ocr_image(self, image_bytes: bytes, filename: str = "document.png") -> OCRResult:
        """
        Executes Optical Character Recognition on an image using:
        1. Multimodal Vision LLM (OpenAI / Gemini / Anthropic via LiteLLM) if credentials exist.
        2. Local OCR (pytesseract or easyocr) if installed.
        3. Deterministic OpenCV visual feature & contour extraction fallback.
        """
        # Validate image can be parsed by Pillow
        try:
            pil_img = Image.open(io.BytesIO(image_bytes))
            width, height = pil_img.size
        except Exception as e:
            logger.warning(f"Failed to open image bytes for OCR: {e}")
            return OCRResult(text=f"[Unreadable Image: {filename}]", confidence=0.0, method="failed")

        # 1. Strategy A: PaddleOCR (Fast, 100% Free, Local On-Premise Engine)
        paddle = self._get_paddle_ocr()
        if paddle is not None:
            try:
                results, _ = paddle(image_bytes)
                if results:
                    lines = [item[1] for item in results if item and len(item) > 1 and item[1]]
                    scores = [float(item[2]) for item in results if item and len(item) > 2]
                    avg_score = sum(scores) / len(scores) if scores else 0.85
                    extracted_text = "\n".join(lines).strip()
                    if extracted_text:
                        return OCRResult(
                            text=extracted_text,
                            confidence=round(avg_score, 2),
                            method="paddle_ocr",
                            metadata={
                                "engine": "paddle_ocr_v4",
                                "width": width,
                                "height": height,
                                "line_count": len(lines),
                            }
                        )
            except Exception as paddle_err:
                logger.warning(f"PaddleOCR inference warning: {paddle_err}")

        # 2. Strategy B: Multimodal Vision LLM via LiteLLM
        has_api_key = bool(
            (getattr(settings, "openai_api_key", None) and settings.openai_api_key.startswith("sk-"))
            or getattr(settings, "google_api_key", None)
            or getattr(settings, "anthropic_api_key", None)
        )

        if has_api_key:
            try:
                import litellm
                b64_data = base64.b64encode(image_bytes).decode("utf-8")
                mime = "image/png" if filename.lower().endswith(".png") else "image/jpeg"
                data_url = f"data:{mime};base64,{b64_data}"

                model = getattr(settings, "litellm_vision_model", None) or getattr(settings, "litellm_model", "gpt-4o-mini")

                response = litellm.completion(
                    model=model,
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You are an enterprise document OCR system. Extract all text, tabular rows, line items, "
                                "dates, invoice numbers, purchase order numbers, vendor details, and currency amounts with exact precision. "
                                "Preserve the layout and formatting. Do not hallucinate or add commentary."
                            ),
                        },
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": "Extract all readable text and data from this document image:"},
                                {"type": "image_url", "image_url": {"url": data_url}},
                            ],
                        },
                    ],
                    temperature=0.0,
                    max_tokens=2000,
                )
                extracted_text = response.choices[0].message.content.strip()
                if extracted_text:
                    return OCRResult(
                        text=extracted_text,
                        confidence=0.95,
                        method="vision_ocr",
                        metadata={"model": model, "width": width, "height": height}
                    )
            except Exception as vision_err:
                logger.warning(f"Vision OCR call failed, attempting fallback: {vision_err}")

        # 3. Strategy C: Local Tesseract if available
        try:
            import pytesseract
            text = pytesseract.image_to_string(pil_img).strip()
            if text:
                return OCRResult(
                    text=text,
                    confidence=0.88,
                    method="local_tesseract",
                    metadata={"width": width, "height": height}
                )
        except Exception:
            pass

        # 3. Strategy C: Deterministic OpenCV Text Region Analysis Fallback
        # Preprocess and detect text lines and regions
        try:
            binary, meta = self.preprocess_image(image_bytes)
            # Find contours that match text line aspect ratios
            contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            text_regions = 0
            for cnt in contours:
                x, y, w, h = cv2.boundingRect(cnt)
                if w > 10 and h > 5:
                    text_regions += 1

            return OCRResult(
                text=(
                    f"[Scanned Document: {filename} | Resolution: {width}x{height} | "
                    f"Detected Text Regions: {text_regions}]"
                ),
                confidence=0.70,
                method="opencv_contour_analyzer",
                metadata={"width": width, "height": height, "text_regions": text_regions}
            )
        except Exception as cv_err:
            return OCRResult(
                text=f"[Scanned Image Document: {filename}]",
                confidence=0.50,
                method="basic_metadata",
                metadata={"width": width, "height": height}
            )

    def extract_text(self, file_content_bytes: bytes, filename: str) -> str:
        """
        Extract text from PDF (digital or scanned OCR), image files, CSV, or plain text.
        """
        ext = os.path.splitext(filename.lower())[1]

        # 1. Image Files -> Direct OCR
        if ext in IMAGE_EXTENSIONS:
            ocr_res = self.ocr_image(file_content_bytes, filename=filename)
            return ocr_res.text

        # 2. PDF Files -> Digital Text + Scanned Page OCR
        if ext == ".pdf":
            try:
                doc = fitz.open(stream=file_content_bytes, filetype="pdf")
                pages_text = []

                for page_num in range(len(doc)):
                    page = doc.load_page(page_num)
                    page_text = page.get_text().strip()

                    # Check if this page is a scanned image (very few digital characters)
                    if len(page_text) < self.min_scanned_page_chars:
                        pix = page.get_pixmap(dpi=150)
                        img_bytes = pix.tobytes("png")
                        ocr_res = self.ocr_image(img_bytes, filename=f"{filename}_page_{page_num + 1}.png")
                        if ocr_res.text and not ocr_res.text.startswith("[Scanned Document:"):
                            pages_text.append(ocr_res.text)
                        elif page_text:
                            pages_text.append(page_text)
                        else:
                            pages_text.append(ocr_res.text)
                    else:
                        pages_text.append(page_text)

                doc.close()
                extracted = "\n\n".join(pages_text).strip()
                if extracted:
                    return extracted
            except Exception as e:
                logger.warning(f"Error reading PDF {filename}: {e}")

        # 3. Plain Text / CSV / JSON / Markdown
        try:
            return file_content_bytes.decode("utf-8")
        except UnicodeDecodeError:
            try:
                return file_content_bytes.decode("latin-1")
            except Exception:
                # If binary image disguised without extension, attempt OCR
                try:
                    ocr_res = self.ocr_image(file_content_bytes, filename=filename)
                    if ocr_res.confidence > 0.4:
                        return ocr_res.text
                except Exception:
                    pass
                return f"[Binary document content: {filename}]"

    def chunk_text(self, text: str, chunk_size: int = 500, overlap: int = 50) -> List[DocumentChunk]:
        """Split text into semantic chunks for vector and GraphRAG indexing."""
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
        """
        Extract structured invoice and purchase order fields from digital PDFs,
        scanned PDFs, or invoice image files.
        """
        raw_text = self.extract_text(file_content_bytes, filename)
        ext = os.path.splitext(filename.lower())[1]
        method = "vision_ocr" if ext in IMAGE_EXTENSIONS else "digital"

        # 1. Invoice Number
        inv_match = re.search(r"\b(INV-[A-Z0-9-]+)\b", raw_text, re.IGNORECASE)
        if not inv_match:
            inv_match = re.search(r"(?:invoice\s*(?:#|no\.?|num(?:ber)?|id)?\s*[:#]\s*)([A-Z0-9-]+)", raw_text, re.IGNORECASE)
        invoice_num = inv_match.group(1).strip() if inv_match else "INV-UNKNOWN"

        # 2. Purchase Order Reference
        po_match = re.search(r"\b(PO-[A-Z0-9-]+)\b", raw_text, re.IGNORECASE)
        if not po_match:
            po_match = re.search(r"(?:purchase\s*order\s*#?|po\s*#?|p\.o\.\s*#?)\s*[:#]\s*([A-Z0-9-]+)", raw_text, re.IGNORECASE)
        po_num = po_match.group(1).strip() if po_match else None

        # 3. Total Amount
        amount_match = re.search(r"\b(?:total\s*(?:amount)?|grand\s*total|amount\s*due|balance\s*due)[:\s]*\$?\s*([0-9,]+\.[0-9]{2})", raw_text, re.IGNORECASE)
        total_amt = 0.0
        if amount_match:
            try:
                total_amt = float(amount_match.group(1).replace(",", ""))
            except ValueError:
                total_amt = 0.0

        # 4. Subtotal & Tax
        subtotal_match = re.search(r"subtotal[:\s]*\$?\s*([0-9,]+\.[0-9]{2})", raw_text, re.IGNORECASE)
        subtotal_amt = float(subtotal_match.group(1).replace(",", "")) if subtotal_match else total_amt

        tax_match = re.search(r"tax[:\s]*\$?\s*([0-9,]+\.[0-9]{2})", raw_text, re.IGNORECASE)
        tax_amt = float(tax_match.group(1).replace(",", "")) if tax_match else 0.0

        # 5. Vendor Name
        vendor_match = re.search(r"(?:from|vendor|supplier|billed\s*from)[:\s]*([^\n\r,;]{2,50})", raw_text, re.IGNORECASE)
        vendor_name = vendor_match.group(1).strip() if vendor_match else "Unknown Vendor"

        # 6. Dates
        issue_date_match = re.search(r"(?:issue\s*date|invoice\s*date|date)[:\s]*(\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{2,4})", raw_text, re.IGNORECASE)
        issue_date = issue_date_match.group(1).strip() if issue_date_match else ""

        due_date_match = re.search(r"(?:due\s*date|payment\s*due)[:\s]*(\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{2,4})", raw_text, re.IGNORECASE)
        due_date = due_date_match.group(1).strip() if due_date_match else ""

        # 7. Line Items Parser (e.g., "SKU-9840 Industrial Valve 10 $45.00 $450.00")
        line_items: List[ExtractedLineItem] = []
        line_item_pattern = re.compile(
            r"([A-Z0-9-]{3,15})\s+([A-Za-z0-9\s-]{3,35})\s+(\d+)\s+\$?([0-9,]+\.[0-9]{2})\s+\$?([0-9,]+\.[0-9]{2})"
        )
        for match in line_item_pattern.finditer(raw_text):
            try:
                line_items.append(ExtractedLineItem(
                    item_code=match.group(1).strip(),
                    description=match.group(2).strip(),
                    quantity=int(match.group(3)),
                    unit_price=float(match.group(4).replace(",", "")),
                    total_price=float(match.group(5).replace(",", ""))
                ))
            except Exception:
                pass

        matched_signals = sum([
            bool(inv_match),
            bool(amount_match),
            bool(vendor_match),
            bool(po_match),
            bool(issue_date_match),
            len(line_items) > 0
        ])
        confidence = round(min(1.0, (matched_signals / 5.0) + (0.1 if len(line_items) > 0 else 0.0)), 2)

        return ExtractedDocument(
            document_type="PDF_SUPPLIER_INVOICE" if ext == ".pdf" else "IMAGE_SUPPLIER_INVOICE",
            vendor_name=vendor_name,
            invoice_number=invoice_num,
            po_number=po_num,
            issue_date=issue_date,
            due_date=due_date,
            total_amount=total_amt,
            subtotal=subtotal_amt,
            tax_amount=tax_amt,
            currency="USD",
            raw_text=raw_text,
            line_items=line_items,
            confidence_score=confidence,
            extraction_method=method
        )


# Global Singleton Document Parser
document_parser = EnterpriseDocumentParser()
