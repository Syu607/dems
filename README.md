# DEMS - Django Event Management System

A comprehensive event management system built with Django for managing events, registrations, assessments, and certificates.

## Features

- User authentication and role-based access control
- Event creation and management
- Event registration and attendance tracking
- Assessment submission and grading (including AI-assisted grading)
- Certificate generation
- Dashboard with analytics

## Installation

1. Clone the repository
   ```
   git clone https://github.com/yourusername/dems.git
   cd dems
   ```

2. Create a virtual environment and activate it
   ```
   python -m venv venv
   # On Windows
   venv\Scripts\activate
   # On macOS/Linux
   source venv/bin/activate
   ```

3. Install dependencies
   ```
   pip install -r requirements.txt
   ```

4. Create a `.env` file based on `.env.example`
   ```
   cp .env.example .env
   # Edit the .env file with your settings
   ```

5. Run migrations
   ```
   python manage.py migrate
   ```

6. Create a superuser
   ```
   python manage.py createsuperuser
   ```

7. Run the development server
   ```
   python manage.py runserver
   ```

## Environment Variables

The following environment variables can be set in the `.env` file:

- `SECRET_KEY`: Django secret key
- `DEBUG`: Set to 'True' for development, 'False' for production
- `ALLOWED_HOSTS`: Comma-separated list of allowed hosts

## Deployment

This project is configured to be deployed to various platforms. See the deployment documentation for more details.

## License

This project is licensed under the MIT License - see the LICENSE file for details.