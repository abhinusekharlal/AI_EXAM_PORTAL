import os
import pickle
import numpy as np
from deepface import DeepFace
from .models import User, FaceEmbedding
from django.conf import settings
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
import base64
from datetime import datetime
import cv2

def extract_face_embedding(image_path):
    """Extract face embedding from an image using DeepFace"""
    try:
        # Using VGG-Face model for facial recognition
        embedding_objs = DeepFace.represent(img_path=image_path, model_name="VGG-Face")
        if embedding_objs and len(embedding_objs) > 0:
            return embedding_objs[0]["embedding"]
        return None
    except Exception as e:
        print(f"Error extracting face embedding: {e}")
        return None

def register_face(user, image_data):
    """Register a user's face from base64 image data from webcam"""
    if not user.is_student():
        return False, "Face registration only required for students"
    
    try:
        # Convert base64 to image file
        format, imgstr = image_data.split(';base64,')
        ext = format.split('/')[-1]
        file_name = f"face_{user.id}_{datetime.now().timestamp()}.{ext}"
        file_path = f"face_recognition/{file_name}"
        
        # Save image to storage
        image_data = base64.b64decode(imgstr)
        path = default_storage.save(file_path, ContentFile(image_data))
        full_path = os.path.join(settings.MEDIA_ROOT, path)
        
        # Detect faces to ensure quality
        try:
            faces = DeepFace.extract_faces(img_path=full_path, enforce_detection=True)
            if not faces or len(faces) == 0:
                return False, "No face detected in the image"
            if len(faces) > 1:
                return False, "Multiple faces detected. Please ensure only your face is visible."
        except:
            return False, "Could not detect a clear face in the image. Please try again."
        
        # Extract face embedding
        embedding = extract_face_embedding(full_path)
        if embedding is None:
            return False, "Failed to extract face features. Please try again."
        
        # Convert numpy array to binary for storage
        embedding_binary = pickle.dumps(embedding)
        
        # Save embedding to database
        face_embedding = FaceEmbedding(
            user=user,
            embedding_vector=embedding_binary,
            is_primary=not user.face_embeddings.exists()  # First one is primary
        )
        face_embedding.save()
        
        # Update user's face recognition status
        user.face_recognition_enabled = True
        user.face_image = file_path
        user.save()
        
        return True, "Face registered successfully"
    except Exception as e:
        return False, f"Error registering face: {str(e)}"

def verify_face(user, image_data):
    """Verify a face against the user's registered face"""
    if not user.is_student():
        return True, "Face verification not required for teachers"
    
    if not user.face_recognition_enabled:
        return False, "Face recognition not enabled for this user"
    
    try:
        # Convert base64 to image file
        format, imgstr = image_data.split(';base64,')
        ext = format.split('/')[-1]
        file_name = f"verify_{user.id}_{datetime.now().timestamp()}.{ext}"
        file_path = f"face_recognition/{file_name}"
        
        # Save image to storage
        image_data = base64.b64decode(imgstr)
        path = default_storage.save(file_path, ContentFile(image_data))
        full_path = os.path.join(settings.MEDIA_ROOT, path)
        
        # Get the user's primary face embedding
        primary_face = user.face_embeddings.filter(is_primary=True).first()
        if not primary_face:
            return False, "No registered face found for verification"
        
        # Verify using DeepFace
        try:
            result = DeepFace.verify(
                img1_path=user.face_image.path,
                img2_path=full_path,
                model_name="VGG-Face", 
                distance_metric="cosine"
            )
            
            verified = result["verified"]
            return verified, "Verification successful" if verified else "Face verification failed"
        except:
            return False, "Could not verify face. Please ensure proper lighting and positioning."
        
    except Exception as e:
        return False, f"Error during face verification: {str(e)}"