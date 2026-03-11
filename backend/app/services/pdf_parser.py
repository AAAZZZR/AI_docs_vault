import base64
import logging

import fitz  # PyMuPDF

from app.core.config import settings

logger = logging.getLogger(__name__)


class PDFParserService:
    def __init__(self):
        self.max_pages = settings.PDF_MAX_PAGES
        self.dpi = 200

    def extract_pages_as_images(
        self, pdf_bytes: bytes
    ) -> list[tuple[int, str]]:
        """
        Convert each PDF page to a PNG image (base64).
        Returns: [(page_num_1indexed, base64_string), ...]
        Caps at PDF_MAX_PAGES.
        """
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        total_pages = min(len(doc), self.max_pages)
        pages = []
        mat = fitz.Matrix(self.dpi / 72, self.dpi / 72)

        for page_num in range(total_pages):
            page = doc[page_num]
            pix = page.get_pixmap(matrix=mat)
            img_bytes = pix.tobytes("png")
            b64 = base64.b64encode(img_bytes).decode("utf-8")
            pages.append((page_num + 1, b64))

        doc.close()
        logger.info("Extracted %d pages as images", total_pages)
        return pages

    def get_page_count(self, pdf_bytes: bytes) -> int:
        """Get total page count of a PDF."""
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        count = len(doc)
        doc.close()
        return count

    def extract_text(self, pdf_bytes: bytes) -> list[tuple[int, str]]:
        """
        Extract raw text from each page (fallback for when images aren't needed).
        Returns: [(page_num_1indexed, text), ...]
        """
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        total_pages = min(len(doc), self.max_pages)
        pages = []

        for page_num in range(total_pages):
            page = doc[page_num]
            text = page.get_text()
            if text.strip():
                pages.append((page_num + 1, text))

        doc.close()
        return pages

    def extract_embedded_images(
        self, pdf_bytes: bytes
    ) -> list[dict]:
        """
        Extract embedded images from PDF for separate S3 storage.
        Returns: [{"page": int, "index": int, "bytes": bytes, "extension": str}, ...]
        """
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        images = []

        for page_num in range(min(len(doc), self.max_pages)):
            page = doc[page_num]
            for img_index, img in enumerate(page.get_images(full=True)):
                try:
                    xref = img[0]
                    base_image = doc.extract_image(xref)
                    if base_image:
                        images.append({
                            "page": page_num + 1,
                            "index": img_index,
                            "bytes": base_image["image"],
                            "extension": base_image["ext"],
                        })
                except Exception:
                    logger.warning(
                        "Failed to extract image %d from page %d",
                        img_index, page_num + 1,
                    )

        doc.close()
        logger.info("Extracted %d embedded images", len(images))
        return images


pdf_parser = PDFParserService()
