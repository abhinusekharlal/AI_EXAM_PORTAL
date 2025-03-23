from django import template

register = template.Library()

@register.filter
def active_session_count(sessions, exam_id):
    """
    Filter to count active sessions for a specific exam
    
    Usage: {{ active_sessions|active_session_count:exam.id }}
    """
    return sessions.filter(exam_id=exam_id).count()