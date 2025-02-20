
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