# KalmanFilter.py
import numpy as np

class KalmanFilter:
    def __init__(self, initial_state):
        # state: [x, y, vx, vy]
        self.x = np.array(initial_state, dtype=float).reshape((4, 1))
        self.P = np.eye(4) * 10.0
        # F will be rebuilt on each predict to include dt
        self.F = np.eye(4, dtype=float)
        self.H = np.array([[1, 0, 0, 0],
                           [0, 1, 0, 0]], dtype=float)
        self.R = np.eye(2) * 1.0
        self.Q = np.eye(4) * 0.01

    def predict(self):

        # rebuild transition matrix for time step dt
        self.F = np.array([
            [1, 0, 1, 0],
            [0, 1, 0, 1],
            [0, 0, 1, 0],
            [0, 0, 0, 1]
        ], dtype=float)

        self.x = self.F @ self.x
        self.P = self.F @ self.P @ self.F.T + self.Q
        return self.x

    def predict_with_dt(self, dt):
        # rebuild transition matrix for time step dt
        self.F = np.array([
            [1, 0, dt, 0],
            [0, 1, 0, dt],
            [0, 0, 1,  0],
            [0, 0, 0,  1]
        ], dtype=float)

        self.x = self.F @ self.x
        self.P = self.F @ self.P @ self.F.T + self.Q
        return self.x

    def update(self, measurement):
        z = np.array(measurement, dtype=float).reshape((2, 1))
        y = z - self.H @ self.x
        S = self.H @ self.P @ self.H.T + self.R
        K = self.P @ self.H.T @ np.linalg.inv(S)
        self.x = self.x + K @ y
        I = np.eye(self.F.shape[0])
        self.P = (I - K @ self.H) @ self.P
        return self.x

    def gating_distance(self, dets):
        x = self.x[:2].reshape((2,))  # (2,)
        S = self.H @ self.P @ self.H.T + self.R
        invS = np.linalg.inv(S)
        dists = []
        for det in dets:
            y = np.array(det).reshape((2,)) - x  # (2,)
            d = float(np.dot(np.dot(y.T, invS), y))  # skalar
            dists.append(d)
        return np.array(dists)