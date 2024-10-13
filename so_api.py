import os
import base64
import logging
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

# Define the request model
class FileData(BaseModel):
    data: str  # Base64 encoded data (PDF or Image)
    ext: str   # File extension, expecting '.pdf', '.png', '.jpg', '.jpeg'

# Initialize the EasyOCR reader for images (English language, no GPU)
ocr_reader = easyocr.Reader(['en'], gpu=False)

@app.post("/read-pdf/")
async def read_file(file_data: FileData):
    logger.info(f"Received request to process file with extension {file_data.ext}.")

    if file_data.ext == '.pdf':
        # Process PDF
        logger.info("Processing PDF file.")
        try:
            # Decode the base64 PDF data
            pdf_content = base64.b64decode(file_data.data)

            # Create a temporary file to store the PDF
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
                logger.info(f"Writing decoded PDF content to temporary file: {temp_file.name}.")
                temp_file.write(pdf_content)
                temp_file.flush()

                # Read the content of the PDF using PyPDF2
                logger.info(f"Reading content from the PDF file: {temp_file.name}.")
                try:
                    pdf_reader = PdfReader(temp_file.name)
                except Exception as e:
                    logger.error(f"Failed to read the PDF file: {e}")
                    raise HTTPException(status_code=400, detail="Failed to read the PDF file. It might be corrupted.")

                text_content = ""
                for page in pdf_reader.pages:
                    text_content += page.extract_text() or ""  # Handle possible None values

            logger.info("Successfully processed the PDF.")
            return {"content": text_content.strip()}

        except Exception as e:
            logger.error(f"An error occurred while processing the PDF: {str(e)}")
            raise HTTPException(status_code=500, detail=f"An error occurred while processing the PDF: {str(e)}")

    elif file_data.ext.lower() in ['.png', '.jpg', '.jpeg']:
        # Process Image
        logger.info("Processing image file.")
        try:
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
                os.remove(temp_file_path)
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
            if os.path.exists(temp_file_path):
                logger.info(f"Removing temporary file: {temp_file_path}.")
                os.remove(temp_file_path)

    else:
        logger.error(f"Invalid file extension: {file_data.ext}. Supported extensions are '.pdf', '.png', '.jpg', '.jpeg'.")
        raise HTTPException(status_code=400, detail="Invalid file extension. Supported extensions are '.pdf', '.png', '.jpg', '.jpeg'.")
