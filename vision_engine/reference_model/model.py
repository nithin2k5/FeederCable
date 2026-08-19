from typing import Dict, Any, List, Optional
import numpy as np

class ReferenceModel:
    def __init__(self):
        self.metadata: Dict[str, Any] = {}
        self.roi: Dict[str, int] = {}
        self.reference_images: List[np.ndarray] = []
        self.keypoints_list: List[List[Dict[str, Any]]] = []
        self.descriptors_list: List[np.ndarray] = []
        self.reference_dimensions: List[Tuple[int, int]] = []
        self.feature_statistics: Dict[str, Any] = {}
        self.detection_config: Dict[str, Any] = {}
        self.camera_config: Dict[str, Any] = {}
        self.calibration: Dict[str, Any] = {}

    def get_summary(self) -> str:
        avg_features = self.feature_statistics.get("avg_features", 0)
        consistency = self.feature_statistics.get("consistency_score", 0) * 100
        sim_threshold = self.detection_config.get("similarity_threshold", 0.7)
        roi_str = f"{self.roi.get('width', 0)} x {self.roi.get('height', 0)}" if self.roi else "Full Image"
        
        return (
            f"Model: {self.metadata.get('model_name', 'Unknown')}\n"
            f"Version: {self.metadata.get('model_version', '1.0')}\n"
            f"References: {len(self.reference_images)}\n"
            f"ROI: {roi_str}\n"
            f"Average Features: {avg_features:.0f}\n"
            f"Reference Consistency: {consistency:.1f}%\n"
            f"Similarity Threshold: {sim_threshold}\n"
            f"Status: READY"
        )

    def validate(self) -> bool:
        from .validator import ModelValidator
        return ModelValidator.validate(self)

    def save(self, file_path: str):
        from .serializer import ModelSerializer
        ModelSerializer.save(self, file_path)

    @classmethod
    def load(cls, file_path: str) -> "ReferenceModel":
        from .serializer import ModelSerializer
        return ModelSerializer.load(file_path)
