import os
import cv2
import numpy as np
from vision_engine.reference_model import build_reference_model, ReferenceModel

# Create dummy images
img1 = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
img2 = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
roi = {"x": 10, "y": 10, "width": 100, "height": 100}

print("Building model...")
try:
    model = build_reference_model([img1, img2], roi)
    model.save("test_model_dir")
    print("Saved model")
except Exception as e:
    print(f"Error building model: {e}")
    # Let's generate a valid SIFT image
    img1 = cv2.imread("nice.jpeg")
    img2 = img1.copy()
    model = build_reference_model([img1, img2], roi)
    model.save("test_model_dir")

print("Loading model...")
loaded = ReferenceModel.load("test_model_dir")
print(f"Loaded ROI: {loaded.roi}")
print(f"Loaded desc: {len(loaded.descriptors_list)}")

# Now test Flann matcher
sift = cv2.SIFT_create()
FLANN_INDEX_KDTREE = 1
index_params = dict(algorithm=FLANN_INDEX_KDTREE, trees=5)
search_params = dict(checks=50)
flann = cv2.FlannBasedMatcher(index_params, search_params)

ref_desc = loaded.descriptors_list[0]
print(f"Ref desc shape: {ref_desc.shape}, dtype: {ref_desc.dtype}")

# Match
try:
    matches = flann.knnMatch(ref_desc, ref_desc, k=2)
    print(f"Matches found: {len(matches)}")
except Exception as e:
    print(f"Error in FLANN: {e}")
