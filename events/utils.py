from django.conf import settings
from PIL import Image, ImageDraw, ImageFont
import os
import uuid
from io import BytesIO
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
import qrcode
from datetime import datetime
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

def get_event_name_similarity(current_event_name, historical_event_names):
    """
    Calculate text similarity between current event name and historical event names
    using TF-IDF vectorization and cosine similarity.
    
    Args:
        current_event_name (str): The name of the current event
        historical_event_names (list): List of historical event names
        
    Returns:
        dict: Dictionary containing similarity scores and most similar events
    """
    if not historical_event_names:
        return {
            'avg_similarity': 0,
            'max_similarity': 0,
            'most_similar_events': []
        }
    
    # Combine current event name with historical names for vectorization
    all_event_names = [current_event_name] + historical_event_names
    
    # Create TF-IDF vectorizer
    vectorizer = TfidfVectorizer(stop_words='english')
    
    try:
        # Transform event names to TF-IDF vectors
        tfidf_matrix = vectorizer.fit_transform(all_event_names)
        
        # Calculate cosine similarity between current event and all historical events
        similarity_scores = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:])[0]
        
        # Get average and maximum similarity
        avg_similarity = np.mean(similarity_scores) * 100
        max_similarity = np.max(similarity_scores) * 100
        
        # Get indices of top 3 most similar events
        top_indices = np.argsort(similarity_scores)[::-1][:3]
        
        # Get most similar events with their similarity scores
        most_similar_events = [
            {
                'name': historical_event_names[idx],
                'similarity': similarity_scores[idx] * 100
            }
            for idx in top_indices if similarity_scores[idx] > 0
        ]
        
        return {
            'avg_similarity': avg_similarity,
            'max_similarity': max_similarity,
            'most_similar_events': most_similar_events
        }
    except Exception as e:
        # Handle potential errors in text processing
        return {
            'avg_similarity': 0,
            'max_similarity': 0,
            'most_similar_events': [],
            'error': str(e)
        }

def analyze_event_budget_name(event_name, event_budget, historical_events):
    """
    Analyze event based on name similarity and budget comparison with historical events.
    Provides a recommendation on whether to approve or reject the event.
    
    Args:
        event_name (str): Name of the current event
        event_budget (float): Budget of the current event
        historical_events (QuerySet): QuerySet of historical events
        
    Returns:
        dict: Analysis results including recommendation and confidence score
    """
    if not historical_events:
        return {
            'recommendation': 'Insufficient Data',
            'confidence': 0,
            'message': 'Not enough historical data to make a recommendation.'
        }
    
    # Extract historical event names and budgets
    historical_names = [e.event_name for e in historical_events]
    historical_budgets = [float(e.budget) for e in historical_events]
    
    # Get name similarity metrics
    name_similarity = get_event_name_similarity(event_name, historical_names)
    
    # Calculate budget metrics
    avg_budget = np.mean(historical_budgets)
    budget_difference = event_budget - avg_budget
    budget_percent_diff = (budget_difference / avg_budget * 100) if avg_budget > 0 else 0
    
    # Find similar events by budget (within 20% range)
    budget_range_min = event_budget * 0.8
    budget_range_max = event_budget * 1.2
    similar_budget_events = [e for e in historical_events if budget_range_min <= float(e.budget) <= budget_range_max]
    
    # Calculate approval rate for similar budget events
    similar_budget_count = len(similar_budget_events)
    similar_budget_approval_rate = 100  # All are approved since we're filtering for approved events
    
    # Calculate weighted score based on name similarity and budget similarity
    name_similarity_weight = 0.6
    budget_similarity_weight = 0.4
    
    # Calculate name similarity score (0-100)
    name_similarity_score = name_similarity['max_similarity']
    
    # Calculate budget similarity score (0-100)
    # Higher score for smaller budget difference percentage
    budget_similarity_score = max(0, 100 - min(abs(budget_percent_diff), 100))
    
    # Calculate weighted confidence score
    confidence_score = (name_similarity_score * name_similarity_weight) + \
                      (budget_similarity_score * budget_similarity_weight)
    
    # Determine recommendation based on confidence score
    if confidence_score > 75:
        recommendation = 'Strongly Recommended for Approval'
    elif confidence_score > 60:
        recommendation = 'Recommended for Approval'
    elif confidence_score > 40:
        recommendation = 'Needs Review'
    else:
        recommendation = 'Not Recommended'
    
    return {
        'recommendation': recommendation,
        'confidence': confidence_score,
        'name_similarity': name_similarity,
        'budget_analysis': {
            'avg_budget': avg_budget,
            'current_budget': event_budget,
            'budget_difference': budget_difference,
            'budget_percent_diff': budget_percent_diff,
            'similar_budget_events': similar_budget_count,
            'similar_budget_approval_rate': similar_budget_approval_rate
        }
    }

def generate_certificate(event, student):
    """
    Generate a certificate for a student who participated in an event
    
    Args:
        event: The Event object
        student: The CustomUser (student) object
    
    Returns:
        certificate_url: URL to the generated certificate
        verification_id: Unique ID for certificate verification
    """
    # Create a blank certificate with white background
    width, height = 1200, 900
    certificate = Image.new('RGB', (width, height), color=(255, 255, 255))
    draw = ImageDraw.Draw(certificate)
    
    # Define color palette according to requirements
    navy_blue = (12, 35, 64)  # #0C2340
    gold = (234, 179, 8)      # #EAB308
    black = (0, 0, 0)         # #000000
    light_gray = (245, 245, 245) # #F5F5F5
    
    # Load fonts - using more professional fonts for certificates
    try:
        # Try to use more elegant fonts if available
        title_font = ImageFont.truetype('arial.ttf', 60)  # Serif font for titles
        header_font = ImageFont.truetype('arial.ttf', 40)  # Sans-serif for headings
        body_font = ImageFont.truetype('arial.ttf', 30)    # Sans-serif for body
        script_font = ImageFont.truetype('arial.ttf', 35)  # Script font for names
        signature_font = ImageFont.truetype('arial.ttf', 25) # Handwritten style
        verification_font = ImageFont.truetype('arial.ttf', 15) # Small sans-serif
        footer_font = ImageFont.truetype('arial.ttf', 15)     # Small sans-serif
        gold_font = ImageFont.truetype('arial.ttf', 35)       # For gold text
    except IOError:
        # Fallback to default font if specified fonts are not available
        title_font = ImageFont.load_default()
        header_font = ImageFont.load_default()
        body_font = ImageFont.load_default()
        script_font = ImageFont.load_default()
        signature_font = ImageFont.load_default()
        verification_font = ImageFont.load_default()
        footer_font = ImageFont.load_default()
        gold_font = ImageFont.load_default()
    
    # Add decorative elements - diagonal corners in blue and yellow like in the template
    # Yellow corner at top left
    yellow_points_top = [(0, 0), (250, 0), (0, 250)]
    draw.polygon(yellow_points_top, fill=gold)  # Gold/yellow color
    
    # Blue corner at bottom right
    blue_points_bottom = [(width, height), (width-250, height), (width, height-250)]
    draw.polygon(blue_points_bottom, fill=navy_blue)  # Navy blue color
    
    # Add elegant border
    border_width = 2
    draw.rectangle(
        [(border_width, border_width), (width - border_width, height - border_width)],
        outline=black,
        width=border_width
    )
    
    # Load logos for the certificate header
    try:
        from cairosvg import svg2png
        
        # Load main logo - try SVG first, fallback to PNG if needed
        logo_svg_path = os.path.join(settings.BASE_DIR, 'static', 'images', 'logo.svg')
        logo_png_path = os.path.join(settings.BASE_DIR, 'static', 'images', 'logo.png')
        
        try:
            # Try to convert SVG to PNG
            logo_png_bytes = BytesIO()
            svg2png(url=logo_svg_path, write_to=logo_png_bytes, output_width=150, output_height=80)
            logo_png_bytes.seek(0)
            logo_img = Image.open(logo_png_bytes)
        except Exception:
            # Fallback to PNG if SVG conversion fails
            logo_img = Image.open(logo_png_path).resize((150, 80))
        
        # Add logo to certificate - centered at top
        logo_pos = (width//2 - 75, 40)
        certificate.paste(logo_img, logo_pos, logo_img if logo_img.mode == 'RGBA' else None)
    except Exception as e:
        # If logo loading fails, just continue without the logo
        print(f"Error loading logo: {e}")
    
    # Add institutional details
    draw.text(
        (width/2, 130),
        "CMR Institute of Technology, Bengaluru",
        font=header_font,
        fill=navy_blue,  # Navy blue text
        anchor="mm"
    )
    
    # Add affiliations and accreditations
    draw.text(
        (width/2, 170),
        "Affiliated to Visvesvaraya Technological University",
        font=verification_font,
        fill=black,
        anchor="mm"
    )
    
    draw.text(
        (width/2, 190),
        "Approved by AICTE, New Delhi | Recognised by Government of Karnataka",
        font=verification_font,
        fill=black,
        anchor="mm"
    )
    
    draw.text(
        (width/2, 210),
        "Accredited by NBA | UGC Recognition | Accredited by NAAC with A++",
        font=verification_font,
        fill=black,
        anchor="mm"
    )
    
    # Add CERTIFICATE OF PARTICIPATION title
    draw.text(
        (width/2, 250),
        "CERTIFICATE OF PARTICIPATION",
        font=title_font,
        fill=navy_blue,  # Navy blue text
        anchor="mm"
    )
    
    # Add 'This is to certify that' text
    draw.text(
        (width/2, 320),
        "This is to certify that",
        font=header_font,
        fill=black,
        anchor="mm"
    )
    
    # Add student name in script font for elegant touch
    student_name = student.get_full_name()
    draw.text(
        (width/2, 370),
        f"{student_name}",
        font=script_font,
        fill=navy_blue,  # Navy blue for emphasis
        anchor="mm"
    )
    
    # Add participation text
    draw.text(
        (width/2, 420),
        "has participated in",
        font=body_font,
        fill=black,
        anchor="mm"
    )
    
    # Add event name in script font
    draw.text(
        (width/2, 470),
        f'"{event.event_name}"',
        font=script_font,
        fill=navy_blue,  # Navy blue for emphasis
        anchor="mm"
    )
    
    # Add event date
    draw.text(
        (width/2, 520),
        f"held on {event.date.strftime('%d %B, %Y')}",
        font=body_font,
        fill=black,
        anchor="mm"
    )
    
    # Add organizing department
    draw.text(
        (width/2, 560),
        f"Organized by Department of {event.get_department_display()}",
        font=body_font,
        fill=black,
        anchor="mm"
    )
    
    # Generate QR code for verification
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,  # Medium error correction for better readability
        box_size=6,
        border=4,
    )
    verification_id = uuid.uuid4().hex
    verification_url = f"https://cmrit.ac.in/verify/{verification_id}"
    qr.add_data(verification_url)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white")
    
    # Resize QR code for better visibility
    qr_img = qr_img.resize((100, 100))
    
    # Add QR code to certificate - positioned at bottom right corner
    qr_pos = (width - 150, height - 150)
    certificate.paste(qr_img, qr_pos, qr_img if qr_img.mode == 'RGBA' else None)
    
    # Try to load signature images
    try:
        from cairosvg import svg2png
        principal_signature_path = os.path.join(settings.BASE_DIR, 'static', 'images', 'principal_signature.svg')
        principal_png_bytes = BytesIO()
        svg2png(url=principal_signature_path, write_to=principal_png_bytes, output_width=120, output_height=60)
        principal_png_bytes.seek(0)
        principal_signature_img = Image.open(principal_png_bytes)
        
        hod_signature_path = os.path.join(settings.BASE_DIR, 'static', 'images', 'hod_signature.svg')
        hod_png_bytes = BytesIO()
        svg2png(url=hod_signature_path, write_to=hod_png_bytes, output_width=120, output_height=60)
        hod_png_bytes.seek(0)
        hod_signature_img = Image.open(hod_png_bytes)
        
        # Add principal signature
        principal_sig_pos = (width//3, height - 200)
        certificate.paste(principal_signature_img, principal_sig_pos, principal_signature_img if principal_signature_img.mode == 'RGBA' else None)
        
        # Add HOD signature
        hod_sig_pos = (width*2//3, height - 200)
        certificate.paste(hod_signature_img, hod_sig_pos, hod_signature_img if hod_signature_img.mode == 'RGBA' else None)
    except Exception as e:
        print(f"Error loading signatures: {e}")
    
    # Add Principal signature text
    draw.text(
        (width//3, height - 160),
        "Dr. Sanjay Jain",
        font=signature_font,
        fill=black,
        anchor="mm"
    )
    draw.text(
        (width//3, height - 130),
        "Principal",
        font=verification_font,
        fill=black,
        anchor="mm"
    )
    draw.text(
        (width//3, height - 110),
        "CMR Institute of Technology, Bengaluru",
        font=verification_font,
        fill=black,
        anchor="mm"
    )
    
    # Add HOD signature text based on department
    hod_name = ""
    if event.department == "CIVIL":
        hod_name = "Mrs. Preeti Jacob"
        hod_title = "Assistant Professor & HOD"
        dept_name = "Department of Civil Engineering"
    elif event.department == "CSE":
        hod_name = "Dr. Kesavamoorthy"
        hod_title = "Professor & HOD"
        dept_name = "Department of Computer Science & Engineering"
    elif event.department == "ISE":
        hod_name = "Dr. Jagadishwari V"
        hod_title = "Professor & HOD"
        dept_name = "Department of Information Science & Engineering"
    else:
        # Default HOD information if department doesn't match
        hod_name = "Department HOD"
        hod_title = "Professor & HOD"
        dept_name = f"Department of {event.get_department_display()}"
    
    draw.text(
        (width*2//3, height - 160),
        hod_name,
        font=signature_font,
        fill=black,
        anchor="mm"
    )
    draw.text(
        (width*2//3, height - 130),
        hod_title,
        font=verification_font,
        fill=black,
        anchor="mm"
    )
    draw.text(
        (width*2//3, height - 110),
        dept_name,
        font=verification_font,
        fill=black,
        anchor="mm"
    )
    
    # Add certificate ID and date at the bottom
    draw.text(
        (width/2, height - 35),
        f"Certificate ID: {verification_id} | Generated on: {datetime.now().strftime('%d-%m-%Y')}",
        font=footer_font,
        fill=black,
        anchor="mm"
    )
    
    # Save certificate to BytesIO - using PNG format first for better image handling
    certificate_io = BytesIO()
    certificate.save(certificate_io, format='PNG', quality=95, dpi=(300, 300))
    certificate_io.seek(0)
    
    # Convert PNG to PDF to ensure images are properly embedded
    from PIL import Image as PILImage
    temp_img = PILImage.open(certificate_io)
    pdf_io = BytesIO()
    temp_img.save(pdf_io, format='PDF', resolution=300.0)
    pdf_io.seek(0)
    certificate_io = pdf_io
    
    # Save to storage and get URL with improved handling
    certificate_filename = f"certificates/{event.event_id}_{student.username}_{verification_id}.pdf"
    
    # Ensure we're reading from the beginning of the file
    certificate_io.seek(0)
    content = certificate_io.read()
    
    # Save the PDF content
    certificate_path = default_storage.save(certificate_filename, ContentFile(content))
    certificate_url = default_storage.url(certificate_path)
    
    return certificate_url, verification_id


def verify_certificate(verification_id):
    """
    Verify a certificate using its verification ID
    
    Args:
        verification_id: The unique verification ID for the certificate
    
    Returns:
        dict: Certificate verification details or None if not found
    """
    from .models import EventRegistration
    
    try:
        # Extract verification ID from the certificate URL
        registration = EventRegistration.objects.filter(
            certificate_url__contains=verification_id
        ).first()
        
        if registration:
            return {
                'valid': True,
                'student_name': registration.student.get_full_name(),
                'event_name': registration.event.event_name,
                'event_date': registration.event.date.strftime('%d %B, %Y'),
                'department': registration.event.get_department_display(),
                'issue_date': registration.certificate_generated_date.strftime('%d %B, %Y') if hasattr(registration, 'certificate_generated_date') else 'Unknown'
            }
        return {'valid': False, 'message': 'Certificate not found'}
    except Exception as e:
        return {'valid': False, 'message': str(e)}


def check_and_generate_certificates(event):
    """
    Generate certificates for students who have been graded for an event.
    No restrictions on when certificates can be generated.
    
    Args:
        event: The Event object
        
    Returns:
        bool: True if certificates were generated, False otherwise
    """
    from .models import EventAssessment, AssessmentSubmission, EventRegistration
    
    # Get all students registered for this event
    registrations = EventRegistration.objects.filter(event=event)
    registered_students = [reg.student for reg in registrations]
    
    if not registered_students:
        return False
    
    # Get all assessments for this event
    assessments = EventAssessment.objects.filter(event=event)
    
    # Find students who have at least one graded submission with passing score
    students_with_passing_grades = set()
    
    for assessment in assessments:
        # Get students who have graded submissions with passing score for this assessment
        graded_students = AssessmentSubmission.objects.filter(
            assessment=assessment,
            student__in=registered_students,
            score__isnull=False,
            score__gte=assessment.passing_score  # Only include students who meet the passing score
        ).values_list('student', flat=True)
        
        # Add these students to our set
        students_with_passing_grades.update(graded_students)
    
    # Generate certificates for students who have at least one graded submission with passing score
    certificates_generated = False
    
    for registration in registrations:
        if registration.student.id in students_with_passing_grades and not registration.certificate_generated:
            certificate_url, verification_id = generate_certificate(event, registration.student)
            registration.certificate_url = certificate_url
            registration.certificate_generated = True
            registration.certificate_generated_date = datetime.now()
            registration.save()
            certificates_generated = True
    
    return certificates_generated