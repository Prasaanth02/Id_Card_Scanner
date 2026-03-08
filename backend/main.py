import io
import base64
import logging
from pathlib import Path

# ── Pillow Compatibility Patch ──────────────────────────────────────
# Pillow 10+ removed Image.ANTIALIAS; older libs still reference it.
from PIL import Image
if not hasattr(Image, "ANTIALIAS"):
    Image.ANTIALIAS = Image.LANCZOS

import numpy as np
import cv2
from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from .image_processor import process_id_card
from .ocr_engine import extract_text
from .field_extractor import extract_fields

# ── Logging ─────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  [%(name)s]  %(message)s",
)
logger = logging.getLogger(__name__)

# ── Path Setup ──────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="AI ID Card Scanner API")

# ── Static Files & Templates ────────────────────────────────────────
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# Allow CORS for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

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

        logger.info("Decoded image: shape=%s, size=%d bytes", img.shape, len(contents))

        # Step 1: Image Processing (Crop & Enhance)
        processed_img, was_cropped = process_id_card(img)
        logger.info("After processing: shape=%s, was_cropped=%s", processed_img.shape, was_cropped)

        # Step 2: OCR Extraction
        ocr_results, raw_text_full = extract_text(processed_img)
        logger.info("OCR returned %d detections, raw_text length=%d", len(ocr_results), len(raw_text_full))

        # Step 3: Intelligent Field Extraction
        extracted_data = extract_fields(ocr_results, raw_text_full)
        logger.info("Extracted fields: %s", {k: v for k, v in extracted_data.items() if k != "_confidence_scores"})

        # Convert processed image to base64 for preview
        # processed_img is grayscale; convert to BGR for proper JPEG preview
        preview_img = cv2.cvtColor(processed_img, cv2.COLOR_GRAY2BGR) if len(processed_img.shape) == 2 else processed_img
        _, buffer = cv2.imencode('.jpg', preview_img, [cv2.IMWRITE_JPEG_QUALITY, 80])
        img_base64 = base64.b64encode(buffer).decode('utf-8')

        # Build response
        response_data = {
            "name": extracted_data.get("name"),
            "roll_number": extracted_data.get("roll_number"),
            "validity": extracted_data.get("validity"),
            "department": extracted_data.get("department"),
            "institution": extracted_data.get("institution"),
            "raw_text": raw_text_full,
            "confidence_scores": extracted_data.get("_confidence_scores", {}),
            "was_cropped": was_cropped,
            "preview_image_base64": f"data:image/jpeg;base64,{img_base64}"
        }

        return JSONResponse(content=response_data)

    except Exception as e:
        logger.exception("Error processing scan")
        raise HTTPException(status_code=500, detail=str(e))
