import unittest
import numpy as np
import cv2
import os
import shutil
from vision_engine.reference_model import ReferenceModelBuilder, ReferenceModel, build_reference_model

class TestReferenceModel(unittest.TestCase):
    def setUp(self):
        self.test_dir = "test_model_output"
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
            
        # Create dummy images with a square
        self.good_images = []
        for i in range(5):
            img = np.ones((200, 200, 3), dtype=np.uint8) * 255
            # Add a bit of noise
            noise = np.random.randint(0, 20, (200, 200, 3), dtype=np.uint8)
            img = cv2.subtract(img, noise)
            # Draw a target shape
            cv2.rectangle(img, (50, 50), (150, 150), (0, 0, 0), -1)
            # Add some internal features to the rectangle so SIFT has something to detect
            cv2.circle(img, (100, 100), 20, (255, 255, 255), -1)
            cv2.line(img, (50, 50), (150, 150), (255, 0, 0), 2)
            self.good_images.append(img)
            
        # Create a bad image (blank)
        self.bad_image = np.ones((200, 200, 3), dtype=np.uint8) * 255

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_build_model(self):
        builder = ReferenceModelBuilder()
        for img in self.good_images:
            builder.add_reference(img)
            
        builder.add_reference(self.bad_image)
        
        # Set ROI
        builder.set_roi(40, 40, 120, 120)
        
        model = builder.build()
        
        summary = model.get_summary()
        self.assertEqual(summary["num_references"], 5)  # The bad image should be rejected
        self.assertGreater(summary["average_keypoints"], 0)
        self.assertEqual(summary["roi"]["width"], 120)
        
    def test_save_load_model(self):
        roi = {"x": 40, "y": 40, "width": 120, "height": 120}
        model = build_reference_model(self.good_images, roi)
        
        model.save(self.test_dir)
        
        self.assertTrue(os.path.exists(os.path.join(self.test_dir, "metadata.json")))
        self.assertTrue(os.path.exists(os.path.join(self.test_dir, "descriptors.npz")))
        
        loaded_model = ReferenceModel.load(self.test_dir)
        
        self.assertEqual(len(loaded_model.descriptors_list), 5)
        self.assertEqual(loaded_model.roi["width"], 120)
        self.assertEqual(loaded_model.metadata["num_original_images"], 5)
        
        # Check descriptor values
        np.testing.assert_array_equal(model.descriptors_list[0], loaded_model.descriptors_list[0])

if __name__ == "__main__":
    unittest.main()
