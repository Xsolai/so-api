import os
import base64
import logging
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from PyPDF2 import PdfReader
import tempfile

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI()

# Define the request model
class PDFData(BaseModel):
    data: str  # Base64 encoded data
    ext: str   # File extension, expecting '.pdf'

@app.post("/read-pdf/")
async def read_pdf(pdf_data: PDFData):
    logger.info("Received request to read PDF.")
    
    if pdf_data.ext != '.pdf':
        logger.error(f"Invalid file extension: {pdf_data.ext}. Only PDF files are supported.")
        raise HTTPException(status_code=400, detail="Invalid file extension. Only PDF files are supported.")

    try:
        # Create a temporary file to store the PDF
        logger.info("Decoding base64 PDF data.")
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        pdf_content = base64.b64decode(pdf_data.data)
        
        # Write the decoded PDF content to the temporary file
        logger.info(f"Writing decoded PDF content to temporary file: {temp_file.name}.")
        with open(temp_file.name, 'wb') as f:
            f.write(pdf_content)
        
        # Read the content of the PDF using PyPDF2
        logger.info(f"Reading content from the PDF file: {temp_file.name}.")
        reader = PdfReader(temp_file.name)
        text_content = ""
        for page in reader.pages:
            logger.info(f"Extracting text from page {reader.pages.index(page)}.")
            text_content += page.extract_text()
        
        # Close and remove the temporary file
        logger.info(f"Removing temporary file: {temp_file.name}.")
        temp_file.close()
        os.remove(temp_file.name)

        logger.info("Successfully processed the PDF.")
        return {"content": text_content.strip()}

    except Exception as e:
        logger.error(f"An error occurred while processing the PDF: {str(e)}")
        raise HTTPException(status_code=500, detail=f"An error occurred while processing the PDF: {str(e)}")
