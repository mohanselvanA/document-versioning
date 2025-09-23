import base64
from io import BytesIO
from pdfminer.high_level import extract_text
from pdfminer.pdfdocument import PDFTextExtractionNotAllowed
import re

def extract_text_from_pdf(pdf_data):
    """Extract text content from base64 encoded PDF data using pdfminer"""
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

def extract_pdf_from_content(content_data):
    """Extract PDF data from content structure"""
    if isinstance(content_data, dict):
        files = content_data.get('files', [])
        for file_info in files:
            if file_info.get('type') == 'application/pdf':
                pdf_data = file_info.get('data', '')
                if pdf_data:
                    return pdf_data
    return None

def extract_html_from_content(content_data):
    """Extract HTML content from content structure"""
    if isinstance(content_data, str):
        return content_data
    elif isinstance(content_data, dict):
        return content_data.get('content', '')
    return ""

def process_content(content_data):
    """Process content - prioritize PDF over HTML"""
    # Try to extract PDF first
    pdf_data = extract_pdf_from_content(content_data)
    if pdf_data:
        pdf_text = extract_text_from_pdf(pdf_data)
        if pdf_text:
            print("Using PDF content")
            return pdf_text
    
    # Fallback to HTML content
    html_content = extract_html_from_content(content_data)
    if html_content:
        print("Using HTML content")
        # Remove HTML tags for clean text processing
        import re
        clean_text = re.sub('<[^<]+?>', ' ', html_content)
        clean_text = re.sub(r'\s+', ' ', clean_text).strip()
        return clean_text
    
    return ""