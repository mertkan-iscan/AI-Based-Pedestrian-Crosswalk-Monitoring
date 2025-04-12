import numpy as np
import cv2
import torch
import torch.nn as nn
import torchvision.models as models
import torchvision.transforms as T

class CNNFeatureExtractor:
    def __init__(self, device='cuda'):
        self.device = device
        # Use pre-trained MobileNetV2 and remove the classifier layer.
        self.model = models.mobilenet_v2(pretrained=True)
        # For MobileNetV2, replace the classifier with identity so that the output is the features.
        self.model.classifier = nn.Identity()
        self.model = self.model.to(self.device)
        self.model.eval()
        self.transform = T.Compose([
            T.ToPILImage(),
            T.Resize((224, 224)),
            T.ToTensor(),
            T.Normalize(mean=[0.485, 0.456, 0.406],
                        std=[0.229, 0.224, 0.225])
        ])

    def extract_features(self, frame, bbox):
        """
        Extract appearance features from the given frame and bounding box.
        bbox: tuple (x1, y1, x2, y2)
        """
        x1, y1, x2, y2 = bbox[:4]
        h, w, _ = frame.shape
        x1 = max(0, min(x1, w - 1))
        x2 = max(0, min(x2, w - 1))
        y1 = max(0, min(y1, h - 1))
        y2 = max(0, min(y2, h - 1))
        patch = frame[y1:y2, x1:x2]
        if patch.size == 0:
            return np.zeros(512)
        patch = cv2.cvtColor(patch, cv2.COLOR_BGR2RGB)
        patch_tensor = self.transform(patch).unsqueeze(0).to(self.device)
        with torch.no_grad():
            features = self.model(patch_tensor)
        features = features.cpu().numpy().flatten()

        return features

    def extract_features_batch(self, frame, bboxes):
        """
        Batch extracts appearance features for multiple bounding boxes.
        bboxes: list of tuples [(x1, y1, x2, y2), ...]
        Returns an array of shape (N, feature_dim).
        """
        patches = []
        h, w, _ = frame.shape
        for bbox in bboxes:
            x1, y1, x2, y2 = bbox[:4]
            x1 = max(0, min(x1, w - 1))
            x2 = max(0, min(x2, w - 1))
            y1 = max(0, min(y1, h - 1))
            y2 = max(0, min(y2, h - 1))
            patch = frame[y1:y2, x1:x2]
            if patch.size == 0:
                patch = np.zeros((224, 224, 3), dtype=np.uint8)
            patch = cv2.cvtColor(patch, cv2.COLOR_BGR2RGB)
            image = self.transform(patch)
            patches.append(image)
        if len(patches) == 0:
            return np.zeros((0, 1280))  # Assuming MobileNetV2 outputs 1280-dim features.
        # Stack patches into a batch.
        batch_tensor = torch.stack(patches, dim=0).to(self.device)
        with torch.no_grad():
            batch_features = self.model(batch_tensor)
        batch_features = batch_features.cpu().numpy()
        return batch_features  # Shape: (N, feature_dim)