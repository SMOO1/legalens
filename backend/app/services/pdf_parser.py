import io
import logging
from pypdf import PdfReader

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """
    Parses a PDF file from bytes and returns all extracted text.
    """
    pdf_stream = io.BytesIO(file_bytes)
    reader = PdfReader(pdf_stream)

    extracted_text = []
    for i, page in enumerate(reader.pages):
        text = page.extract_text()
        if text:
            logger.debug(f"--- Page {i + 1} ---")
            logger.debug(text)
            extracted_text.append(text)

    full_text = "\n".join(extracted_text)
    logger.debug(f"=== Full Extracted Text ({len(reader.pages)} pages) ===")
    logger.debug(full_text)

    return full_text