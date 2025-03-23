import json
import base64
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone
from .models import ExamSession, StreamFrame, Alert
from classroom.models import Exam
from Users.models import User
import uuid
import os
from datetime import datetime
from django.conf import settings

logger = logging.getLogger(__name__)

class ExamMonitorConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for handling student webcam streams during exams"""
    
    async def connect(self):
        self.exam_id = self.scope['url_route']['kwargs']['exam_id']
        self.user = self.scope['user']
        
        if not self.user.is_authenticated:
            logger.warning(f"Unauthorized connection attempt to exam {self.exam_id}")
            await self.close()
            return
            
        # Create unique group names for this connection
        self.student_group = f"exam_{self.exam_id}_student_{self.user.id}"
        self.exam_group = f"exam_{self.exam_id}"
        
        # Join room groups
        await self.channel_layer.group_add(self.student_group, self.channel_name)
        await self.channel_layer.group_add(self.exam_group, self.channel_name)
        
        # Register exam session
        self.session = await self.register_exam_session()
        
        await self.accept()
        
        # Send confirmation
        await self.send(text_data=json.dumps({
            'type': 'connection_established',
            'message': 'Connected to exam monitoring system'
        }))

    async def disconnect(self, close_code):
        # Leave room groups
        if hasattr(self, 'student_group'):
            await self.channel_layer.group_discard(self.student_group, self.channel_name)
        if hasattr(self, 'exam_group'):
            await self.channel_layer.group_discard(self.exam_group, self.channel_name)
        
        # Mark session as inactive
        if hasattr(self, 'session'):
            await self.end_exam_session()

    async def receive(self, text_data):
        """Handle incoming messages from students"""
        try:
            data = json.loads(text_data)
            
            if data['type'] == 'frame':
                # Forward frame to monitoring interface
                await self.channel_layer.group_send(
                    f"exam_{self.exam_id}_monitors",
                    {
                        'type': 'student_frame',
                        'student_id': self.user.id,
                        'student_name': self.user.get_full_name(),
                        'image_data': data['image_data'],
                        'timestamp': timezone.now().isoformat()
                    }
                )
                
                # Store frame in database if needed
                if data.get('store_frame', False):
                    await self.store_frame(data['image_data'])
                
        except Exception as e:
            logger.error(f"Error processing WebSocket message: {str(e)}")

    async def student_frame(self, event):
        """Forward frame to monitoring client"""
        await self.send(text_data=json.dumps(event))

    @database_sync_to_async
    def register_exam_session(self):
        """Create or update exam session record"""
        exam = Exam.objects.get(id=self.exam_id)
        
        session, created = ExamSession.objects.get_or_create(
            exam=exam,
            student=self.user,
            is_active=True,
            defaults={
                'started_at': timezone.now(),
                'connection_id': self.channel_name
            }
        )
        
        if not created:
            session.connection_id = self.channel_name
            session.last_activity = timezone.now()
            session.save()
        
        return session

    @database_sync_to_async
    def end_exam_session(self):
        """Mark exam session as inactive"""
        self.session.is_active = False
        self.session.save()

    @database_sync_to_async
    def store_frame(self, image_data):
        """Store webcam frame and return the saved path"""
        try:
            # Extract base64 data
            if image_data.startswith('data:image'):
                format, imgstr = image_data.split(';base64,')
                ext = format.split('/')[-1]
                
                # Generate unique filename
                filename = f"frame_{self.session.id}_{uuid.uuid4().hex}.{ext}"
                filepath = os.path.join('monitoring_frames', filename)
                
                # Save image to storage
                from django.core.files.base import ContentFile
                from django.core.files.storage import default_storage
                
                image_data_binary = base64.b64decode(imgstr)
                saved_path = default_storage.save(filepath, ContentFile(image_data_binary))
                
                # Create stream frame record
                StreamFrame.objects.create(
                    session=self.session,
                    frame_path=saved_path,
                    timestamp=timezone.now()
                )
                
                return saved_path
                
        except Exception as e:
            logger.error(f"Error storing frame: {str(e)}")
            return None

class TeacherMonitorConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for teacher's monitoring interface"""
    
    async def connect(self):
        self.exam_id = self.scope['url_route']['kwargs']['exam_id']
        self.user = self.scope['user']
        
        # Verify teacher has access to this exam
        if not self.user.is_authenticated or not await self.verify_teacher_access():
            logger.warning(f"Unauthorized teacher connection attempt to exam {self.exam_id}")
            await self.close()
            return
        
        # Join monitor group for this exam
        self.monitor_group = f"exam_{self.exam_id}_monitors"
        await self.channel_layer.group_add(self.monitor_group, self.channel_name)
        
        await self.accept()
        
        # Send active sessions info
        active_sessions = await self.get_active_sessions()
        await self.send(text_data=json.dumps({
            'type': 'active_sessions',
            'sessions': active_sessions
        }))

    async def disconnect(self, close_code):
        if hasattr(self, 'monitor_group'):
            await self.channel_layer.group_discard(self.monitor_group, self.channel_name)

    async def receive(self, text_data):
        """Handle incoming messages from teachers"""
        try:
            data = json.loads(text_data)
            
            if data['type'] == 'generate_alert':
                # Create alert for student
                await self.create_alert(data)
                
        except Exception as e:
            logger.error(f"Error processing monitor message: {str(e)}")

    async def student_frame(self, event):
        """Forward student frame to monitoring interface"""
        await self.send(text_data=json.dumps(event))

    @database_sync_to_async
    def verify_teacher_access(self):
        """Verify the teacher has access to monitor this exam"""
        try:
            exam = Exam.objects.get(id=self.exam_id)
            return self.user.user_type == 'teacher' and exam.teacher == self.user
        except Exam.DoesNotExist:
            return False

    @database_sync_to_async
    def get_active_sessions(self):
        """Get list of active exam sessions"""
        sessions = ExamSession.objects.filter(
            exam_id=self.exam_id,
            is_active=True
        ).select_related('student')
        
        return [{
            'student_id': str(session.student.id),
            'student_name': session.student.get_full_name(),
            'started_at': session.started_at.isoformat(),
        } for session in sessions]

    @database_sync_to_async
    def create_alert(self, data):
        """Create an alert for a student"""
        try:
            session = ExamSession.objects.get(
                exam_id=self.exam_id,
                student_id=data['student_id'],
                is_active=True
            )
            
            Alert.objects.create(
                session=session,
                alert_type=data['alert_type'],
                description=data.get('description', ''),
                severity=data.get('severity', 'medium'),
                screenshot=data.get('screenshot')
            )
            
        except ExamSession.DoesNotExist:
            logger.error(f"Session not found for alert: {data}")