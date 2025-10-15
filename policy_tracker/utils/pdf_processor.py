import base64
from io import BytesIO
from pdfminer.high_level import extract_text
from pdfminer.pdfdocument import PDFTextExtractionNotAllowed
from pdfminer.layout import LAParams, LTTextContainer, LTTextBox, LTTextLine, LTChar
from pdfminer.converter import PDFPageAggregator
from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
from pdfminer.pdfpage import PDFPage
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

def extract_text_from_pdf_preserve_formatting(pdf_data):
    """Extract text content from PDF preserving original formatting and spacing"""
    try:
        # Decode base64 PDF data
        pdf_bytes = base64.b64decode(pdf_data)
        
        # Extract text using pdfminer
        text_content = extract_text(BytesIO(pdf_bytes))
        
        # Preserve original line breaks and spacing
        # Only clean up excessive spaces/tabs but keep line structure
        text_content = re.sub(r'[ \t]+', ' ', text_content)  # Replace multiple spaces/tabs with single space
        text_content = re.sub(r'\n\s*\n', '\n\n', text_content)  # Preserve paragraph breaks
        text_content = text_content.strip()
        
        return text_content
    except PDFTextExtractionNotAllowed:
        print("PDF does not allow text extraction")
        return ""
    except Exception as e:
        print(f"Error extracting PDF text: {str(e)}")
        return ""

def extract_text_with_fonts(pdf_data):
    """Extract text content from PDF with font information"""
    try:
        # Decode base64 PDF data
        pdf_bytes = base64.b64decode(pdf_data)
        pdf_file = BytesIO(pdf_bytes)
        
        # Set up PDF resource manager
        rsrcmgr = PDFResourceManager()
        
        # Set up layout parameters
        laparams = LAParams(
            char_margin=2.0,
            line_margin=0.5,
            word_margin=0.1,
            boxes_flow=0.5,
            all_texts=True
        )
        
        # Create PDF page aggregator
        device = PDFPageAggregator(rsrcmgr, laparams=laparams)
        interpreter = PDFPageInterpreter(rsrcmgr, device)
        
        html_content = ""
        
        # Process each page
        for page in PDFPage.get_pages(pdf_file, check_extractable=True):
            interpreter.process_page(page)
            layout = device.get_result()
            
            # Extract text with font information
            page_html = extract_text_from_layout(layout)
            html_content += page_html
        
        pdf_file.close()
        return html_content
        
    except Exception as e:
        print(f"Error extracting PDF with fonts: {str(e)}")
        return ""

def extract_text_from_layout(layout):
    """Extract text from layout object with font information and proper spacing"""
    html_content = ""
    previous_element_y = None
    
    for element in layout:
        if isinstance(element, LTTextBox):
            # Check for paragraph breaks between text boxes
            current_y = getattr(element, 'y0', 0)
            if previous_element_y is not None:
                vertical_gap = abs(current_y - previous_element_y)
                if vertical_gap > 20:  # Significant gap indicates new paragraph
                    html_content += "<br><br>"  # Add paragraph spacing
            
            textbox_content = extract_text_from_textbox(element)
            if textbox_content.strip():
                html_content += textbox_content
                previous_element_y = current_y
        elif hasattr(element, '__iter__'):
            # Recursively process nested elements
            nested_content = extract_text_from_layout(element)
            if nested_content.strip():
                html_content += nested_content
    
    return html_content

def extract_text_from_textbox(textbox):
    """Extract text from textbox with font styling and proper line breaks"""
    html_content = ""
    previous_line_y = None
    
    for line in textbox:
        if isinstance(line, LTTextLine):
            line_html = extract_text_from_line(line)
            if line_html.strip():
                # Check if this is a new paragraph based on vertical spacing
                current_y = getattr(line, 'y0', 0)
                if previous_line_y is not None:
                    # If there's significant vertical gap, it might be a paragraph break
                    vertical_gap = abs(current_y - previous_line_y)
                    if vertical_gap > 15:  # Adjust threshold as needed
                        html_content += "<br>"  # Add extra line break for paragraph spacing
                
                html_content += f"<div>{line_html}</div>\n"
                previous_line_y = current_y
    
    return html_content

def extract_text_from_line(line):
    """Extract text from line with font styling and preserve line breaks"""
    line_html = ""
    current_font = None
    current_size = None
    current_weight = "normal"
    
    for char in line:
        if isinstance(char, LTChar):
            # Get font information
            font_name = getattr(char, 'fontname', 'Arial')
            font_size = getattr(char, 'size', 12)
            
            # Determine font weight based on font name
            if 'bold' in font_name.lower() or 'black' in font_name.lower():
                weight = "bold"
            elif 'light' in font_name.lower() or 'thin' in font_name.lower():
                weight = "lighter"
            else:
                weight = "normal"
            
            # Check if we need to open/close font tags
            if font_name != current_font or font_size != current_size or weight != current_weight:
                # Close previous font tag if exists
                if current_font is not None:
                    line_html += "</span>"
                
                # Open new font tag
                style = f"font-family: '{font_name}', Arial, sans-serif; font-size: {font_size}px; font-weight: {weight};"
                line_html += f'<span style="{style}">'
                
                current_font = font_name
                current_size = font_size
                current_weight = weight
            
            # Add the character
            char_text = char.get_text()
            if char_text:
                # Escape HTML special characters
                char_text = char_text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                line_html += char_text
    
    # Close the last font tag
    if current_font is not None:
        line_html += "</span>"
    
    # Add line break at the end of each line
    line_html += "<br>"
    
    return line_html

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

def html_to_text(html_content):
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
    
    # Handle list items
    html_content = re.sub(r'<li[^>]*>', '\n• ', html_content, flags=re.IGNORECASE)
    html_content = re.sub(r'</li>', '', html_content, flags=re.IGNORECASE)
    
    # Remove other HTML tags but preserve content
    html_content = re.sub(r'<[^>]+>', ' ', html_content)
    
    # Handle HTML entities
    html_content = re.sub(r'&nbsp;', ' ', html_content, flags=re.IGNORECASE)
    html_content = re.sub(r'&amp;', '&', html_content, flags=re.IGNORECASE)
    html_content = re.sub(r'&lt;', '<', html_content, flags=re.IGNORECASE)
    html_content = re.sub(r'&gt;', '>', html_content, flags=re.IGNORECASE)
    html_content = re.sub(r'&quot;', '"', html_content, flags=re.IGNORECASE)
    html_content = re.sub(r'&#39;', "'", html_content, flags=re.IGNORECASE)
    
    # Clean up whitespace
    html_content = re.sub(r'\n\s*\n', '\n\n', html_content)  # Preserve paragraph breaks
    html_content = re.sub(r'[ \t]+', ' ', html_content)  # Collapse multiple spaces/tabs
    html_content = re.sub(r'\n +', '\n', html_content)  # Remove spaces after newlines
    html_content = html_content.strip()
    
    return html_content

def extract_text_from_html(html_content):
    """
    Extract clean text from HTML content - alias for html_to_text for consistency
    """
    return html_to_text(html_content)

def process_content_to_text(content_data):
    """
    Process content and return clean text - handles both PDF and HTML input
    """
    # Try to extract PDF first
    pdf_data = extract_pdf_from_content(content_data)
    if pdf_data:
        pdf_text = extract_text_from_pdf_preserve_formatting(pdf_data)
        if pdf_text:
            print("Using PDF content converted to text")
            return pdf_text
    
    # If content_data is a string, it might be HTML
    if isinstance(content_data, str):
        html_text = html_to_text(content_data)
        if html_text:
            print("Using HTML content converted to text")
            return html_text
    
    # If content_data is a dict with content field
    if isinstance(content_data, dict):
        html_content = content_data.get('content', '')
        if html_content:
            html_text = html_to_text(html_content)
            if html_text:
                print("Using content field converted to text")
                return html_text
    
    return ""

def process_content_for_llm(content_data):
    """
    Process content for LLM consumption - returns clean text suitable for AI processing
    """
    text_content = process_content_to_text(content_data)
    
    # Additional cleaning for LLM
    if text_content:
        # Remove excessive line breaks but preserve paragraphs
        text_content = re.sub(r'\n{3,}', '\n\n', text_content)
        # Ensure proper encoding
        text_content = text_content.encode('utf-8', 'ignore').decode('utf-8')
    
    return text_content

def get_content_type(content_data):
    """
    Determine the type of content provided
    Returns: 'pdf', 'html', or 'unknown'
    """
    if isinstance(content_data, dict):
        files = content_data.get('files', [])
        for file_info in files:
            if file_info.get('type') == 'application/pdf':
                return 'pdf'
        
        if content_data.get('content'):
            return 'html'
    
    elif isinstance(content_data, str):
        # Check if it looks like HTML
        if re.search(r'<[^>]+>', content_data):
            return 'html'
        else:
            return 'text'
    
    return 'unknown'

def convert_pdf_to_html(pdf_data):
    """Convert PDF data to HTML format preserving original fonts and formatting"""
    try:
        # First try to extract with font information
        html_content = extract_text_with_fonts(pdf_data)
        
        if not html_content or not html_content.strip():
            # Fallback to basic text extraction if font extraction fails
            pdf_text = extract_text_from_pdf_preserve_formatting(pdf_data)
            if not pdf_text:
                return ""
            
            # Convert text to HTML preserving line breaks and structure
            paragraphs = pdf_text.split('\n\n')
            html_content = ""
            
            for paragraph in paragraphs:
                paragraph = paragraph.strip()
                if paragraph:
                    # Preserve line breaks within paragraphs by converting \n to <br>
                    paragraph_html = paragraph.replace('\n', '<br>')
                    html_content += f"<p>{paragraph_html}</p>\n"
        
        # Wrap everything in a basic HTML structure
        html_document = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>PDF Content</title>
    <style>
        body {{ 
            margin: 20px; 
            line-height: 1.4;
            white-space: pre-line;
        }}
        div {{ 
            margin-bottom: 0; 
            margin-top: 0;
            display: block;
        }}
        p {{ 
            margin-bottom: 12px; 
            margin-top: 0;
        }}
        br {{
            line-height: 1.2;
        }}
    </style>
</head>
<body>
{html_content}
</body>
</html>"""
        
        return html_document
    except Exception as e:
        print(f"Error converting PDF to HTML: {str(e)}")
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

def process_content_to_html(content_data):
    """Process content and return HTML format - prioritize PDF over HTML"""
    # Try to extract PDF first and convert to HTML
    pdf_data = extract_pdf_from_content(content_data)
    if pdf_data:
        html_content = convert_pdf_to_html(pdf_data)
        if html_content:
            print("Using PDF content converted to HTML")
            return html_content
    
    # Fallback to HTML content
    html_content = extract_html_from_content(content_data)
    if html_content:
        print("Using HTML content")
        return html_content
    
    return ""