import cv2
import numpy as np
import logging

logger = logging.getLogger(__name__)

def order_points(pts):
    """
    Order points: top-left, top-right, bottom-right, bottom-left.
    """
    rect = np.zeros((4, 2), dtype="float32")
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]

    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]

    return rect

def four_point_transform(image, pts):
    """
    Apply perspective transform to get a top-down view of the card.
    """
    rect = order_points(pts)
    (tl, tr, br, bl) = rect

    widthA = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
    widthB = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
    maxWidth = max(int(widthA), int(widthB))

    heightA = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
    heightB = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))
    maxHeight = max(int(heightA), int(heightB))

    dst = np.array([
        [0, 0],
        [maxWidth - 1, 0],
        [maxWidth - 1, maxHeight - 1],
        [0, maxHeight - 1]], dtype="float32")

    M = cv2.getPerspectiveTransform(rect, dst)
    warped = cv2.warpPerspective(image, M, (maxWidth, maxHeight))
    return warped

def enhance_image(image):
    """
    Enhance the image for OCR using CLAHE and optional sharpening.
    Returns a single-channel grayscale image for optimal OCR performance.
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    # Apply CLAHE (Contrast Limited Adaptive Histogram Equalization)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    enhanced = clahe.apply(gray)
    
    # Return grayscale directly — EasyOCR handles grayscale natively.
    # Avoids unnecessary GRAY→BGR conversion (which EasyOCR would just
    # undo internally), saving ~3× memory and processing time.
    return enhanced

def _is_valid_crop(warped, original_h, original_w):
    """
    Validate that the cropped image is usable for OCR.
    Returns True if the crop looks like a real ID card region.
    """
    h, w = warped.shape[:2]

    # 1. Minimum dimension check — reject tiny crops
    if h < 50 or w < 50:
        logger.warning("Crop rejected: too small (%d x %d)", w, h)
        return False

    # 2. Area ratio — crop should be at least 20% of the original
    crop_area = h * w
    original_area = original_h * original_w
    area_ratio = crop_area / original_area
    if area_ratio < 0.20:
        logger.warning(
            "Crop rejected: area ratio %.1f%% < 20%% (%d vs %d pixels)",
            area_ratio * 100, crop_area, original_area,
        )
        return False

    # 3. Aspect ratio guard — ID cards are roughly landscape rectangles
    aspect = w / h
    if aspect < 0.3 or aspect > 5.0:
        logger.warning("Crop rejected: extreme aspect ratio %.2f", aspect)
        return False

    logger.info("Crop accepted: %d x %d  (area ratio %.1f%%)", w, h, area_ratio * 100)
    return True

def process_id_card(image):
    """
    Detects the ID card in the image, crops it, and enhances it.
    Returns: (processed_image, was_cropped)
    """
    # Resize if too large to speed up processing
    height, width = image.shape[:2]
    logger.info("Input image shape: %d x %d", width, height)

    max_dim = 1000  # 1000px is sufficient for ID card OCR; was 1500
    if max(height, width) > max_dim:
        scale = max_dim / float(max(height, width))
        image = cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        height, width = image.shape[:2]
        logger.info("Resized to: %d x %d", width, height)

    # No need to copy — edge detection operates on derived arrays (gray, blurred),
    # not on `image` itself, so the original is safe to reuse directly.
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    # Blur to reduce noise
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    
    # Edge detection
    edged = cv2.Canny(blurred, 50, 150)
    
    # Find contours
    contours, _ = cv2.findContours(edged.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    # Sort contours by area in descending order
    contours = sorted(contours, key=cv2.contourArea, reverse=True)[:5]
    logger.info("Found %d contours (top 5 by area)", len(contours))
    
    card_contour = None
    
    for i, c in enumerate(contours):
        # Approximate the contour
        peri = cv2.arcLength(c, True)
        approx = cv2.approxPolyDP(c, 0.02 * peri, True)
        area = cv2.contourArea(c)
        logger.debug("Contour %d: vertices=%d, area=%.0f", i, len(approx), area)
        
        # If contour has 4 points and area is sufficiently large, we assume it's the card
        if len(approx) == 4 and area > 10000:
            card_contour = approx
            logger.info("Selected contour %d as card candidate (area=%.0f)", i, area)
            break

    was_cropped = False
    
    if card_contour is not None:
        # We found a card candidate — warp it
        warped = four_point_transform(image, card_contour.reshape(4, 2))
        logger.info("Warped image shape: %d x %d", warped.shape[1], warped.shape[0])

        # Validate the crop before using it
        if _is_valid_crop(warped, height, width):
            processed = enhance_image(warped)
            was_cropped = True
        else:
            logger.warning("Crop validation failed — falling back to full image")
            processed = enhance_image(image)
    else:
        # No card found, just enhance the whole image
        logger.info("No 4-point contour found — enhancing full image")
        processed = enhance_image(image)

    logger.info("Final processed image shape: %s", processed.shape)
    return processed, was_cropped
