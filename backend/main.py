import io
import base64
import numpy as np
import cv2
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from .image_processor import process_id_card
from .ocr_engine import extract_text
from .field_extractor import extract_fields

app = FastAPI(title="AI ID Card Scanner API")

# Allow CORS for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.post("/scan")
async def scan_id_card(file: UploadFile = File(...)):
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File provided is not an image.")

    try:
        # Read image to memory
        contents = await file.read()
        nparr = np.frombuffer(contents, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if img is None:
            raise HTTPException(status_code=400, detail="Could not decode image.")

        # Step 1: Image Processing (Crop & Enhance)
        processed_img, was_cropped = process_id_card(img)

        # Step 2: OCR Extraction
        ocr_results, raw_text_full = extract_text(processed_img)

        # Step 3: Intelligent Field Extraction
        extracted_data = extract_fields(ocr_results, raw_text_full)

        # Convert processed image to base64 for preview
        _, buffer = cv2.imencode('.jpg', processed_img)
        img_base64 = base64.b64encode(buffer).decode('utf-8')

        # Build response
        response_data = {
            "name": extracted_data.get("name"),
            "roll_number": extracted_data.get("roll_number"),
            "date_of_birth": extracted_data.get("date_of_birth"),
            "department": extracted_data.get("department"),
            "institution": extracted_data.get("institution"),
            "raw_text": raw_text_full,
            "confidence_scores": extracted_data.get("_confidence_scores", {}),
            "was_cropped": was_cropped,
            "preview_image_base64": f"data:image/jpeg;base64,{img_base64}"
        }

        return JSONResponse(content=response_data)

    except Exception as e:
        print(f"Error processing scan: {e}")
        raise HTTPException(status_code=500, detail=str(e))
