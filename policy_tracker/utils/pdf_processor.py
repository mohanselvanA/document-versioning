import base64
import re
from io import BytesIO
from pdfminer.high_level import extract_text
from pdfminer.pdfdocument import PDFTextExtractionNotAllowed


class PDFProcessor:
    """Service class for PDF processing operations"""
    
    @staticmethod
    def extract_text_from_pdf(pdf_data: str) -> str:
        """
        Extract text content from base64 encoded PDF data using pdfminer
        """
        try:
            # Decode base64 PDF data
            pdf_bytes = base64.b64decode(pdf_data)
            
            # Extract text using pdfminer
            text_content = extract_text(BytesIO(pdf_bytes))
            
            # Clean up the text - remove excessive whitespace
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
        """
        Extract text content from PDF preserving original formatting and spacing
        """
        try:
            # Decode base64 PDF data
            pdf_bytes = base64.b64decode(pdf_data)
            
            # Extract text using pdfminer
            text_content = extract_text(BytesIO(pdf_bytes))
            
            # Preserve original line breaks and spacing
            text_content = re.sub(r'[ \t]+', ' ', text_content)  # Normalize spaces/tabs
            text_content = re.sub(r'\n\s*\n', '\n\n', text_content)  # Preserve paragraph breaks
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
        """
        Convert HTML content to clean text while preserving structure
        """
        if not html_content:
            return ""
        
        # Remove script and style elements
        html_content = re.sub(r'<script[^>]*>.*?</script>', '', html_content, flags=re.DOTALL)
        html_content = re.sub(r'<style[^>]*>.*?</style>', '', html_content, flags=re.DOTALL)
        
        # Replace common HTML tags with appropriate text formatting
        html_content = re.sub(r'<br\s*/?>', '\n', html_content, flags=re.IGNORECASE)
        html_content = re.sub(r'<p[^>]*>', '\n\n', html_content, flags=re.IGNORECASE)
        html_content = re.sub(r'</p>', '\n\n', html_content, flags=re.IGNORECASE)
        
        # Handle headings
        html_content = re.sub(r'<h[1-6][^>]*>', '\n\n', html_content, flags=re.IGNORECASE)
        html_content = re.sub(r'</h[1-6]>', '\n\n', html_content, flags=re.IGNORECASE)
        
        # Handle lists
        html_content = re.sub(r'<li[^>]*>', '\n• ', html_content, flags=re.IGNORECASE)
        html_content = re.sub(r'</li>', '', html_content, flags=re.IGNORECASE)
        
        # Remove all other HTML tags
        html_content = re.sub(r'<[^>]+>', '', html_content)
        
        # Clean up whitespace
        html_content = re.sub(r'\n\s*\n', '\n\n', html_content)  # Preserve paragraph breaks
        html_content = re.sub(r'[ \t]+', ' ', html_content)  # Normalize spaces
        html_content = html_content.strip()
        
        return html_content


# Legacy function aliases for backward compatibility
def extract_text_from_pdf(pdf_data):
    """Legacy function - use PDFProcessor.extract_text_from_pdf instead"""
    return PDFProcessor.extract_text_from_pdf(pdf_data)

def extract_text_from_pdf_preserve_formatting(pdf_data):
    """Legacy function - use PDFProcessor.extract_text_from_pdf_preserve_formatting instead"""
    return PDFProcessor.extract_text_from_pdf_preserve_formatting(pdf_data)

def html_to_text(html_content):
    """Legacy function - use PDFProcessor.html_to_text instead"""
    return PDFProcessor.html_to_text(html_content)


# =============================================================================
# UNUSED FUNCTIONS (COMMENTED OUT FOR NOW)
# =============================================================================

"""
def extract_text_with_fonts(pdf_data):
    # Extract text with font information - not currently used
    pass

def extract_pdf_from_content(content_data):
    # Extract PDF from content structure - not currently used
    pass

def extract_html_from_content(content_data):
    # Extract HTML from content structure - not currently used
    pass

def extract_text_from_html(html_content):
    # Alias for html_to_text - redundant
    pass

def process_content_to_text(content_data):
    # Process content to text - not currently used
    pass

def process_content_for_llm(content_data):
    # Process content for LLM - not currently used
    pass

def get_content_type(content_data):
    # Get content type - not currently used
    pass

def convert_pdf_to_html(pdf_data):
    # Convert PDF to HTML - not currently used
    pass

def process_content(content_data):
    # Process content - not currently used
    pass

def process_content_to_html(content_data):
    # Process content to HTML - not currently used
    pass
"""