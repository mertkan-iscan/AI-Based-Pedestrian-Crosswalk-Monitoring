import numpy as np
import cv2
import torch
import torch.nn as nn
import torchvision.models as models
import torchvision.transforms as T
from torchvision.models import EfficientNet_B0_Weights


class CNNFeatureExtractor:
    def __init__(self, device='cuda'):
        self.device = device
        # Use pre-trained EfficientNet-B0 and remove the classifier layer.
        self.model = models.efficientnet_b0(weights=EfficientNet_B0_Weights.DEFAULT)
        # Replace the classifier with identity so that the output is the raw features.
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
        # Code remains unchanged
        x1, y1, x2, y2 = bbox[:4]
        h, w, _ = frame.shape
        x1 = max(0, min(x1, w - 1))
        x2 = max(0, min(x2, w - 1))
        y1 = max(0, min(y1, h - 1))
        y2 = max(0, min(y2, h - 1))
        patch = frame[y1:y2, x1:x2]
        if patch.size == 0:
            return np.zeros(1280)  # Adjusted to EfficientNet-B0's output dim.
        patch = cv2.cvtColor(patch, cv2.COLOR_BGR2RGB)
        patch_tensor = self.transform(patch).unsqueeze(0).to(self.device)
        with torch.no_grad():
            features = self.model(patch_tensor)
        features = features.cpu().numpy().flatten()

        return features

    def extract_features_batch(self, frame, bboxes):
        # Code remains similar for batch processing.
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
            return np.zeros((0, 1280))
        batch_tensor = torch.stack(patches, dim=0).to(self.device)
        with torch.no_grad():
            batch_features = self.model(batch_tensor)
        batch_features = batch_features.cpu().numpy()
        return batch_features  # Output shape: (N, 1280)
