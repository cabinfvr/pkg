from flask import Flask, render_template, url_for, abort, request, redirect, session, flash, jsonify, send_from_directory
from helper import *
from logos import Logos
import requests
from supabase import create_client, Client
import json 
from functools import wraps
import os
import uuid
from werkzeug.utils import secure_filename
from PIL import Image
import io

# CDN Integration
class CdnImageObject:
    """
    Represents an image to upload:
      - filename:      the path/key under your bucket (e.g. "avatars/user.png")
      - data:          raw bytes of the file
      - content_type:  MIME type, e.g. "image/png"
    """
    def __init__(self, filename: str, data: bytes, content_type: str):
        self.filename = filename
        self.data = data
        # Ensure content_type is never None
        self.content_type = content_type or "application/octet-stream"

def preprocess_image(image_bytes: bytes, size: int = 256) -> bytes:
    """
    Crop the input image to a centered square and resize to the specified size.
    
    :param image_bytes: Raw image bytes.
    :param size: Desired output size (both width and height).
    :return: Processed image as bytes.
    """
    with Image.open(io.BytesIO(image_bytes)) as img:
        # Ensure image is in RGBA mode for consistency
        img = img.convert("RGBA")
        width, height = img.size
        # Determine the size of the square crop
        min_dim = min(width, height)
        left = (width - min_dim) // 2
        top = (height - min_dim) // 2
        right = left + min_dim
        bottom = top + min_dim
        # Crop and resize the image
        img_cropped = img.crop((left, top, right, bottom))
        img_resized = img_cropped.resize((size, size), Image.LANCZOS)
        # Save the processed image to a bytes buffer
        buffer = io.BytesIO()
        img_resized.save(buffer, format="PNG")
        return buffer.getvalue()

class cdn:
    """
    CDN service for uploading images via Supabase:

      - upload() sends bytes to Storage,
      - makes them public,
      - records metadata in your database.
    """
    def __init__(self, supabase_client, bucket: str, table: str = "cdn_images"):
        self.supabase = supabase_client
        self.bucket_name = bucket
        self.table_name = table

    def upload(self, image_obj: CdnImageObject) -> str:
        """
        Uploads to Supabase Storage, makes public, and records metadata.

        :param image_obj: instance of CdnImageObject
        :return: the public URL of the uploaded file
        """
        # Preprocess the image
        processed_data = preprocess_image(image_obj.data)
        
        # Ensure content_type is a valid string
        content_type = image_obj.content_type or "image/png"
        if not isinstance(content_type, str) or not content_type.strip():
            content_type = "image/png"

        # 1) Upload processed bytes
        try:
            res = self.supabase.storage.from_(self.bucket_name).upload(
                path=image_obj.filename,
                file=processed_data,
                file_options={"content-type": content_type, "upsert": "true"}
            )
            # Check if upload was successful by examining the response
            if not hasattr(res, 'path') or not res.path:
                raise RuntimeError(f"Upload failed: Unexpected response format")
        except Exception as e:
            raise RuntimeError(f"Upload failed: {str(e)}")

        # 2) Construct public URL
        public_url = self.supabase.storage.from_(self.bucket_name).create_signed_url(image_obj.filename, 60 * 60 * 24 * 7)

        # 3) Insert metadata record (optional - will skip if table doesn't exist)
        try:
            insert_payload = {
                "filename": image_obj.filename,
                "url": public_url['signedURL'],
                "content_type": content_type
            }
            db_res = self.supabase.table(self.table_name).insert(insert_payload).execute()
            print(f"Metadata saved to database table '{self.table_name}'")
        except Exception as e:
            print(f"Warning: Could not save metadata to database table '{self.table_name}': {str(e)}")
            print("The file was uploaded successfully, but metadata was not recorded.")

        return public_url

app = Flask(__name__)
app.secret_key = os.environ['SECRET_KEY'] 

SUPABASE_URL = os.environ['SUPABASE_URL']
SUPABASE_KEY = os.environ['SUPABASE_KEY']
SUPABASE_STORAGE_BUCKET = os.environ.get('SUPABASE_STORAGE_BUCKET', 'images')

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Initialize CDN service
cdn_service = cdn(supabase, SUPABASE_STORAGE_BUCKET)

# Configure upload settings
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB

@app.route('/_next/<path:filename>')
def custom_static(filename):
    return send_from_directory('_next', filename)

@app.route('/favicon.ico')
def send_favicon():
    return send_from_directory('static', 'favicon.ico')

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def login_required(f):
    """Decorator to require login for certain routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'access_token' not in session or 'user' not in session:
            flash('Please log in to access this page.', 'info')
            return redirect(url_for('login'))
        
        # Try to validate the current session
        try:
            access_token = session.get('access_token')
            refresh_token_val = session.get('refresh_token')
            
            if access_token and refresh_token_val:
                # Try to get current user to validate session
                supabase.auth.set_session(access_token, refresh_token_val)
                user = supabase.auth.get_user()
                
                if not user or not user.user:
                    # Session is invalid
                    session.clear()
                    flash('Your session has expired. Please log in again.', 'info')
                    return redirect(url_for('login'))
            else:
                # Missing tokens
                session.clear()
                flash('Please log in to access this page.', 'info')
                return redirect(url_for('login'))
                
        except Exception as e:
            print(f"Session validation error: {e}")
            session.clear()
            flash('Your session has expired. Please log in again.', 'info')
            return redirect(url_for('login'))
        
        return f(*args, **kwargs)
    return decorated_function

def get_user_by_username(username):
    """Fetch user data from Supabase by username"""
    try:
        response = supabase.table('profiles').select('*').eq('username', username).execute()
        
        if response.data and len(response.data) > 0:
            return response.data[0]
        else:
            return None
    except Exception as e:
        print(f"Error fetching user data: {e}")
        return None

def get_user_count():
    """Fetch the count of users from Supabase"""
    try:
        response = supabase.table('profiles').select('*').execute()
        return len(response.data)
    except Exception as e:
        print(f'Error fetching user count: {e}')
        return 10
    
def get_user_by_id(user_id):
    """Fetch user data from Supabase by id"""
    try:
        response = supabase.table('profiles').select('*').eq('id', user_id).execute() 
        
        if response.data and len(response.data) > 0:
            return response.data[0]
        else:
            return None
    except Exception as e:
        print(f"Error fetching user data: {e}")
        return None

def create_or_update_profile(user_id, username, **kwargs):
    """Create or update user profile in profiles table"""
    try:
        # Validate required fields
        if not user_id or not username:
            print("Missing required fields: user_id or username")
            return None
            
        # Check if profile exists
        existing_profile = get_user_by_id(user_id)
        
        profile_data = {
            'id': user_id,
            'username': username,
            'avatar_link': kwargs.get('avatar_link', 'https://pkg-cdn.vercel.app/blank.webp'),
            'quote': kwargs.get('quote', 'this is a blank account.'),
            'badges': kwargs.get('badges', []),
            'links': kwargs.get('links', {}),
            'discord_id': kwargs.get('discord_id')
        }
        
        print(f"Creating/updating profile for user_id: {user_id}, username: {username}")
        print(f"Profile data: {profile_data}")
        
        if existing_profile:
            # Update existing profile
            print("Updating existing profile")
            response = supabase.table('profiles').update(profile_data).eq('id', user_id).execute()
        else:
            # Create new profile
            print("Creating new profile")
            response = supabase.table('profiles').insert(profile_data).execute()
        
        print(f"Supabase response: {response}")
        
        # Check if the operation was successful
        if hasattr(response, 'data') and response.data:
            print("Profile operation successful")
            return response.data[0]
        else:
            print(f"Profile operation failed - no data returned")
            if hasattr(response, 'error') and response.error:
                print(f"Supabase error: {response.error}")
            return None
            
    except Exception as e:
        print(f"Error creating/updating profile: {e}")
        print(f"Exception type: {type(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        return None

def format_user_data(user_data):
    """Format user data from database to match the expected bio_config structure"""
    if not user_data:
        return None
    
    badges = user_data.get('badges', [])
    links_data = user_data.get('links', {})
    links = []
    
    for service, info in links_data.items():
        if isinstance(info, dict) and 'link' in info:
            links.append({
                'name': service.title(),  
                'url': info['link'],
                'icon': info.get('bxl_class', f'bx-{service.lower()}')
            })
    
    bio_config = {
        'profile_picture_url': user_data.get('avatar_link', 'https://via.placeholder.com/150'),
        'username': user_data.get('username'),
        'quote': user_data.get('quote', ''),
        'supporter': 'supporter' in badges,
        'verified': 'verified' in badges,
        'owner': 'owner' in badges,
        'early': 'early' in badges,
        'discord_user_id': user_data.get('discord_id'),
        'links': links
    }
    
    return bio_config

# Image Upload Route
@app.route('/upload-avatar', methods=['POST'])
@login_required
def upload_avatar():
    """Handle avatar image upload"""
    try:
        if 'avatar_file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['avatar_file']
        
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if not allowed_file(file.filename):
            return jsonify({'error': 'File type not allowed. Please use PNG, JPG, JPEG, GIF, or WEBP'}), 400
        
        # Check file size
        file_data = file.read()
        if len(file_data) > MAX_FILE_SIZE:
            return jsonify({'error': 'File too large. Maximum size is 5MB'}), 400
        
        # Generate unique filename
        file_extension = file.filename.rsplit('.', 1)[1].lower()
        unique_filename = f"avatars/{session['user']['id']}_{uuid.uuid4().hex}.{file_extension}"
        
        # Create CDN image object
        image_obj = CdnImageObject(
            filename=unique_filename,
            data=file_data,
            content_type=file.content_type
        )
        
        # Upload to CDN
        public_url = cdn_service.upload(image_obj)
        
        return jsonify({
            'success': True,
            'url': public_url,
            'message': 'Image uploaded successfully'
        })
        
    except Exception as e:
        print(f"Upload error: {e}")
        return jsonify({'error': 'Upload failed. Please try again.'}), 500

# Authentication routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        try:
            # Sign in with Supabase Auth
            response = supabase.auth.sign_in_with_password({
                "email": email,
                "password": password
            })
            
            if response.user:
                # Store auth data in session
                session['access_token'] = response.session.access_token
                session['refresh_token'] = response.session.refresh_token
                session['user'] = {
                    'id': response.user.id,
                    'email': response.user.email
                }
                
                # Check if profile exists, if not redirect to onboarding
                profile = get_user_by_id(response.user.id)
                if not profile:
                    return redirect(url_for('onboarding'))
                
                flash('Logged in successfully!', 'success')
                return redirect(url_for('dashboard'))
            else:
                flash('Invalid email or password', 'error')
                
        except Exception as e:
            print(f"Login error: {e}")
            flash('Invalid email or password', 'error')
    
    return render_template('auth/login.html', url_for=url_for)

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        username = request.form['username']
        
        # Basic validation
        if len(username) < 3:
            flash('Username must be at least 3 characters long', 'error')
            return render_template('auth/signup.html', url_for=url_for)
        
        if len(password) < 6:
            flash('Password must be at least 6 characters long', 'error')
            return render_template('auth/signup.html', url_for=url_for)
        
        if password != confirm_password:
            flash('Passwords do not match', 'error')
            return render_template('auth/signup.html', url_for=url_for)
        
        try:
            # Check if username already exists
            existing_user = get_user_by_username(username)
            if existing_user:
                flash('Username already taken', 'error')
                return render_template('auth/signup.html', url_for=url_for)
            
            # Sign up with Supabase Auth
            response = supabase.auth.sign_up({
                "email": email,
                "password": password
            })
            
            if response.user:
                print(f"User created with ID: {response.user.id}")
                
                # Store auth data in session
                session['access_token'] = response.session.access_token if response.session else None
                session['refresh_token'] = response.session.refresh_token if response.session else None
                session['user'] = {
                    'id': response.user.id,
                    'email': response.user.email
                }
                session['pending_username'] = username  # Store username for onboarding
                
                if response.session:
                    # User is confirmed, try to create basic profile immediately
                    try:
                        profile = create_or_update_profile(
                            response.user.id, 
                            username,
                            avatar_link='https://pkg-cdn.vercel.app/blank.webp',
                            quote='this is a blank account.',
                            badges=[],
                            links={},
                            discord_id=None
                        )
                        
                        if profile:
                            print(f"Profile created successfully for user: {username}")
                            flash('Account created successfully!', 'success')
                            return redirect(url_for('onboarding'))
                        else:
                            print(f"Failed to create profile for user: {username}")
                            # Profile creation failed, but auth user exists
                            # Clean up by deleting the auth user if possible
                            try:
                                supabase.auth.admin.delete_user(response.user.id)
                            except:
                                pass  # Admin delete might not be available
                            
                            session.clear()
                            flash('Error creating user profile. Please try again.', 'error')
                            return render_template('auth/signup.html', url_for=url_for)
                            
                    except Exception as profile_error:
                        print(f"Profile creation error: {profile_error}")
                        session.clear()
                        flash('Database error saving new user. Please try again.', 'error')
                        return render_template('auth/signup.html', url_for=url_for)
                else:
                    # Email confirmation required
                    flash('Please check your email to confirm your account before logging in', 'info')
                    return redirect(url_for('login'))
            else:
                print("No user returned from Supabase auth signup")
                flash('Error creating account', 'error')
                
        except Exception as e:
            print(f"Signup error: {e}")
            # More specific error messages based on the exception
            error_message = str(e).lower()
            if 'email' in error_message and 'already' in error_message:
                flash('An account with this email already exists', 'error')
            elif 'password' in error_message:
                flash('Password does not meet requirements', 'error')
            elif 'database' in error_message or 'connection' in error_message:
                flash('Database error saving new user. Please try again later.', 'error')
            else:
                flash('An error occurred during signup. Please try again.', 'error')
    
    return render_template('auth/signup.html', url_for=url_for)

@app.route('/logout')
def logout():
    try:
        # Sign out with Supabase Auth
        supabase.auth.sign_out()
    except Exception as e:
        print(f"Logout error: {e}")
    
    session.clear()
    flash('Logged out successfully!', 'success')
    return redirect(url_for('home'))

@app.route('/onboarding', methods=['GET', 'POST'])
@login_required
def onboarding():
    logos = Logos()
    
    # Get the username from session (set during signup)
    username = session.get('pending_username')
    if not username:
        # If no pending username, user might have refreshed or came here directly
        # Check if they already have a profile
        user_data = get_user_by_id(session['user']['id'])
        if user_data:
            # User already has a profile, redirect to dashboard
            return redirect(url_for('dashboard'))
        else:
            # No profile and no pending username, something went wrong
            flash('Session expired. Please sign up again.', 'error')
            return redirect(url_for('signup'))
    
    if request.method == 'POST':
        try:
            user_id = session['user']['id']
            
            # Use the username from session (no need to ask again)
            # username is already set from above
            
            # Check if username is taken by another user (shouldn't happen, but safety check)
            existing_user = get_user_by_username(username)
            if existing_user and existing_user['id'] != user_id:
                flash('Username conflict detected. Please contact support.', 'error')
                return render_template('onboarding.html', url_for=url_for, logos=logos.get_all(), clean_string=clean_string, username=username)
            
            # Get form data
            avatar_link = request.form.get('avatar_link', '').strip()
            quote = request.form.get('quote', '').strip()
            discord_id = request.form.get('discord_id', '').strip()
            
            # Process links
            links = {}
            for key, value in request.form.items():
                if key.startswith('link_') and value.strip():
                    service = key.replace('link_', '')
                    brand_info = logos.get_brand(service)
                    links[service] = {
                        'link': value.strip(),
                        'bxl_class': brand_info.get('bxl_class', f'bx-{service}')
                    }
            
            # Create profile with the username from signup
            profile_data = {
                'avatar_link': avatar_link if avatar_link else 'https://pkg-cdn.vercel.app/blank.webp',
                'quote': quote,
                'links': links,
                'discord_id': int(discord_id) if discord_id else None
            }
            
            profile = create_or_update_profile(user_id, username, **profile_data)
            
            if profile:
                # Clear pending username from session
                session.pop('pending_username', None)
                flash(f'Welcome, {username}! Your profile has been created.', 'success')
                return redirect(url_for('dashboard'))
            else:
                flash('Error setting up profile', 'error')
                
        except Exception as e:
            print(f"Onboarding error: {e}")
            flash('An error occurred while setting up your profile', 'error')
    
    # Pass username to template so it can be displayed (read-only)
    return render_template('onboarding.html', url_for=url_for, logos=logos.get_all(), clean_string=clean_string, username=username)


# Dashboard route
@app.route('/dashboard')
@login_required
def dashboard():
    user_data = get_user_by_id(session['user']['id'])
    bio_config = format_user_data(user_data)
    return render_template('dashboard.html', url_for=url_for, user_data=user_data, bio_config=bio_config)

@app.route('/dashboard/edit', methods=['GET', 'POST'])
@login_required
def dashboard_edit():
    logos = Logos()
    user_data = get_user_by_id(session['user']['id'])
    
    if request.method == 'POST':
        try:
            user_id = session['user']['id']
            
            # Get form data
            avatar_link = request.form.get('avatar_link', '').strip()
            quote = request.form.get('quote', '').strip()
            discord_id = request.form.get('discord_id', '').strip()
            
            # Process links
            links = {}
            
            # Find all link services by looking for fields that start with 'link_' 
            # but exclude the name and icon fields
            link_services = set()
            for key in request.form.keys():
                if key.startswith('link_') and not key.startswith('link_name_') and not key.startswith('link_icon_'):
                    service = key.replace('link_', '')
                    link_services.add(service)
            
            # Process each service
            for service in link_services:
                url = request.form.get(f'link_{service}', '').strip()
                name = request.form.get(f'link_name_{service}', '').strip()
                icon = request.form.get(f'link_icon_{service}', '').strip()
                
                # Only add if URL exists
                if url:
                    # Use the name as the key if provided, otherwise use service
                    link_key = name if name else service
                    
                    # Get brand info if it exists
                    brand_info = logos.get_brand(service)
                    default_icon = brand_info.get('bxl_class', f'bx-{service}') if brand_info else 'bx-link'
                    
                    links[link_key] = {
                        'link': url,
                        'bxl_class': icon if icon else default_icon
                    }
            
            # Update user data
            update_data = {
                'avatar_link': avatar_link if avatar_link else user_data.get('avatar_link'),
                'quote': quote,
                'links': links
            }
            
            if discord_id:
                update_data['discord_id'] = int(discord_id)
            elif discord_id == '':
                update_data['discord_id'] = None
            
            response = supabase.table('profiles').update(update_data).eq('id', user_id).execute()
            
            if response.data:
                flash('Profile updated successfully!', 'success')
                return redirect(url_for('dashboard'))
            else:
                flash('Error updating profile', 'error')
                
        except Exception as e:
            print(f"Dashboard edit error: {e}")
            flash('An error occurred while updating your profile', 'error')
    
    return render_template('dashboard_edit.html', url_for=url_for, user_data=user_data, logos=logos.get_all(), clean_string=clean_string)

@app.route('/')
def home():
    active_user_count = get_user_count()
    return render_template('home.html', url_for=url_for, clean_string=clean_string, active_user_count=active_user_count)

@app.route('/<username>')
def about(username):
    # Fetch user data from Supabase
    user_data = get_user_by_username(username)
    
    if not user_data:
        # User not found in database
        abort(404)
    
    # Format the data for the template
    bio_config = format_user_data(user_data)
    
    # Fetch Discord activity if user ID is provided
    discord_activity = None
    if bio_config.get('discord_user_id'):
        discord_activity = get_discord_activity(bio_config['discord_user_id'])
    
    return render_template('bio.html',
                         url_for=url_for,
                         discord_activity=discord_activity,
                         **bio_config)

@app.route('/testing/basicSelect')
def basic_select():
    options = Logos().get_options()
    return render_template('testing/basicSelect.html', url_for=url_for, options=options, clean_string=clean_string)

@app.route('/testing/activityParsing/<id>')
def activity_parsing(id):
    response = requests.get(f'https://lanyard.rest/v1/users/{id}')
    if response.status_code == 200:
        data = response.json()
        activity = parse_activity(data)
    else:
        print(response.status_code, response.text)
        activity = None
    
    return render_template('testing/activityParsing.html', url_for=url_for, activity=activity, clean_string=clean_string)

if __name__ == '__main__':
    app.run('localhost', port=3000, debug=True)