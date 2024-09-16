import os
import base64
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from PyPDF2 import PdfReader
import tempfile

app = FastAPI()

# Define the request model
class PDFData(BaseModel):
    data: str  # Base64 encoded data
    ext: str   # File extension, expecting '.pdf'

@app.post("/read-pdf/")
async def read_pdf(pdf_data: PDFData):
    if pdf_data.ext != '.pdf':
        raise HTTPException(status_code=400, detail="Invalid file extension. Only PDF files are supported.")

    try:
        # Create a temporary file to store the PDF
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        pdf_content = base64.b64decode(pdf_data.data)
        
        # Write the decoded PDF content to the temporary file
        with open(temp_file.name, 'wb') as f:
            f.write(pdf_content)
        
        # Read the content of the PDF using PyPDF2
        reader = PdfReader(temp_file.name)
        text_content = ""
        for page in reader.pages:
            text_content += page.extract_text()
        
        # Close and remove the temporary file
        temp_file.close()
        os.remove(temp_file.name)

        return {"content": text_content.strip()}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred while processing the PDF: {str(e)}")
