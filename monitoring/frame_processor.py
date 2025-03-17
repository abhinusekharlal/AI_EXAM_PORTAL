import cv2
import numpy as np
from deepface import DeepFace
from ultralytics import YOLO
import base64
import logging
from django.utils import timezone
from django.conf import settings
from .models import Alert, StreamFrame
import io
from PIL import Image
import os
import json
import Users

logger = logging.getLogger(__name__)

# Define objects of interest and their COCO class IDs
OBJECTS_OF_INTEREST = {
    0: "person",
    63: "laptop",
    62: "tv/monitor",
    67: "cell phone",
    72: "speaker"
}

COLORS = {
    "person": (0, 255, 0),
    "laptop": (255, 0, 0),
    "tv/monitor": (0, 0, 255),
    "cell phone": (255, 255, 0),
    "speaker": (255, 0, 255)
}

class FrameProcessor:
    def __init__(self, session):
        self.session = session
        # Initialize face detection
        self.face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        
        # Initialize YOLO model
        model_path = os.path.join(settings.YOLO_MODEL_DIR, 'yolov8n.pt')
        if os.path.exists(model_path):
            self.yolo_model = YOLO(model_path)
        else:
            self.yolo_model = YOLO('yolov8n.pt')  # Will download if not exists
            
        # Initialize state tracking
        self.last_face_direction = None
        self.consecutive_no_face = 0
        self.consecutive_multiple_faces = 0
        self.last_object_detection = {}

    def process_frame(self, frame_path):
        """Process a frame and generate alerts if violations are detected"""
        try:
            # Load image
            frame = self._load_image(frame_path)
            if frame is None:
                return []

            alerts = []
            
            # Run face detection and verification
            face_alerts = self._process_faces(frame)
            alerts.extend(face_alerts)
            
            # Run YOLO object detection
            yolo_alerts = self._detect_objects(frame)
            alerts.extend(yolo_alerts)
            
            # Save annotated frame if any alerts were generated
            if alerts:
                self._save_annotated_frame(frame, alerts, frame_path)
            
            return alerts
            
        except Exception as e:
            logger.error(f"Error processing frame: {str(e)}")
            return []

    def _load_image(self, frame_path):
        """Load image from path and convert to correct format"""
        try:
            # Use PIL first for better format support
            with Image.open(frame_path) as image:
                if image.mode != 'RGB':
                    image = image.convert('RGB')
                # Convert to numpy array for OpenCV
                frame = np.array(image)
                # Convert RGB to BGR for OpenCV
                frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                return frame
        except Exception as e:
            logger.error(f"Error loading image: {str(e)}")
            return None

    def _process_faces(self, frame):
        """Process faces in frame and return any alerts"""
        alerts = []
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = self.face_cascade.detectMultiScale(gray, 1.1, 4)
        
        # Check number of faces
        if len(faces) == 0:
            self.consecutive_no_face += 1
            if self.consecutive_no_face >= 3:  # Alert after 3 consecutive frames
                alerts.append(self._create_alert(
                    'face_missing',
                    'No face detected in frame',
                    'high',
                    confidence=0.9
                ))
        else:
            self.consecutive_no_face = 0
        
        if len(faces) > 1:
            self.consecutive_multiple_faces += 1
            if self.consecutive_multiple_faces >= 2:  # Alert after 2 consecutive frames
                alerts.append(self._create_alert(
                    'multiple_faces',
                    f'{len(faces)} faces detected in frame',
                    'critical',
                    confidence=0.95
                ))
        else:
            self.consecutive_multiple_faces = 0
        
        # If exactly one face is detected, run additional checks
        if len(faces) == 1:
            x, y, w, h = faces[0]
            face_roi = frame[y:y+h, x:x+w]
            
            # Analyze face direction
            # try:
            #     analysis = DeepFace.analyze(
            #         face_roi, 
            #         actions=['head_pose'],
            #         enforce_detection=False
            #     )
                
            #     pitch = analysis[0]['head_pose']['pitch']
            #     yaw = analysis[0]['head_pose']['yaw']
                
            #     if abs(yaw) > 30 or abs(pitch) > 20:  # Thresholds for head movement
            #         alerts.append(self._create_alert(
            #             'looking_away',
            #             f'Head position indicates looking away (pitch: {pitch:.1f}, yaw: {yaw:.1f})',
            #             'medium',
            #             confidence=0.8
            #         ))
            # except Exception as e:
            #     logger.warning(f"Face analysis error: {str(e)}")
            
            # Verify student identity if enrolled
            # try:
            #     # enrolled_image = self.session.student.get_enrolled_face_image()
            #     enrolled_image = self.session.face_embeddings.filter(is_primary=True).first()
            #     if enrolled_image:
            #         verification = DeepFace.verify(
            #             face_roi,
            #             enrolled_image,
            #             enforce_detection=False
            #         )
                    
            #         if not verification['verified']:
            #             alerts.append(self._create_alert(
            #                 'unknown_face',
            #                 'Face does not match enrolled student',
            #                 'critical',
            #                 confidence=verification['distance']
            #             ))
            # except Exception as e:
            #     logger.warning(f"Face verification error: {str(e)}")
        
        return alerts

    def _detect_objects(self, frame, conf_threshold=0.5):
        """Run YOLO object detection and return alerts for suspicious objects"""
        alerts = []
        # Run inference
        results = self.yolo_model(frame)[0]
        detection_counts = {obj_name: 0 for obj_name in OBJECTS_OF_INTEREST.values()}
        
        # Process results
        for result in results.boxes.data.tolist():
            x1, y1, x2, y2, score, class_id = result
            class_id = int(class_id)
            
            if class_id in OBJECTS_OF_INTEREST and score >= conf_threshold:
                object_name = OBJECTS_OF_INTEREST[class_id]
                detection_counts[object_name] += 1
        
        # Generate alerts based on detections
        if detection_counts["cell phone"] > 0:
            alerts.append(self._create_alert(
                'phone_detected',
                f'Cell phone detected in frame ({detection_counts["cell phone"]} instances)',
                'critical',
                confidence=0.9
            ))
            
        if detection_counts["person"] > 1:
            alerts.append(self._create_alert(
                'multiple_faces',
                f'Multiple people detected ({detection_counts["person"]} people)',
                'critical',
                confidence=0.95
            ))
            
        suspicious_devices = []
        for device in ["laptop", "tv/monitor", "speaker"]:
            if detection_counts[device] > 0:
                suspicious_devices.append(f"{device} ({detection_counts[device]})")
        
        if suspicious_devices:
            alerts.append(self._create_alert(
                'unauthorized_object',
                f'Unauthorized devices detected: {", ".join(suspicious_devices)}',
                'high',
                confidence=0.85
            ))
        
        return alerts

    def _create_alert(self, alert_type, description, severity='medium', confidence=0.0):
        """Create and return an Alert object"""
        return Alert.objects.create(
            session=self.session,
            alert_type=alert_type,
            description=description,
            severity=severity,
            confidence=confidence,
            timestamp=timezone.now()
        )

    def _save_annotated_frame(self, frame, alerts, original_frame_path):
        """Save an annotated version of the frame with detection visualizations"""
        try:
            # Create annotated copy
            annotated = frame.copy()
            
            # Add alert information
            y_position = 30
            for alert in alerts:
                color = (0, 0, 255) if alert.severity == 'critical' else (0, 255, 255)
                cv2.putText(annotated, 
                           f'{alert.get_alert_type_display()}: {alert.confidence:.2f}',
                           (10, y_position),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
                y_position += 30
            
            # Save annotated frame
            annotated_path = original_frame_path.replace('.', '_annotated.')
            cv2.imwrite(os.path.join(settings.MEDIA_ROOT, annotated_path), annotated)
            
            # Update alert with annotated frame path
            for alert in alerts:
                alert.screenshot = annotated_path
                alert.save()
                
        except Exception as e:
            logger.error(f"Error saving annotated frame: {str(e)}")