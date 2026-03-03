import cv2
import numpy as np

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
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    # Apply CLAHE (Contrast Limited Adaptive Histogram Equalization)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    enhanced = clahe.apply(gray)
    
    # We will return the BGR image so EasyOCR handles color if needed,
    # but enhanced gray is often best for OCR accuracy.
    # Let's return the enhanced grayscale image converted back to BGR 
    # so downstream API stays uniform.
    return cv2.cvtColor(enhanced, cv2.COLOR_GRAY2BGR)

def process_id_card(image):
    """
    Detects the ID card in the image, crops it, and enhances it.
    Returns: (processed_image, was_cropped)
    """
    # Resize if too large to speed up processing
    height, width = image.shape[:2]
    max_dim = 1500
    if max(height, width) > max_dim:
        scale = max_dim / float(max(height, width))
        image = cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)

    orig = image.copy()
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    # Blur to reduce noise
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    
    # Edge detection
    edged = cv2.Canny(blurred, 50, 150)
    
    # Find contours
    contours, _ = cv2.findContours(edged.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    # Sort contours by area in descending order
    contours = sorted(contours, key=cv2.contourArea, reverse=True)[:5]
    
    card_contour = None
    
    for c in contours:
        # Approximate the contour
        peri = cv2.arcLength(c, True)
        approx = cv2.approxPolyDP(c, 0.02 * peri, True)
        
        # If contour has 4 points and area is sufficiently large, we assume it's the card
        if len(approx) == 4 and cv2.contourArea(c) > 10000:
            card_contour = approx
            break

    was_cropped = False
    
    if card_contour is not None:
        # We found a card, warp it
        warped = four_point_transform(orig, card_contour.reshape(4, 2))
        processed = enhance_image(warped)
        was_cropped = True
    else:
        # No card found, just enhance the whole image
        processed = enhance_image(orig)
        
    return processed, was_cropped
