# AI-Based Pedestrian and Vehicle Crosswalk Monitoring

A real-time, AI-powered system for monitoring crosswalks at urban intersections. The system detects and tracks pedestrians and vehicles using live video feeds, analyzes their interactions, synchronizes with traffic light states, and provides automated event logging and safety analytics. It features a graphical interface for easy configuration and region annotation.

## Features

- **Real-time Object Detection and Tracking:** Uses YOLOv5 for detection and a custom DeepSORT-based tracker for associating pedestrians and vehicles across frames.
- **Supports Live and Recorded Video:** Can process both camera streams (HLS) and video files (MP4).
- **Crosswalk and Region Annotation:** GUI tools for annotating crosswalks, sidewalks, waiting areas, and detection blackouts.
- **Homography Calibration:** Aligns video frames to a real-world reference using point mapping and projective transformation.
- **Traffic Light State Recognition:** Detects and synchronizes with vehicle and pedestrian traffic signals for advanced event analysis.
- **Event Logging and Analysis:** Automatically detects, logs, and exports events such as pedestrian crossings, red-light violations, vehicle yielding, and more.
- **User-Friendly Interface:** GUI for configuration, real-time monitoring, and event inspection.
- **Configurable for Any Crosswalk Layout:** Adaptable to diverse urban intersections.

## How It Works

1. **Video Input:** The system takes a live camera stream or video file as input.
2. **Region Annotation:** Users define crosswalks, waiting areas, sidewalks, and blackout regions via the GUI. Homography calibration can be done using bird’s-eye images from sources like Google Maps.
3. **Object Detection and Tracking:** Every frame is processed with YOLOv5; detected objects are tracked with a Kalman-filter-based, appearance-aided tracker (DeepSORT).
4. **Traffic Light Monitoring:** The user can annotate traffic lights; the system analyzes cropped regions to detect light color/state.
5. **Event Analysis:** The system matches pedestrian and vehicle trajectories to traffic light phases and annotated regions, detects safety-critical events, and logs all results.
6. **Visualization:** All detections, tracks, regions, and status overlays are shown on the GUI for real-time feedback.
7. **Data Export:** Event logs and statistics can be saved for further analysis.

## Technology Stack

- **Python** (main language)
- **PyQt5** (for GUI)
- **OpenCV** (video processing and region annotation)
- **YOLOv5** (object detection, PyTorch backend)
- **DeepSORT** (multi-object tracking, with Kalman filter and custom ReID)
- **NumPy**, **Pandas** (data processing)
- **HLS/MP4** (video source formats)
- **JSON** (for region/configuration storage)

## System Requirements

- Windows or Linux
- Python 3.8+
- Modern GPU for real-time performance (recommended)
- Required Python packages: `PyQt5`, `opencv-python`, `torch`, `numpy`, `pandas`
- YOLOv5 weights for detection (trained on traffic datasets)

## Installation

1. **Clone the repository:**
2. **Install dependencies:**
3. **(Optional) Download or train YOLOv5 weights for traffic/pedestrian detection.**
- Place the weights in the designated models folder.

## Usage

1. **Start the application:**
2. **Add a monitored location:**  
Use the GUI to add a new camera/video source, optionally upload a bird’s-eye image, and perform homography calibration.

3. **Annotate regions:**  
Draw crosswalks, waiting areas, sidewalks, and detection blackouts. Add and calibrate traffic lights.

4. **Start monitoring:**  
Begin live monitoring, detection, and tracking. The GUI will display detections, tracks, region overlays, and real-time event logs.

5. **Review and export results:**  
Save or export event logs/statistics for safety analysis.

## Example Workflow

1. Launch the application with `python main.py`
2. Add a new location and provide the video stream or file path.
3. Optionally calibrate with a bird’s-eye image for real-world measurement.
4. Use annotation tools to define crosswalk packs and other regions.
5. Begin monitoring. The system will automatically detect, track, and analyze all events at the crosswalk.

## Main Functionalities

- **Pedestrian and Vehicle Detection:** Fast and accurate detection in challenging urban scenes.
- **Multiple Object Tracking:** Consistent ID assignment for moving objects, even with partial occlusions.
- **Event Analysis:** Detection of key safety events:
 - Pedestrian crossing during red light
 - Vehicle failing to yield
 - Vehicle/pedestrian entering crosswalk during wrong signal
 - Pedestrian wait and crossing durations
- **Configurable and Extensible:** Easily adapts to new layouts, sources, and analysis requirements.

## Limitations

- Real-time performance depends on available GPU/CPU resources.
- Supports one video stream at a time in this version.
- Best results in stable lighting conditions and with camera placement that covers the crosswalk clearly.

## Demo and Documentation

- **YouTube Video Demo:** [Watch on YouTube](https://lnkd.in/dSYrW4_d)
- **Project Report:** [View Project Report (PDF)](https://lnkd.in/dhxnGaB9)

## Author

Mertkan İşcan

Project completed as the graduation project for Yeditepe University Computer Engineering, 2025.
