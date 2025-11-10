import base64
import re
from io import BytesIO
from pdfminer.high_level import extract_text
from pdfminer.pdfdocument import PDFTextExtractionNotAllowed


class PDFProcessor:
    @staticmethod
    def extract_text_from_pdf(pdf_data: str) -> str:
        try:
            pdf_bytes = base64.b64decode(pdf_data)
            text_content = extract_text(BytesIO(pdf_bytes))
            text_content = re.sub(r'\s+', ' ', text_content).strip()
            return text_content
        except PDFTextExtractionNotAllowed:
            print("PDF does not allow text extraction")
            return ""
        except Exception as e:
            print(f"Error extracting PDF text: {str(e)}")
            return ""

    @staticmethod
    def extract_text_from_pdf_preserve_formatting(pdf_data: str) -> str:
        try:
            pdf_bytes = base64.b64decode(pdf_data)
            text_content = extract_text(BytesIO(pdf_bytes))
            text_content = re.sub(r'[ \t]+', ' ', text_content)
            text_content = re.sub(r'\n\s*\n', '\n\n', text_content)
            text_content = text_content.strip()
            return text_content
        except PDFTextExtractionNotAllowed:
            print("PDF does not allow text extraction")
            return ""
        except Exception as e:
            print(f"Error extracting PDF text: {str(e)}")
            return ""

    @staticmethod
    def html_to_text(html_content: str) -> str:
        if not html_content:
            return ""
        html_content = re.sub(r'<script[^>]*>.*?</script>', '', html_content, flags=re.DOTALL)
        html_content = re.sub(r'<style[^>]*>.*?</style>', '', html_content, flags=re.DOTALL)
        html_content = re.sub(r'<br\s*/?>', '\n', html_content, flags=re.IGNORECASE)
        html_content = re.sub(r'<p[^>]*>', '\n\n', html_content, flags=re.IGNORECASE)
        html_content = re.sub(r'</p>', '\n\n', html_content, flags=re.IGNORECASE)
        html_content = re.sub(r'<h[1-6][^>]*>', '\n\n', html_content, flags=re.IGNORECASE)
        html_content = re.sub(r'</h[1-6]>', '\n\n', html_content, flags=re.IGNORECASE)
        html_content = re.sub(r'<li[^>]*>', '\n• ', html_content, flags=re.IGNORECASE)
        html_content = re.sub(r'</li>', '', html_content, flags=re.IGNORECASE)
        html_content = re.sub(r'<[^>]+>', '', html_content)
        html_content = re.sub(r'\n\s*\n', '\n\n', html_content)
        html_content = re.sub(r'[ \t]+', ' ', html_content)
        html_content = html_content.strip()
        return html_content


def extract_text_from_pdf(pdf_data):
    return PDFProcessor.extract_text_from_pdf(pdf_data)

def extract_text_from_pdf_preserve_formatting(pdf_data):
    return PDFProcessor.extract_text_from_pdf_preserve_formatting(pdf_data)

def html_to_text(html_content):
    return PDFProcessor.html_to_text(html_content)