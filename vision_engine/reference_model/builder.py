import time
import numpy as np
from typing import List, Dict, Optional, Tuple
from .model import ReferenceModel
from .features import FeatureExtractor
from .statistics import ReferenceStatistics
import uuid

class ReferenceModelBuilder:
    def __init__(self):
        self.images: List[np.ndarray] = []
        self.roi: Optional[Dict[str, int]] = None
        self.extractor = FeatureExtractor()
        self.stats = ReferenceStatistics()
        self.min_match_count = 10
        self.model_name = "New Model"

    def add_reference(self, image: np.ndarray):
        if image is None or image.size == 0:
            raise ValueError("Attempted to add empty/invalid image.")
        self.images.append(image.copy())

    def set_roi(self, x: int, y: int, width: int, height: int):
        self.roi = {"x": x, "y": y, "width": width, "height": height}

    def build(self) -> ReferenceModel:
        if not self.images:
            raise ValueError("No reference images provided.")
        
        if not self.roi:
            h, w = self.images[0].shape[:2]
            self.roi = {"x": 0, "y": 0, "width": w, "height": h}

        valid_keypoints = []
        valid_descriptors = []
        valid_dimensions = []
        valid_images = []

        for i, img in enumerate(self.images):
            kp, desc = self.extractor.extract(img, self.roi)
            if len(kp) < self.min_match_count:
                # Rejecting unusable image
                continue
            
            valid_keypoints.append(kp)
            valid_descriptors.append(desc)
            valid_dimensions.append((img.shape[1], img.shape[0]))
            valid_images.append(img)
            
        if not valid_descriptors:
            raise ValueError("No valid features could be extracted from the reference images.")
            
        if len(valid_descriptors) < 2 and len(self.images) >= 2:
            raise ValueError("Most reference images were rejected. Please ensure the target part is visible.")

        consistency_score, _ = self.stats.compute_consistency(valid_descriptors)
        
        if consistency_score < 0.1 and len(valid_descriptors) > 1:
            raise ValueError(f"Reference images are extremely inconsistent (score {consistency_score:.2f}). Model generation aborted.")

        model = ReferenceModel()
        model.roi = self.roi
        model.reference_images = valid_images
        model.reference_dimensions = valid_dimensions
        model.descriptors_list = valid_descriptors
        
        serialized_kp = []
        for kp in valid_keypoints:
            serialized_kp.append([self.extractor.serialize_keypoint(p) for p in kp])
        model.keypoints_list = serialized_kp
        
        model.feature_statistics = self.stats.generate_stats(serialized_kp, consistency_score)
        
        model.metadata = {
            "model_name": self.model_name,
            "model_id": str(uuid.uuid4()),
            "creation_date": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "modification_date": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "application_version": "2.0",
            "model_version": "1.0",
            "num_original_images": len(self.images),
            "num_usable_images": len(valid_images)
        }
        
        model.detection_config = {
            "similarity_threshold": 0.7,
            "min_feature_matches": self.min_match_count,
            "geometric_verification_threshold": 0.5,
            "scale_tolerance": 0.2,
            "rotation_tolerance": 180.0,
            "confidence_threshold": 0.8
        }
        
        return model

def build_reference_model(images: List[np.ndarray], roi: Dict[str, int]) -> ReferenceModel:
    builder = ReferenceModelBuilder()
    for img in images:
        builder.add_reference(img)
    if roi:
        builder.set_roi(roi.get("x", 0), roi.get("y", 0), roi.get("width", 100), roi.get("height", 100))
    return builder.build()
