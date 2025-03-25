from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser

@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'role', 'department', 'emp_id', 'is_approved', 'date_joined')
    list_filter = ('is_approved', 'role', 'department')
    ordering = ('-date_joined',)
    actions = ['approve_users']
    
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'email', 'mobile_number')}),
        ('Role Information', {'fields': ('role', 'department', 'emp_id', 'is_approved')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'password1', 'password2', 'role', 'department', 'emp_id'),
        }),
    )
    
    def approve_users(self, request, queryset):
        queryset.update(is_approved=True)
        self.message_user(request, f'{queryset.count()} users were successfully approved.')
    approve_users.short_description = 'Approve selected users'

# Register your models here.
