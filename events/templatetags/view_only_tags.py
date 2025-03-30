from django import template
from django.urls import resolve

register = template.Library()

@register.simple_tag(takes_context=True)
def is_view_only(context):
    """Check if the current user is in view-only mode"""
    request = context['request']
    return not request.user.is_superuser

@register.filter
def can_edit(user):
    """Check if the user has edit permissions"""
    return user.is_superuser or user.has_perm('users.can_manage_events')

@register.filter
def can_view_analytics(user):
    """Check if the user can view analytics"""
    return user.is_superuser or user.role in ['HOD', 'PRINCIPAL'] or user.has_perm('users.can_view_analytics')

@register.simple_tag(takes_context=True)
def disable_if_view_only(context):
    """Return 'disabled' attribute if user is in view-only mode"""
    request = context['request']
    if not request.user.is_superuser and not request.user.has_perm('users.can_manage_events'):
        return 'disabled'
    return ''