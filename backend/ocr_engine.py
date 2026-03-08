import easyocr
import cv2
import logging

logger = logging.getLogger(__name__)

# Initialize the EasyOCR Reader once to cache the model in memory.
# It will download the models on first run if they don't exist.
reader = easyocr.Reader(['en'], gpu=False) # set gpu=True if CUDA is available

def extract_text(image):
    """
    Extracts text from the provided image using EasyOCR.
    Returns:
        detailed_results: list of dictionaries with bbox, text, and confidence
        raw_text: full concatenated text string separated by newlines
    """
    logger.info("OCR input image shape: %s, dtype: %s", image.shape, image.dtype)

    # EasyOCR can take a numpy array directly (cv2 image)
    # The detail=1 flag returns bounding box, text, and confidence.
    results = reader.readtext(image, detail=1)
    
    detailed_results = []
    raw_text_lines = []
    
    for (bbox, text, prob) in results:
        detailed_results.append({
            "bbox": bbox,       # e.g., [[x1, y1], [x2, y1], [x2, y2], [x1, y2]]
            "text": text,
            "confidence": prob
        })
        raw_text_lines.append(text)

    logger.info("OCR detections: %d", len(detailed_results))
    if not detailed_results:
        logger.warning("OCR returned ZERO detections — check input image quality/content")
    else:
        for r in detailed_results:
            logger.debug("  [%.2f] %s", r["confidence"], r["text"])

    raw_text = "\n".join(raw_text_lines)
    return detailed_results, raw_text
