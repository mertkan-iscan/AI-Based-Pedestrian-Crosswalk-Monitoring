import os
import cv2

from utils.benchmark.Benchmark import Benchmark

class ReportManager:
    def __init__(self, video_path):
        self.video_path = video_path
        self.bm         = Benchmark.instance()

    def _get_video_duration(self):
        cap = cv2.VideoCapture(self.video_path)
        fps         = cap.get(cv2.CAP_PROP_FPS) or 0.0
        frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0.0
        cap.release()
        return (frame_count / fps) if fps > 0 else 0.0

    def _format_ts(self, sec_idx):
        m = sec_idx // 60
        s = sec_idx % 60
        return f"{m:02d}:{s:02d}"

    def save_per_second_report(self, output_path=None):
        per_sec = self.bm.get_per_second()
        duration = self._get_video_duration()

        if output_path is None:
            base = os.path.splitext(os.path.basename(self.video_path))[0]
            folder = os.path.dirname(self.video_path) or os.getcwd()
            output_path = os.path.join(folder, f"{base}_per_second_report.txt")

        with open(output_path, 'w') as f:
            f.write(f"Video File: {os.path.basename(self.video_path)}\n")
            f.write(f"Duration: {int(duration//60):02d}:{int(duration%60):02d}\n\n")
            f.write("Second, FPS, Avg Delay (s)\n")
            for sec, stats in per_sec:
                fps = stats['frames']
                delays = stats['delays']
                avg_delay = (sum(delays) / len(delays)) if delays else 0.0
                f.write(f"{self._format_ts(sec)}, {fps}, {avg_delay:.3f}\n")

        return output_path