import cv2
import numpy as np
from typing import Tuple, List, Dict, Any, Optional

class FeatureExtractor:
    def __init__(self):
        self.sift = cv2.SIFT_create()

    def preprocess_image(self, image: np.ndarray) -> np.ndarray:
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()
            
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        return clahe.apply(blurred)

    def extract(self, image: np.ndarray, roi: Optional[Dict[str, int]] = None) -> Tuple[List[cv2.KeyPoint], np.ndarray]:
        preprocessed = self.preprocess_image(image)
        mask = None
        
        if roi:
            mask = np.zeros_like(preprocessed)
            x, y = roi.get("x", 0), roi.get("y", 0)
            w, h = roi.get("width", preprocessed.shape[1]), roi.get("height", preprocessed.shape[0])
            x = max(0, x)
            y = max(0, y)
            w = min(w, preprocessed.shape[1] - x)
            h = min(h, preprocessed.shape[0] - y)
            mask[y:y+h, x:x+w] = 255
            
        keypoints, descriptors = self.sift.detectAndCompute(preprocessed, mask)
        if descriptors is None:
            descriptors = np.array([])
        return keypoints, descriptors

    @staticmethod
    def serialize_keypoint(kp: cv2.KeyPoint) -> Dict[str, Any]:
        return {
            "pt": (kp.pt[0], kp.pt[1]),
            "size": kp.size,
            "angle": kp.angle,
            "response": kp.response,
            "octave": kp.octave,
            "class_id": kp.class_id
        }

    @staticmethod
    def deserialize_keypoint(data: Dict[str, Any]) -> cv2.KeyPoint:
        kp = cv2.KeyPoint(
            x=data["pt"][0],
            y=data["pt"][1],
            size=data["size"],
            angle=data["angle"],
            response=data["response"],
            octave=data["octave"],
            class_id=data["class_id"]
        )
        return kp
