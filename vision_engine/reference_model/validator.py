from .model import ReferenceModel

class ModelValidator:
    @staticmethod
    def validate(model: ReferenceModel) -> bool:
        if not model.metadata:
            raise ValueError("Model has no metadata")
        if not model.reference_images:
            raise ValueError("Model has no reference images")
        if len(model.reference_images) != len(model.keypoints_list):
            raise ValueError("Mismatch between number of images and feature keypoints")
        if len(model.descriptors_list) != len(model.keypoints_list):
            raise ValueError("Mismatch between keypoints and descriptors")
        
        # Check minimum consistency
        consistency = model.feature_statistics.get("consistency_score", 0)
        if consistency < 0.1 and len(model.reference_images) > 1:
            raise ValueError(f"Model consistency is too low ({consistency:.2f}). Images might not be of the same part.")
            
        return True
