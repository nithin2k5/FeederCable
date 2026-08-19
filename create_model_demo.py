import os
import cv2
import numpy as np
from vision_engine.reference_model import ReferenceModelBuilder, ReferenceModel

def create_dummy_image(index):
    img = np.ones((480, 640, 3), dtype=np.uint8) * 200
    noise = np.random.randint(0, 30, (480, 640, 3), dtype=np.uint8)
    img = cv2.subtract(img, noise)
    
    # Draw a mock part
    cv2.rectangle(img, (200, 150), (440, 330), (50, 50, 50), -1)
    cv2.circle(img, (320, 240), 40, (150, 150, 150), -1)
    
    # Add a slight shift to simulate part movement
    shift_x = np.random.randint(-5, 5)
    shift_y = np.random.randint(-5, 5)
    
    # Add fake keypoint details
    cv2.line(img, (220 + shift_x, 170 + shift_y), (420 + shift_x, 310 + shift_y), (255, 255, 255), 3)
    cv2.line(img, (420 + shift_x, 170 + shift_y), (220 + shift_x, 310 + shift_y), (255, 255, 255), 3)
    
    return img

def main():
    print("1. Loading 6-10 sample images...")
    images = [create_dummy_image(i) for i in range(8)]
    
    print("2. Building the reference model...")
    builder = ReferenceModelBuilder()
    builder.model_name = "PART_001"
    
    for img in images:
        builder.add_reference(img)
        
    builder.set_roi(180, 130, 280, 220)
    
    try:
        model = builder.build()
    except Exception as e:
        print(f"Failed to build model: {e}")
        return

    print("3. Displaying model statistics...")
    print(model.get_summary())
    
    model_file = "PART_001.ivmodel"
    print(f"\n4. Saving model to: {model_file}...")
    model.save(model_file)
    
    print(f"5. Loading the same file again...")
    loaded_model = ReferenceModel.load(model_file)
    
    print("6. Validating the loaded model...")
    if loaded_model.validate():
        print("\n7. Validation Result:")
        print("       MODEL VALID")
        print(f"       REFERENCES: {len(loaded_model.reference_images)}")
        consistency = loaded_model.feature_statistics.get("consistency_score", 0) * 100
        print(f"       CONSISTENCY: {consistency:.1f}%")

if __name__ == "__main__":
    main()
