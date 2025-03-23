from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from monitoring.models import ExamSession, StreamFrame, Alert
import os
from django.conf import settings

class Command(BaseCommand):
    help = 'Cleans up old monitoring data (frames, inactive sessions, resolved alerts)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=7,
            help='Number of days of data to keep'
        )

    def handle(self, *args, **options):
        cutoff_date = timezone.now() - timedelta(days=options['days'])
        
        # Clean up old frames
        old_frames = StreamFrame.objects.filter(timestamp__lt=cutoff_date)
        for frame in old_frames:
            # Delete file if it exists
            if frame.frame_path:
                file_path = os.path.join(settings.MEDIA_ROOT, frame.frame_path)
                if os.path.exists(file_path):
                    os.remove(file_path)
        
        frame_count = old_frames.count()
        old_frames.delete()
        
        # Clean up inactive sessions
        session_count = ExamSession.objects.filter(
            is_active=False,
            last_activity__lt=cutoff_date
        ).delete()[0]
        
        # Clean up reviewed alerts
        alert_count = Alert.objects.filter(
            is_reviewed=True,
            timestamp__lt=cutoff_date
        ).delete()[0]
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully cleaned up monitoring data:\n'
                f'- {frame_count} old frames removed\n'
                f'- {session_count} inactive sessions removed\n'
                f'- {alert_count} reviewed alerts removed'
            )
        )