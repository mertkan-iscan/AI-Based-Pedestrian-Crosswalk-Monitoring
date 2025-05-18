# CNNFeatureExtractor.py
from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
import cv2
import torchvision.transforms as T
from torchvision.models import resnet50


class ReIDModel(nn.Module):
    def __init__(self, embedding_dim: int = 512):
        super().__init__()
        backbone = resnet50(pretrained=True)
        backbone.fc = nn.Identity()
        self.backbone = backbone
        self.embedding = nn.Linear(2048, embedding_dim)
        self.bnneck = nn.BatchNorm1d(embedding_dim)
        self.bnneck.bias.requires_grad_(False)

    def forward(self, x):
        x = self.backbone(x)
        x = self.embedding(x)
        x = self.bnneck(x)
        return x


class CNNFeatureExtractor:
    def __init__(
        self,
        device: str = "cuda",
        checkpoint_path: str | None = None,
        embedding_dim: int = 512,
    ):
        self.device = torch.device(device)
        model = ReIDModel(embedding_dim)
        if checkpoint_path is not None:
            # load the file (may contain a 'state_dict' wrapper)
            raw = torch.load(checkpoint_path, map_location=self.device, weights_only=False)
            state_dict = raw.get("state_dict", raw)
            # load with strict=False so that:
            #  - 'conv1.weight', etc. map automatically into model.backbone.*
            #  - missing keys (e.g. classifier) are ignored
            model.load_state_dict(state_dict, strict=False)
        self.model = model.to(self.device).eval()

        self.transform = T.Compose([
            T.ToPILImage(),
            T.Resize((256, 128)),
            T.ToTensor(),
            T.Normalize(mean=[0.485, 0.456, 0.406],
                        std=[0.229, 0.224, 0.225]),
        ])

    def _preprocess(self, crops: list[np.ndarray]) -> torch.Tensor:
        tensor_list = []
        for crop in crops:
            if crop.size == 0:
                crop = np.zeros((128, 256, 3), dtype=np.uint8)
            crop = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
            tensor_list.append(self.transform(crop))
        return torch.stack(tensor_list, dim=0)

    def extract_features(self, crops: list[np.ndarray]) -> list[np.ndarray]:
        if len(crops) == 0:
            return []
        with torch.no_grad():
            batch = self._preprocess(crops).to(self.device)
            feats = self.model(batch).cpu()
            feats = F.normalize(feats, p=2, dim=1)
            return feats.numpy().astype(np.float32)

    def extract_features_batch(self, frame: np.ndarray,
                               bboxes: list[tuple[int, int, int, int]]) -> np.ndarray:
        patches = []
        for x1, y1, x2, y2 in bboxes:
            patch = frame[y1:y2, x1:x2]
            if patch.size == 0:
                patch = np.zeros((128, 256, 3), dtype=np.uint8)
            patch = cv2.cvtColor(patch, cv2.COLOR_BGR2RGB)
            patches.append(self.transform(patch))
        if not patches:
            return np.zeros((0, self.model.embedding.out_features), dtype=np.float32)
        batch = torch.stack(patches, dim=0).to(self.device)
        with torch.no_grad():
            feats = self.model(batch).cpu()
            feats = F.normalize(feats, p=2, dim=1)
            return feats.numpy().astype(np.float32)
