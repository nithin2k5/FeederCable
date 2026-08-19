import unittest
import numpy as np
import cv2
import os
from vision_engine.reference_model import ReferenceModelBuilder, ReferenceModel, build_reference_model

class TestReferenceModel(unittest.TestCase):
    def setUp(self):
        self.test_file = "test_model_output.ivmodel"
        if os.path.exists(self.test_file):
            os.remove(self.test_file)
            
        # Create dummy images with a square
        self.good_images = []
        for i in range(5):
            img = np.ones((200, 200, 3), dtype=np.uint8) * 255
            noise = np.random.randint(0, 20, (200, 200, 3), dtype=np.uint8)
            img = cv2.subtract(img, noise)
            cv2.rectangle(img, (50, 50), (150, 150), (0, 0, 0), -1)
            cv2.circle(img, (100, 100), 20, (255, 255, 255), -1)
            cv2.line(img, (50, 50), (150, 150), (255, 0, 0), 2)
            self.good_images.append(img)
            
        self.bad_image = np.ones((200, 200, 3), dtype=np.uint8) * 255

    def tearDown(self):
        if os.path.exists(self.test_file):
            os.remove(self.test_file)

    def test_build_model(self):
        builder = ReferenceModelBuilder()
        for img in self.good_images:
            builder.add_reference(img)
            
        builder.add_reference(self.bad_image)
        builder.set_roi(40, 40, 120, 120)
        
        model = builder.build()
        
        summary = model.get_summary()
        self.assertIn("References: 5", summary)
        self.assertIn("ROI: 120 x 120", summary)
        
    def test_save_load_model(self):
        roi = {"x": 40, "y": 40, "width": 120, "height": 120}
        model = build_reference_model(self.good_images, roi)
        
        model.save(self.test_file)
        self.assertTrue(os.path.exists(self.test_file))
        
        loaded_model = ReferenceModel.load(self.test_file)
        
        self.assertEqual(len(loaded_model.descriptors_list), 5)
        self.assertEqual(loaded_model.roi["width"], 120)
        self.assertEqual(loaded_model.metadata["num_original_images"], 5)
        
        # Check descriptor values
        np.testing.assert_array_equal(model.descriptors_list[0], loaded_model.descriptors_list[0])

if __name__ == "__main__":
    unittest.main()
