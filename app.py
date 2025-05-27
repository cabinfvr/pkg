from flask import Flask, render_template, url_for, abort, request, redirect, session, flash, jsonify
from helper import *
from logos import Logos
import requests
from supabase import create_client, Client
import hashlib
import json 
import secrets
from functools import wraps
import os

app = Flask(__name__)
app.secret_key = os.environ['SECRET_KEY']  # Change this to a secure secret key

SUPABASE_URL = os.environ['SUPABASE_URL']
SUPABASE_KEY = os.environ['SUPABASE_KEY']

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def hash_password(password):
    """Hash password with salt"""
    salt = secrets.token_hex(16)
    pwd_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 100000)
    return salt + pwd_hash.hex()

def verify_password(stored_password, provided_password):
    """Verify password against stored hash"""
    salt = stored_password[:32]
    stored_hash = stored_password[32:]
    pwd_hash = hashlib.pbkdf2_hmac('sha256', provided_password.encode('utf-8'), salt.encode('utf-8'), 100000)
    return pwd_hash.hex() == stored_hash

def login_required(f):
    """Decorator to require login for certain routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def get_user_by_username(username):
    """Fetch user data from Supabase by username"""
    try:
        response = supabase.table('users').select('*').eq('username', username).execute()
        
        if response.data and len(response.data) > 0:
            return response.data[0]
        else:
            return None
    except Exception as e:
        print(f"Error fetching user data: {e}")
        return None

def get_user_by_id(user_id):
    """Fetch user data from Supabase by id"""
    try:
        response = supabase.table('users').select('*').eq('id', user_id).execute()  # Changed from 'user_id' to 'id'
        
        if response.data and len(response.data) > 0:
            return response.data[0]
        else:
            return None
    except Exception as e:
        print(f"Error fetching user data: {e}")
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

# Authentication routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        try:
            # Get user from database including password - using 'id' instead of 'user_id'
            response = supabase.table('users').select('id, username, password_hash').eq('username', username).execute()
            
            if response.data and len(response.data) > 0:
                user = response.data[0]
                if verify_password(user['password_hash'], password):
                    session['user_id'] = user['id']  # Store as 'user_id' in session but use 'id' from DB
                    session['username'] = user['username']
                    flash('Logged in successfully!', 'success')
                    return redirect(url_for('dashboard'))
                else:
                    flash('Invalid username or password', 'error')
            else:
                flash('Invalid username or password', 'error')
                
        except Exception as e:
            print(f"Login error: {e}")
            flash('An error occurred during login', 'error')
    
    return render_template('auth/login.html', url_for=url_for)

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        
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
            
            # Create new user
            password_hash = hash_password(password)
            user_data = {
                'username': username,
                'password_hash': password_hash,
                'avatar_link': 'https://pkg-cdn.vercel.app/blank.webp',
                'quote': 'this is a blank account.',
                'badges': [],
                'links': {}
            }
            
            response = supabase.table('users').insert(user_data).execute()
            
            if response.data:
                # Auto-login after signup
                session['username'] = username
                flash('Account created successfully!', 'success')
                return redirect(url_for('onboarding'))
            else:
                flash('Error creating account', 'error')
                
        except Exception as e:
            print(f"Signup error: {e}")
            flash('An error occurred during signup', 'error')
    
    return render_template('auth/signup.html', url_for=url_for)

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully!', 'success')
    return redirect(url_for('home'))

@app.route('/onboarding', methods=['GET', 'POST'])
@login_required
def onboarding():
    logos = Logos()
    
    if request.method == 'POST':
        try:
            user_id = session['user_id']  # This stays the same since we're storing it as 'user_id' in session
            
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
            
            # Update user data - using 'id' to match the database column
            update_data = {
                'avatar_link': avatar_link if avatar_link else 'https://via.placeholder.com/150',
                'quote': quote,
                'links': links
            }
            
            if discord_id:
                update_data['discord_id'] = int(discord_id)
            
            response = supabase.table('users').update(update_data).eq('id', user_id).execute()  # Changed from 'user_id' to 'id'
            
            if response.data:
                flash('Profile setup completed!', 'success')
                return redirect(url_for('dashboard'))
            else:
                flash('Error updating profile', 'error')
                
        except Exception as e:
            print(f"Onboarding error: {e}")
            flash('An error occurred while setting up your profile', 'error')
    
    return render_template('onboarding.html', url_for=url_for, logos=logos.get_all(), clean_string=clean_string)

# Dashboard route
@app.route('/dashboard')
@login_required
def dashboard():
    user_data = get_user_by_id(session['user_id'])
    bio_config = format_user_data(user_data)
    return render_template('dashboard.html', url_for=url_for, user_data=user_data, bio_config=bio_config)

@app.route('/dashboard/edit', methods=['GET', 'POST'])
@login_required
def dashboard_edit():
    logos = Logos()
    user_data = get_user_by_id(session['user_id'])
    
    if request.method == 'POST':
        try:
            user_id = session['user_id']
            
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
            
            # Update user data - using 'id' to match the database column
            update_data = {
                'avatar_link': avatar_link if avatar_link else user_data.get('avatar_link'),
                'quote': quote,
                'links': links
            }
            
            if discord_id:
                update_data['discord_id'] = int(discord_id)
            elif discord_id == '':
                update_data['discord_id'] = None
            
            response = supabase.table('users').update(update_data).eq('id', user_id).execute()  # Changed from 'user_id' to 'id'
            
            if response.data:
                flash('Profile updated successfully!', 'success')
                return redirect(url_for('dashboard'))
            else:
                flash('Error updating profile', 'error')
                
        except Exception as e:
            print(f"Dashboard edit error: {e}")
            flash('An error occurred while updating your profile', 'error')
    
    return render_template('dashboard_edit.html', url_for=url_for, user_data=user_data, logos=logos.get_all(), clean_string=clean_string)

# Original routes
@app.route('/')
def home():
    return render_template('home.html', url_for=url_for, clean_string=clean_string)

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

# API routes
@app.route('/api/users', methods=['POST'])
def create_user():
    """Example endpoint to create a user - you can remove this if not needed"""
    try:
        data = request.json
        response = supabase.table('users').insert(data).execute()
        return jsonify({"success": True, "data": response.data})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

if __name__ == '__main__':
    app.run('localhost', port=3000, debug=True)
