import cv2
import numpy as np
from typing import List, Tuple, Dict, Any

class ReferenceStatistics:
    def __init__(self):
        FLANN_INDEX_KDTREE = 1
        index_params = dict(algorithm=FLANN_INDEX_KDTREE, trees=5)
        search_params = dict(checks=50)
        self.flann = cv2.FlannBasedMatcher(index_params, search_params)

    def compute_consistency(self, descriptors_list: List[np.ndarray]) -> Tuple[float, List[List[float]]]:
        if len(descriptors_list) < 2:
            return 1.0, []

        scores = []
        n = len(descriptors_list)
        matrix = [[0.0 for _ in range(n)] for _ in range(n)]
        
        for i in range(n):
            for j in range(i + 1, n):
                desc1 = descriptors_list[i]
                desc2 = descriptors_list[j]
                
                if len(desc1) < 2 or len(desc2) < 2:
                    matrix[i][j] = matrix[j][i] = 0.0
                    scores.append(0.0)
                    continue

                try:
                    matches = self.flann.knnMatch(desc1, desc2, k=2)
                    good_matches = 0
                    for match_tuple in matches:
                        if len(match_tuple) == 2:
                            m, n_match = match_tuple
                            if m.distance < 0.7 * n_match.distance:
                                good_matches += 1
                    
                    min_desc = min(len(desc1), len(desc2))
                    score = good_matches / min_desc if min_desc > 0 else 0
                except Exception:
                    score = 0.0
                    
                matrix[i][j] = matrix[j][i] = score
                scores.append(score)
                
        avg_score = float(np.mean(scores)) if scores else 0.0
        return avg_score, matrix

    def generate_stats(self, keypoints_list: List[List[Any]], consistency_score: float) -> Dict[str, Any]:
        counts = [len(kp) for kp in keypoints_list]
        return {
            "num_references": len(keypoints_list),
            "min_features": int(min(counts)) if counts else 0,
            "max_features": int(max(counts)) if counts else 0,
            "avg_features": float(np.mean(counts)) if counts else 0.0,
            "consistency_score": consistency_score
        }
