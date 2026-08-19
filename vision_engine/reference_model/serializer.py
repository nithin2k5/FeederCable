import os
import json
import zipfile
import hashlib
import numpy as np
import cv2
from io import BytesIO
from .model import ReferenceModel

class ModelSerializer:
    MAGIC = b"IVMODEL"
    FORMAT_VERSION = 1

    @classmethod
    def save(cls, model: ReferenceModel, file_path: str):
        if not file_path.endswith('.ivmodel'):
            file_path += '.ivmodel'

        # Serialize data
        metadata_json = json.dumps(model.metadata).encode('utf-8')
        roi_json = json.dumps(model.roi).encode('utf-8')
        keypoints_json = json.dumps(model.keypoints_list).encode('utf-8')
        stats_json = json.dumps(model.feature_statistics).encode('utf-8')
        config_json = json.dumps(model.detection_config).encode('utf-8')
        cam_json = json.dumps(model.camera_config).encode('utf-8')
        calib_json = json.dumps(model.calibration).encode('utf-8')
        dims_json = json.dumps(model.reference_dimensions).encode('utf-8')

        # Descriptors
        desc_io = BytesIO()
        desc_dict = {f"desc_{i}": desc for i, desc in enumerate(model.descriptors_list)}
        np.savez_compressed(desc_io, **desc_dict)
        desc_bytes = desc_io.getvalue()

        # Images
        img_dict = {}
        for i, img in enumerate(model.reference_images):
            success, encoded = cv2.imencode('.png', img)
            if success:
                img_dict[f"ref_{i}.png"] = encoded.tobytes()

        # Compute checksum over main components
        hasher = hashlib.sha256()
        hasher.update(metadata_json)
        hasher.update(keypoints_json)
        hasher.update(desc_bytes)
        for name in sorted(img_dict.keys()):
            hasher.update(img_dict[name])
            
        integrity = {
            "checksum": hasher.hexdigest(),
            "format_version": cls.FORMAT_VERSION
        }
        integrity_json = json.dumps(integrity).encode('utf-8')

        with zipfile.ZipFile(file_path, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("magic.bin", cls.MAGIC)
            zf.writestr("metadata.json", metadata_json)
            zf.writestr("roi.json", roi_json)
            zf.writestr("keypoints.json", keypoints_json)
            zf.writestr("statistics.json", stats_json)
            zf.writestr("detection_config.json", config_json)
            zf.writestr("camera_config.json", cam_json)
            zf.writestr("calibration.json", calib_json)
            zf.writestr("dimensions.json", dims_json)
            zf.writestr("descriptors.npz", desc_bytes)
            zf.writestr("integrity.json", integrity_json)
            
            for name, data in img_dict.items():
                zf.writestr(f"images/{name}", data)

    @classmethod
    def load(cls, file_path: str) -> ReferenceModel:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Model file not found: {file_path}")

        model = ReferenceModel()
        
        with zipfile.ZipFile(file_path, 'r') as zf:
            magic = zf.read("magic.bin")
            if magic != cls.MAGIC:
                raise ValueError("Invalid format: Not an IVMODEL file")
                
            integrity = json.loads(zf.read("integrity.json"))
            if integrity.get("format_version", 1) > cls.FORMAT_VERSION:
                raise ValueError("Unsupported format version")

            metadata_bytes = zf.read("metadata.json")
            keypoints_bytes = zf.read("keypoints.json")
            desc_bytes = zf.read("descriptors.npz")
            
            # Read images
            img_files = [n for n in zf.namelist() if n.startswith("images/")]
            img_dict = {}
            for name in sorted(img_files):
                img_dict[name.split("/")[-1]] = zf.read(name)

            # Verify checksum
            hasher = hashlib.sha256()
            hasher.update(metadata_bytes)
            hasher.update(keypoints_bytes)
            hasher.update(desc_bytes)
            for name in sorted(img_dict.keys()):
                hasher.update(img_dict[name])
                
            if hasher.hexdigest() != integrity["checksum"]:
                raise ValueError("Model file is corrupted (checksum mismatch). Do not use this model.")

            # Load components
            model.metadata = json.loads(metadata_bytes)
            model.roi = json.loads(zf.read("roi.json"))
            model.keypoints_list = json.loads(keypoints_bytes)
            model.feature_statistics = json.loads(zf.read("statistics.json"))
            model.detection_config = json.loads(zf.read("detection_config.json"))
            model.camera_config = json.loads(zf.read("camera_config.json"))
            model.calibration = json.loads(zf.read("calibration.json"))
            
            dims = json.loads(zf.read("dimensions.json"))
            model.reference_dimensions = [tuple(d) for d in dims]
            
            desc_io = BytesIO(desc_bytes)
            desc_data = np.load(desc_io)
            model.descriptors_list = [desc_data[f"desc_{i}"] for i in range(len(model.keypoints_list))]
            
            for name in sorted(img_dict.keys()):
                data = img_dict[name]
                np_arr = np.frombuffer(data, np.uint8)
                img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
                model.reference_images.append(img)
                
        return model
