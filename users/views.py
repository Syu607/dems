from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.forms import AuthenticationForm
from django.views.decorators.http import require_http_methods
from .models import CustomUser
from .forms import UserLoginForm, UserRegistrationForm

def index(request):
    return render(request, 'users/index.html')

@require_http_methods(['GET', 'POST'])
def register(request):
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, 'Registration successful. Please wait for approval.')
            return redirect('login')
        else:
            messages.error(request, 'Registration failed. Please correct the errors.')
    else:
        form = UserRegistrationForm()
    return render(request, 'users/register.html', {'form': form})

@require_http_methods(['GET', 'POST'])
def user_login(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = UserLoginForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                if user.is_approved:
                    login(request, user)
                    messages.success(request, f'Welcome back, {username}!')
                    return redirect('dashboard')
                else:
                    messages.warning(request, 'Your account is pending approval.')
            else:
                messages.error(request, 'Invalid username or password.')
    else:
        form = UserLoginForm()
    return render(request, 'users/login.html', {'form': form})

@login_required
def user_logout(request):
    logout(request)
    messages.info(request, 'You have been logged out successfully.')
    return redirect('login')

@login_required
def dashboard(request):
    user = request.user
    context = {
        'user': user
    }
    
    if user.role == 'PRINCIPAL':
        return render(request, 'users/principal_dashboard.html', context)
    elif user.role == 'HOD':
        return render(request, 'users/hod_dashboard.html', context)
    elif user.role == 'EVENT_COORDINATOR':
        return render(request, 'users/coordinator_dashboard.html', context)
    else:  # STUDENT
        return render(request, 'users/student_dashboard.html', context)
