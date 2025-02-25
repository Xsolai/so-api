import os
import base64
import logging
from typing import Union, List
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from PyPDF2 import PdfReader
from PIL import Image, UnidentifiedImageError
import tempfile
import easyocr

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI()

# Define the request model with pages parameter
class FileData(BaseModel):
    data: str  # Base64 encoded data (PDF or Image)
    ext: str   # File extension, expecting '.pdf', '.png', '.jpg', '.jpeg'
    pages: Union[str, List[Union[str, int]]] = "ALL"  # Page selection parameter with default "ALL"

# Initialize the EasyOCR reader for images (English language, no GPU)
ocr_reader = easyocr.Reader(['en'], gpu=False)

def parse_page_selection(pages_param: Union[str, List[Union[str, int]]]) -> Union[str, List[int]]:
    """
    Parse the page selection parameter and return either "ALL" or a list of page numbers.
    
    Examples:
    - "ALL" -> "ALL"
    - "1" -> [1]
    - "2-5" -> [2, 3, 4, 5]
    - "2,5,7" -> [2, 5, 7]
    - "1-3,5,7-9" -> [1, 2, 3, 5, 7, 8, 9]
    """
    # If it's already a list, convert string elements to integers
    if isinstance(pages_param, list):
        result = []
        for p in pages_param:
            if isinstance(p, int):
                result.append(p)
            elif isinstance(p, str) and p.isdigit():
                result.append(int(p))
        return result if result else "ALL"
    
    # If it's a string, parse it
    if isinstance(pages_param, str):
        # Check for "ALL" case (case-insensitive)
        if pages_param.upper() == "ALL":
            return "ALL"
        
        result = []
        # Split by comma to handle different selections
        selections = pages_param.split(',')
        
        for selection in selections:
            selection = selection.strip()
            
            # Handle single page
            if selection.isdigit():
                result.append(int(selection))
            # Handle range (e.g., "2-5")
            elif '-' in selection:
                try:
                    start, end = map(int, selection.split('-'))
                    if start <= end:
                        result.extend(range(start, end + 1))
                    else:
                        logger.warning(f"Invalid range: {selection}. Start should be less than or equal to end.")
                except ValueError:
                    logger.warning(f"Invalid range format: {selection}")
            else:
                logger.warning(f"Ignoring invalid page selection: {selection}")
                
        return sorted(set(result)) if result else "ALL"  # Sort and remove duplicates
    
    # Default to "ALL" if the format is unrecognized
    logger.warning(f"Unrecognized pages parameter format: {pages_param}. Defaulting to ALL.")
    return "ALL"

@app.post("/read-pdf/")
async def read_file(file_data: FileData):
    logger.info(f"Received request to process file with extension {file_data.ext}.")
    
    # Parse page selection
    selected_pages = parse_page_selection(file_data.pages)
    logger.info(f"Page selection: {selected_pages}")

    if file_data.ext == '.pdf':
        # Process PDF
        logger.info("Processing PDF file.")
        temp_file_path = None
        
        try:
            # Decode the base64 PDF data
            pdf_content = base64.b64decode(file_data.data)

            # Create a temporary file to store the PDF
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
                logger.info(f"Writing decoded PDF content to temporary file: {temp_file.name}.")
                temp_file.write(pdf_content)
                temp_file.flush()
                temp_file_path = temp_file.name

                # Read the content of the PDF using PyPDF2
                logger.info(f"Reading content from the PDF file: {temp_file_path}.")
                try:
                    pdf_reader = PdfReader(temp_file_path)
                except Exception as e:
                    logger.error(f"Failed to read the PDF file: {e}")
                    raise HTTPException(status_code=400, detail="Failed to read the PDF file. It might be corrupted.")

                text_content = ""
                
                # Process according to page selection
                if selected_pages == "ALL":
                    # Process all pages
                    logger.info(f"Processing all {len(pdf_reader.pages)} pages")
                    for i, page in enumerate(pdf_reader.pages, 1):
                        page_text = page.extract_text() or ""
                        text_content += f"--- Page {i} ---\n{page_text}\n\n"
                else:
                    # Process only selected pages
                    total_pages = len(pdf_reader.pages)
                    valid_pages = [p for p in selected_pages if 1 <= p <= total_pages]
                    
                    if not valid_pages:
                        logger.warning(f"No valid pages selected. Total pages: {total_pages}, Selected: {selected_pages}")
                        return {"content": "No valid pages selected.", "total_pages": total_pages}
                    
                    logger.info(f"Processing selected pages: {valid_pages} out of {total_pages} total pages")
                    for page_num in valid_pages:
                        # PyPDF2 uses 0-based indexing, but our API uses 1-based indexing for user-friendliness
                        page = pdf_reader.pages[page_num - 1]
                        page_text = page.extract_text() or ""
                        text_content += f"--- Page {page_num} ---\n{page_text}\n\n"

            logger.info("Successfully processed the PDF.")
            return {"content": text_content.strip()}

        except Exception as e:
            logger.error(f"An error occurred while processing the PDF: {str(e)}")
            raise HTTPException(status_code=500, detail=f"An error occurred while processing the PDF: {str(e)}")
        
        finally:
            # Clean up temporary file
            if temp_file_path and os.path.exists(temp_file_path):
                logger.info(f"Removing temporary file: {temp_file_path}.")
                os.remove(temp_file_path)

    elif file_data.ext.lower() in ['.png', '.jpg', '.jpeg']:
        # Process Image (for images, page selection doesn't apply, but we'll keep the API consistent)
        logger.info("Processing image file.")
        temp_file_path = None
        
        try:
            if selected_pages != "ALL" and (isinstance(selected_pages, list) and 1 not in selected_pages):
                logger.warning("Image files only have one page. Ignoring page selection other than page 1.")
                return {"content": "Image files only have one page. Please use 'ALL' or '1' for page selection."}
            
            # Decode the base64 image data
            try:
                image_content = base64.b64decode(file_data.data)
            except base64.binascii.Error as decode_error:
                logger.error("Failed to decode base64 image data.")
                raise HTTPException(status_code=400, detail="Invalid base64 data.") from decode_error

            # Create a temporary file to store the image
            with tempfile.NamedTemporaryFile(delete=False, suffix=file_data.ext) as temp_file:
                logger.info(f"Writing decoded image content to temporary file: {temp_file.name}.")
                temp_file.write(image_content)
                temp_file.flush()
                temp_file_path = temp_file.name

            try:
                # Open the image using Pillow to verify it's valid
                logger.info(f"Opening image file: {temp_file_path}.")
                image = Image.open(temp_file_path)
                image.verify()  # Check if the image is not corrupted
            except UnidentifiedImageError as img_error:
                logger.error("The provided image data is not a valid image.")
                raise HTTPException(status_code=400, detail="Invalid image file.") from img_error

            # Use EasyOCR to extract text from the image
            logger.info(f"Extracting text from image using EasyOCR: {temp_file_path}.")
            text_results = ocr_reader.readtext(temp_file_path, detail=0)  # detail=0 gives only the text

            # Combine the recognized text
            text_content = " ".join(text_results)

            logger.info("Successfully processed the image.")
            return {"content": text_content.strip()}

        except Exception as e:
            logger.error(f"An error occurred while processing the image: {str(e)}")
            raise HTTPException(status_code=500, detail=f"An error occurred while processing the image: {str(e)}")

        finally:
            # Ensure the temporary file is removed even if there's an exception
            if temp_file_path and os.path.exists(temp_file_path):
                logger.info(f"Removing temporary file: {temp_file_path}.")
                os.remove(temp_file_path)

    else:
        logger.error(f"Invalid file extension: {file_data.ext}. Supported extensions are '.pdf', '.png', '.jpg', '.jpeg'.")
        raise HTTPException(status_code=400, detail="Invalid file extension. Supported extensions are '.pdf', '.png', '.jpg', '.jpeg'.")