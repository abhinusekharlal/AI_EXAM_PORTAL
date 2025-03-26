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
from Users.face_recognition_utils import extract_face_embedding, verify_face

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
        
        # Add verification tracking
        self.last_verification_time = None
        self.verification_interval = 15 # Verify every 30 seconds
        self.consecutive_verification_failures = 0
        self.max_verification_failures = 3  # Max failures before critical alert

    def process_frame(self, frame_path):
        """Process a frame and generate alerts if violations are detected"""
        try:
            # Load image
            frame = self._load_image(frame_path)
            if frame is None:
                logger.error(f"Failed to load image from {frame_path}")
                return []

            # Create list to hold alerts
            alerts = []
            
            # Create annotated frame path for potential alerts
            annotated_path = frame_path.rsplit('.', 1)[0] + '_annotated.' + frame_path.rsplit('.', 1)[1]
            relative_screenshot_path = None
            if os.path.exists(settings.MEDIA_ROOT):
                relative_screenshot_path = os.path.relpath(annotated_path, settings.MEDIA_ROOT) if annotated_path else None
            
            # Run face detection and verification
            face_alerts = self._process_faces(frame, relative_screenshot_path)
            alerts.extend(face_alerts)
            
            # Run YOLO object detection
            yolo_alerts = self._detect_objects(frame, conf_threshold=0.5, screenshot_path=relative_screenshot_path)
            alerts.extend(yolo_alerts)
            
            # Save annotated frame if alerts were generated, otherwise delete original
            if alerts:
                self._save_annotated_frame(frame, alerts, annotated_path)
            
            # Always delete the original frame to save space
            if os.path.exists(frame_path):
                os.remove(frame_path)
            
            return alerts
            
        except Exception as e:
            logger.error(f"Error processing frame: {str(e)}")
            # Clean up original frame on error
            if os.path.exists(frame_path):
                os.remove(frame_path)
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

    def _process_faces(self, frame, screenshot_path=None):
        """Process faces in frame and return any alerts"""
        alerts = []
        try:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = self.face_cascade.detectMultiScale(gray, 1.1, 4)
            
            # Check number of faces
            if len(faces) == 0:
                self.consecutive_no_face += 1
                if self.consecutive_no_face >= 3:  # Alert after 3 consecutive frames
                    alerts.append(self._create_alert(
                        'face_missing',
                        'No face detected in frame. Please ensure your face is visible.',
                        'high',
                        confidence=0.9,
                        screenshot=screenshot_path
                    ))
            else:
                self.consecutive_no_face = 0
            
            if len(faces) > 1:
                self.consecutive_multiple_faces += 1
                if self.consecutive_multiple_faces >= 2:
                    alerts.append(self._create_alert(
                        'multiple_faces',
                        f'{len(faces)} faces detected in frame. Only one person should be visible.',
                        'critical',
                        confidence=0.95,
                        screenshot=screenshot_path
                    ))
            else:
                self.consecutive_multiple_faces = 0
            
            # If exactly one face is detected, run face verification
            if len(faces) == 1:
                x, y, w, h = faces[0]
                face_roi = frame[y:y+h, x:x+w]
                
                # Check lighting conditions
                avg_brightness = cv2.mean(cv2.cvtColor(face_roi, cv2.COLOR_BGR2GRAY))[0]
                if avg_brightness < 40:  # Too dark
                    alerts.append(self._create_alert(
                        'poor_lighting',
                        'Lighting too dark. Please improve lighting conditions.',
                        'medium',
                        confidence=0.85,
                        screenshot=screenshot_path
                    ))
                elif avg_brightness > 240:  # Too bright
                    alerts.append(self._create_alert(
                        'poor_lighting',
                        'Lighting too bright. Please reduce lighting glare.',
                        'medium',
                        confidence=0.85,
                        screenshot=screenshot_path
                    ))
                
                # Face quality check
                try:
                    # Convert face_roi to a temporary file for DeepFace
                    temp_face_path = os.path.join(settings.MEDIA_ROOT, f"face_verification/temp_quality_{timezone.now().timestamp()}.jpg")
                    os.makedirs(os.path.dirname(temp_face_path), exist_ok=True)
                    cv2.imwrite(temp_face_path, face_roi)
                    
                    try:
                        # Use DeepFace.represent with enforce_detection=False
                        embedding_objs = DeepFace.represent(img_path=temp_face_path, model_name="VGG-Face", enforce_detection=False)
                        face_info = embedding_objs[0]["embedding"] if embedding_objs and len(embedding_objs) > 0 else None
                        
                        # Clean up temp file
                        if os.path.exists(temp_face_path):
                            os.remove(temp_face_path)
                            
                        if not face_info:
                            alerts.append(self._create_alert(
                                'face_quality',
                                'Face not clearly visible. Please adjust position or lighting.',
                                'medium',
                                confidence=0.8,
                                screenshot=screenshot_path
                            ))
                            return alerts
                    except Exception as e:
                        logger.warning(f"Face quality check error with DeepFace: {str(e)}")
                        # Clean up temp file
                        if os.path.exists(temp_face_path):
                            os.remove(temp_face_path)
                        # Continue with verification even if quality check fails
                except Exception as e:
                    logger.warning(f"Face quality check error: {str(e)}")
                    # Continue with verification even if quality check fails
                
                # Periodic face verification
                current_time = timezone.now()
                if (not self.last_verification_time or 
                    (current_time - self.last_verification_time).total_seconds() >= self.verification_interval):
                    
                    try:
                        # Get enrolled face image
                        student = self.session.student
                        if not student.face_recognition_enabled or not student.face_image:
                            alerts.append(self._create_alert(
                                'verification_error',
                                'No enrolled face found for verification',
                                'critical',
                                confidence=1.0,
                                screenshot=screenshot_path
                            ))
                            return alerts
                        
                        # Save face_roi to a temporary file for verification
                        temp_face_path = os.path.join(settings.MEDIA_ROOT, f"face_verification/temp_{self.session.id}_{current_time.timestamp()}.jpg")
                        os.makedirs(os.path.dirname(temp_face_path), exist_ok=True)
                        cv2.imwrite(temp_face_path, face_roi)
                        
                        # Verify face using DeepFace
                        try:
                            verification = DeepFace.verify(
                                img1_path=student.face_image.path,
                                img2_path=temp_face_path,
                                model_name="VGG-Face",
                                enforce_detection=False,  # Set enforce_detection to False
                                distance_metric="cosine"
                            )
                            
                            self.last_verification_time = current_time
                            
                            if not verification["verified"]:
                                self.consecutive_verification_failures += 1
                                severity = 'critical' if self.consecutive_verification_failures >= self.max_verification_failures else 'high'
                                
                                alerts.append(self._create_alert(
                                    'identity_mismatch',
                                    'Face does not match enrolled student identity',
                                    severity,
                                    confidence=1 - verification["distance"],  # Convert distance to confidence
                                    screenshot=screenshot_path
                                ))
                            else:
                                self.consecutive_verification_failures = 0
                            
                            # Clean up temp file
                            if os.path.exists(temp_face_path):
                                os.remove(temp_face_path)
                                
                        except Exception as e:
                            logger.error(f"DeepFace verification error: {str(e)}")
                            
                            # Alternative method using our custom verify_face function
                            # Convert face_roi to base64 for verification
                            _, buffer = cv2.imencode('.jpg', face_roi)
                            img_str = base64.b64encode(buffer).decode('utf-8')
                            img_base64 = f"data:image/jpeg;base64,{img_str}"
                            
                            # Use verify_face from face_recognition_utils
                            verified, message = verify_face(student, img_base64)
                            
                            self.last_verification_time = current_time
                            
                            if not verified:
                                self.consecutive_verification_failures += 1
                                severity = 'critical' if self.consecutive_verification_failures >= self.max_verification_failures else 'high'
                                
                                alerts.append(self._create_alert(
                                    'identity_mismatch',
                                    'Face does not match enrolled student identity',
                                    severity,
                                    confidence=0.9,
                                    screenshot=screenshot_path
                                ))
                            else:
                                self.consecutive_verification_failures = 0
                            
                    except Exception as e:
                        logger.error(f"Face verification error: {str(e)}")
                        alerts.append(self._create_alert(
                            'verification_error',
                            'Error during face verification. Please check lighting and face position.',
                            'medium',
                            confidence=0.7,
                            screenshot=screenshot_path
                        ))
                        
        except Exception as e:
            logger.error(f"Error in face processing: {str(e)}")
            alerts.append(self._create_alert(
                'processing_error',
                'Error processing video frame',
                'medium',
                confidence=0.5,
                screenshot=screenshot_path
            ))
            
        return alerts

    def _detect_objects(self, frame, conf_threshold=0.5, screenshot_path=None):
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
                confidence=0.9,
                screenshot=screenshot_path
            ))
            
        if detection_counts["person"] > 1:
            alerts.append(self._create_alert(
                'multiple_faces',
                f'Multiple people detected ({detection_counts["person"]} people)',
                'critical',
                confidence=0.95,
                screenshot=screenshot_path
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
                confidence=0.85,
                screenshot=screenshot_path
            ))
        
        return alerts

    def _create_alert(self, alert_type, description, severity='medium', confidence=0.0, screenshot=None):
        """Create and return an Alert object"""
        return Alert.objects.create(
            session=self.session,
            alert_type=alert_type,
            description=description,
            severity=severity,
            confidence=confidence,
            timestamp=timezone.now(),
            screenshot=screenshot
        )

    def _save_annotated_frame(self, frame, alerts, annotated_frame_path):
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
                y_position += 30  # Increment position for next alert

            # Save the annotated frame
            cv2.imwrite(annotated_frame_path, annotated)
            
            # Create and save StreamFrame object
            frame_obj = StreamFrame.objects.create(
                session=self.session,
                frame_path=annotated_frame_path,
                timestamp=timezone.now()
            )
            return frame_obj

        except Exception as e:
            logger.error(f"Error saving annotated frame: {str(e)}")
            return None