import requests
import base64
import json

# Function to convert PDF to base64
def pdf_to_base64_json(pdf_file_path):
    with open(pdf_file_path, "rb") as pdf_file:
        # Read and encode the PDF file in base64
        pdf_content = pdf_file.read()
        base64_encoded = base64.b64encode(pdf_content).decode('utf-8')
        
        # Create the required JSON format
        return {"data": base64_encoded, "ext": ".pdf"}

# Path to the PDF file you want to send
pdf_file_path = "POD OCR Project Phase[1] (1).pdf"  # Replace with the actual PDF file path

# Convert the PDF to base64 format
base64_pdf_json = pdf_to_base64_json(pdf_file_path)

# API endpoint URL (local FastAPI server)
api_url = "http://127.0.0.1:8000/read-pdf/"

# Send POST request with JSON data
response = requests.post(api_url, json=base64_pdf_json)

# Check if the request was successful and print the response
if response.status_code == 200:
    print("Response from the API:", response.json())
else:
    print(f"Failed to send POST request. Status code: {response.status_code}, Error: {response.text}")
