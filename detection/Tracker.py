import numpy as np
from scipy.optimize import linear_sum_assignment
from detection.PathUpdater import task_queue

class KalmanFilter:
    def __init__(self, initial_state):
        self.x = np.array(initial_state, dtype=float).reshape((4, 1))
        self.P = np.eye(4) * 10.0
        self.F = np.array([[1, 0, 1, 0],
                           [0, 1, 0, 1],
                           [0, 0, 1, 0],
                           [0, 0, 0, 1]], dtype=float)
        self.H = np.array([[1, 0, 0, 0],
                           [0, 1, 0, 0]], dtype=float)
        self.R = np.eye(2) * 1.0
        self.Q = np.eye(4) * 0.01

    def predict(self):
        self.x = np.dot(self.F, self.x)
        self.P = np.dot(self.F, np.dot(self.P, self.F.T)) + self.Q
        return self.x

    def update(self, measurement):
        z = np.array(measurement, dtype=float).reshape((2, 1))
        y = z - np.dot(self.H, self.x)
        S = np.dot(self.H, np.dot(self.P, self.H.T)) + self.R
        K = np.dot(self.P, np.dot(self.H.T, np.linalg.inv(S)))
        self.x = self.x + np.dot(K, y)
        I = np.eye(self.F.shape[0])
        self.P = np.dot(I - np.dot(K, self.H), self.P)
        return self.x

class DeepSortTracker:
    def __init__(self, maxDisappeared=50):
        self.nextObjectID = 0
        self.tracks = {}
        self.disappeared = {}
        self.maxDisappeared = maxDisappeared

    def register(self, centroid, bbox):
        kf = KalmanFilter([centroid[0], centroid[1], 0, 0])
        self.tracks[self.nextObjectID] = {"kf": kf, "bbox": bbox}
        self.disappeared[self.nextObjectID] = 0
        self.nextObjectID += 1

    def deregister(self, objectID):
        if objectID in self.tracks:
            del self.tracks[objectID]
        if objectID in self.disappeared:
            del self.disappeared[objectID]
        task_queue.put(('disappear', objectID, None))

    def update(self, rects):
        if len(rects) == 0:
            for objectID in list(self.disappeared.keys()):
                self.disappeared[objectID] += 1
                if self.disappeared[objectID] > self.maxDisappeared:
                    self.deregister(objectID)
            objects = {}
            for objectID, track in self.tracks.items():
                pred_state = track["kf"].predict()
                centroid = (int(pred_state[0, 0]), int(pred_state[1, 0]))
                objects[objectID] = (centroid, track["bbox"])
            return objects

        inputCentroids = np.zeros((len(rects), 2), dtype="int")
        for i, rect in enumerate(rects):
            x1, y1, x2, y2 = rect[:4]
            cX = int((x1 + x2) / 2.0)
            cY = int((y1 + y2) / 2.0)
            inputCentroids[i] = (cX, cY)

        if len(self.tracks) == 0:
            for i in range(len(inputCentroids)):
                self.register(inputCentroids[i], rects[i])
            objects = {}
            for objectID, track in self.tracks.items():
                objects[objectID] = (inputCentroids[list(self.tracks.keys()).index(objectID)], track["bbox"])
            return objects

        objectIDs = list(self.tracks.keys())
        predictedCentroids = []
        for objectID in objectIDs:
            pred_state = self.tracks[objectID]["kf"].predict()
            predictedCentroids.append([int(pred_state[0, 0]), int(pred_state[1, 0])])
        predictedCentroids = np.array(predictedCentroids)

        D = np.linalg.norm(predictedCentroids[:, np.newaxis] - inputCentroids, axis=2)
        rows, cols = linear_sum_assignment(D)

        assignedTracks = set()
        assignedDetections = set()
        for row, col in zip(rows, cols):
            if D[row, col] > 100:
                continue
            objectID = objectIDs[row]
            self.tracks[objectID]["kf"].update(inputCentroids[col])
            self.tracks[objectID]["bbox"] = rects[col]
            self.disappeared[objectID] = 0
            assignedTracks.add(objectID)
            assignedDetections.add(col)

        for objectID in objectIDs:
            if objectID not in assignedTracks:
                self.disappeared[objectID] += 1
                if self.disappeared[objectID] > self.maxDisappeared:
                    self.deregister(objectID)

        for i in range(len(rects)):
            if i not in assignedDetections:
                self.register(inputCentroids[i], rects[i])

        objects = {}
        for objectID, track in self.tracks.items():
            state = track["kf"].x
            centroid = (int(state[0, 0]), int(state[1, 0]))
            objects[objectID] = (centroid, track["bbox"])
        return objects
