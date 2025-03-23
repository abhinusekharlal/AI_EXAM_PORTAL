from django import template

register = template.Library()

@register.filter
def get_options(question):
    """Return a list of tuples containing option numbers and text."""
    return [
        (1, question.option1),
        (2, question.option2),
        (3, question.option3),
        (4, question.option4),
    ]

@register.filter
def multiply(value, arg):
    """Multiply the value by the argument"""
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0
    
@register.filter
def divided_by(value, arg):
    """Divide the value by the argument"""
    try:
        return float(value) / float(arg)
    except (ValueError, TypeError, ZeroDivisionError):
        return 0
    
@register.filter
def subtract(value, arg):
    """Subtract the argument from the value"""
    try:
        return float(value) - float(arg)
    except (ValueError, TypeError):
        return 0