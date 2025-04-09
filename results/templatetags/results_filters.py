from django import template

register = template.Library()

@register.filter
def contains(value, arg):
    """
    Check if a string contains another substring
    Usage: {{ value|contains:"substring" }}
    """
    return arg in value

@register.filter
def get_option(question, option_number):
    """
    Get the text of a specific option from a question object
    Usage: {{ question|get_option:option_number }}
    """
    try:
        option_number = int(option_number)
        if option_number == 1:
            return question.option1
        elif option_number == 2:
            return question.option2
        elif option_number == 3:
            return question.option3
        elif option_number == 4:
            return question.option4
        else:
            return ""
    except (ValueError, AttributeError):
        return ""

@register.simple_tag
def assign_value(value):
    """
    Simple tag to assign a value to a variable
    Usage: {% assign_value "value" as variable_name %}
    """
    return value