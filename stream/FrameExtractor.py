import cv2

from stream.StreamContainer import StreamContainer

class FrameExtractor:

    @staticmethod
    def frame_generator(container):
        for frame in container.decode(video=0):
            yield frame.to_ndarray(format='bgr24')

    @staticmethod
    def get_single_frame_from_stream(stream_url):
        cap = cv2.VideoCapture(stream_url)
        if not cap.isOpened():
            print(f"Error: Cannot open stream {stream_url}")
            return None

        ret, frame = cap.read()
        cap.release()
        if not ret:
            print(f"Error: Cannot read a frame from {stream_url}")
            return None

        return frame

    @staticmethod
    def get_single_frame_from_file(video_file_path):
        cap = cv2.VideoCapture(video_file_path)
        if not cap.isOpened():
            print(f"Error: Could not open video file: {video_file_path}")
            return None

        ret, frame = cap.read()
        cap.release()

        if not ret:
            print(f"Error: Could not read a frame from: {video_file_path}")
            return None

        return frame