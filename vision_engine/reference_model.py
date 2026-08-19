import os
import json
import numpy as np
import cv2
import logging
from typing import List, Dict, Any, Tuple, Optional

logger = logging.getLogger(__name__)

class ReferenceModel:
    def __init__(self):
        self.metadata: Dict[str, Any] = {}
        self.roi: Dict[str, int] = {}
        # Lists containing data for each valid reference image
        self.keypoints_list: List[List[Dict[str, Any]]] = []
        self.descriptors_list: List[np.ndarray] = []
        self.reference_dimensions: List[Tuple[int, int]] = []
        self.feature_statistics: Dict[str, Any] = {}

    def get_summary(self) -> Dict[str, Any]:
        return {
            "num_references": len(self.descriptors_list),
            "roi": self.roi,
            "average_keypoints": np.mean([len(kp) for kp in self.keypoints_list]) if self.keypoints_list else 0,
            "metadata": self.metadata,
            "feature_statistics": self.feature_statistics
        }

    def save(self, path: str):
        if not os.path.exists(path):
            os.makedirs(path)
        
        # Save ROI and Metadata
        with open(os.path.join(path, "roi.json"), "w") as f:
            json.dump(self.roi, f, indent=4)
            
        with open(os.path.join(path, "metadata.json"), "w") as f:
            json.dump(self.metadata, f, indent=4)
            
        # Save Keypoints (as JSON) and Descriptors (as NPY)
        keypoints_data = []
        for kp_list in self.keypoints_list:
            keypoints_data.append(kp_list)
            
        with open(os.path.join(path, "keypoints.json"), "w") as f:
            json.dump(keypoints_data, f, indent=4)
            
        # Descriptors are a list of arrays of varying lengths, we can save them as a single object array or multiple files
        # Using a single npz file is convenient
        desc_dict = {f"desc_{i}": desc for i, desc in enumerate(self.descriptors_list)}
        np.savez_compressed(os.path.join(path, "descriptors.npz"), **desc_dict)
        
        # Save dimensions
        with open(os.path.join(path, "dimensions.json"), "w") as f:
            json.dump(self.reference_dimensions, f, indent=4)

    @classmethod
    def load(cls, path: str) -> "ReferenceModel":
        model = cls()
        
        with open(os.path.join(path, "roi.json"), "r") as f:
            model.roi = json.load(f)
            
        with open(os.path.join(path, "metadata.json"), "r") as f:
            model.metadata = json.load(f)
            
        with open(os.path.join(path, "keypoints.json"), "r") as f:
            model.keypoints_list = json.load(f)
            
        desc_data = np.load(os.path.join(path, "descriptors.npz"))
        model.descriptors_list = [desc_data[f"desc_{i}"] for i in range(len(model.keypoints_list))]
        
        with open(os.path.join(path, "dimensions.json"), "r") as f:
            # json saves tuples as lists, convert back
            model.reference_dimensions = [tuple(d) for d in json.load(f)]
            
        model.feature_statistics = model.metadata.get("feature_statistics", {})
        return model


class ReferenceModelBuilder:
    def __init__(self):
        self.images: List[np.ndarray] = []
        self.roi: Optional[Dict[str, int]] = None
        self.sift = cv2.SIFT_create()
        self.min_match_count = 10
        self.flann = self._init_flann()

    def _init_flann(self):
        FLANN_INDEX_KDTREE = 1
        index_params = dict(algorithm=FLANN_INDEX_KDTREE, trees=5)
        search_params = dict(checks=50)
        return cv2.FlannBasedMatcher(index_params, search_params)

    def add_reference(self, image: np.ndarray):
        if image is None or image.size == 0:
            logger.warning("Attempted to add empty/invalid image.")
            return
        self.images.append(image.copy())

    def set_roi(self, x: int, y: int, width: int, height: int):
        self.roi = {"x": x, "y": y, "width": width, "height": height}

    def preprocess_image(self, image: np.ndarray) -> np.ndarray:
        # Convert to grayscale
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()
            
        # Noise reduction
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        
        # CLAHE (Contrast Limited Adaptive Histogram Equalization)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(blurred)
        
        return enhanced

    def extract_features(self, image: np.ndarray) -> Tuple[List[cv2.KeyPoint], np.ndarray]:
        preprocessed = self.preprocess_image(image)
        
        mask = None
        if self.roi:
            mask = np.zeros_like(preprocessed)
            x, y, w, h = self.roi["x"], self.roi["y"], self.roi["width"], self.roi["height"]
            # Ensure ROI is within bounds
            x = max(0, x)
            y = max(0, y)
            w = min(w, preprocessed.shape[1] - x)
            h = min(h, preprocessed.shape[0] - y)
            mask[y:y+h, x:x+w] = 255
            
        keypoints, descriptors = self.sift.detectAndCompute(preprocessed, mask)
        if descriptors is None:
            descriptors = np.array([])
        return keypoints, descriptors

    def _serialize_keypoint(self, kp: cv2.KeyPoint) -> Dict[str, Any]:
        return {
            "pt": (kp.pt[0], kp.pt[1]),
            "size": kp.size,
            "angle": kp.angle,
            "response": kp.response,
            "octave": kp.octave,
            "class_id": kp.class_id
        }

    def compute_consistency(self, descriptors_list: List[np.ndarray]) -> Tuple[float, List[List[float]]]:
        if len(descriptors_list) < 2:
            return 1.0, []

        scores = []
        matrix = [[0.0 for _ in range(len(descriptors_list))] for _ in range(len(descriptors_list))]
        
        for i in range(len(descriptors_list)):
            for j in range(i + 1, len(descriptors_list)):
                desc1 = descriptors_list[i]
                desc2 = descriptors_list[j]
                
                if len(desc1) < 2 or len(desc2) < 2:
                    matrix[i][j] = matrix[j][i] = 0.0
                    scores.append(0.0)
                    continue

                matches = self.flann.knnMatch(desc1, desc2, k=2)
                good_matches = []
                for match_tuple in matches:
                    if len(match_tuple) == 2:
                        m, n = match_tuple
                        if m.distance < 0.7 * n.distance:
                            good_matches.append(m)
                
                # Score is the ratio of good matches to the minimum descriptors count
                min_desc = min(len(desc1), len(desc2))
                score = len(good_matches) / min_desc if min_desc > 0 else 0
                matrix[i][j] = matrix[j][i] = score
                scores.append(score)
                
        avg_score = np.mean(scores) if scores else 0.0
        return float(avg_score), matrix

    def build(self) -> ReferenceModel:
        if not self.images:
            raise ValueError("No reference images provided.")
        if not self.roi:
            # Default to full image if ROI not set
            h, w = self.images[0].shape[:2]
            self.roi = {"x": 0, "y": 0, "width": w, "height": h}

        model = ReferenceModel()
        model.roi = self.roi
        
        valid_keypoints = []
        valid_descriptors = []
        valid_dimensions = []
        
        # 1. Feature Extraction
        for i, img in enumerate(self.images):
            kp, desc = self.extract_features(img)
            
            if len(kp) < self.min_match_count:
                logger.warning(f"Image {i} has insufficient features ({len(kp)}). Discarding.")
                continue
                
            valid_keypoints.append(kp)
            valid_descriptors.append(desc)
            valid_dimensions.append((img.shape[1], img.shape[0]))
            
        if not valid_descriptors:
            raise ValueError("No valid features could be extracted from the reference images.")

        # 2. Consistency Check
        consistency_score, consistency_matrix = self.compute_consistency(valid_descriptors)
        logger.info(f"Reference consistency score: {consistency_score:.3f}")
        
        if consistency_score < 0.1 and len(valid_descriptors) > 1:
            logger.warning("Reference images appear to be highly inconsistent. The model may perform poorly.")

        # 3. Populate Model
        for kp in valid_keypoints:
            model.keypoints_list.append([self._serialize_keypoint(p) for p in kp])
        model.descriptors_list = valid_descriptors
        model.reference_dimensions = valid_dimensions
        
        model.feature_statistics = {
            "consistency_score": consistency_score,
            "min_features": int(min(len(kp) for kp in valid_keypoints)),
            "max_features": int(max(len(kp) for kp in valid_keypoints)),
            "avg_features": float(np.mean([len(kp) for kp in valid_keypoints])),
        }
        
        model.metadata = {
            "version": "1.0",
            "num_original_images": len(self.images),
            "num_usable_images": len(valid_descriptors),
            "feature_extractor": "SIFT",
            "feature_statistics": model.feature_statistics
        }
        
        return model

def build_reference_model(images: List[np.ndarray], roi: Dict[str, int]) -> ReferenceModel:
    """Helper function to build a reference model in one call."""
    builder = ReferenceModelBuilder()
    for img in images:
        builder.add_reference(img)
    builder.set_roi(roi["x"], roi["y"], roi["width"], roi["height"])
    return builder.build()
