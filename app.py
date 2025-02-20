from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for, flash, get_flashed_messages
from flask_cors import CORS
from flask_wtf.csrf import CSRFProtect
import os
from PIL import Image
import numpy as np
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)
csrf = CSRFProtect(app)
CORS(app, resources={
    r"/api/*": {
        "origins": "*",
        "methods": ["POST", "OPTIONS"],
        "allow_headers": ["Content-Type"]
    }
})

# Configure upload folder and allowed extensions
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def ensure_upload_folder():
    """Ensure upload folder exists"""
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def safe_delete(path):
    """Safely delete a file with retries"""
    try:
        if os.path.exists(path):
            os.remove(path)
        return True
    except Exception as e:
        print(f"Error deleting {path}: {e}")
        return False

def text_to_binary(text):
    """Convert text to binary string"""
    binary = ''.join(format(ord(char), '08b') for char in text)
    return binary + '1111111111111110'  # Add delimiter

def binary_to_text(binary):
    """Convert binary string to text"""
    # Find delimiter
    delimiter_index = binary.find('1111111111111110')
    if (delimiter_index == -1):
        return None
    
    binary = binary[:delimiter_index]
    # Convert each 8 bits to character
    text = ''.join(chr(int(binary[i:i+8], 2)) for i in range(0, len(binary), 8))
    return text

def encode_message(image_path, message, output_path, password):
    try:
        # Load image
        img = Image.open(image_path)
        pixels = np.array(img)
        
        # Convert message to binary
        binary_message = text_to_binary(message)
        if len(binary_message) > pixels.size:
            raise ValueError("Message too large for this image")
        
        # Flatten the pixel array to make it easier to iterate
        flat_pixels = pixels.reshape(-1, 3)
        binary_index = 0
        
        # Modify LSB of each color channel
        for i in range(len(flat_pixels)):
            for j in range(3):  # RGB channels
                if binary_index < len(binary_message):
                    # Clear the LSB and set it to the message bit
                    flat_pixels[i][j] = (flat_pixels[i][j] & ~1) | int(binary_message[binary_index])
                    binary_index += 1
        
        # Reshape back to original dimensions
        encoded_pixels = flat_pixels.reshape(pixels.shape)
        
        # Save encoded image
        encoded_img = Image.fromarray(encoded_pixels.astype('uint8'))
        encoded_img.save(output_path, 'PNG')
        return True
        
    except Exception as e:
        print(f"Encoding error: {str(e)}")
        return False

def decode_message(image_path, password):
    try:
        # Load image
        img = Image.open(image_path)
        pixels = np.array(img)
        
        # Flatten pixel array
        flat_pixels = pixels.reshape(-1, 3)
        binary_message = ''
        
        # Extract LSB from each color channel
        for pixel in flat_pixels:
            for channel in pixel:
                binary_message += str(channel & 1)
                # Check for delimiter as we go
                if len(binary_message) >= 16 and binary_message[-16:] == '1111111111111110':
                    return binary_to_text(binary_message)
        
        return None
        
    except Exception as e:
        print(f"Decoding error: {str(e)}")
        return None

@app.context_processor
def utility_processor():
    return {
        'get_flash_messages': get_flash_messages
    }

def get_flash_messages():
    messages = []
    for category, message in get_flashed_messages(with_categories=True):
        messages.append({'category': category, 'message': message})
    return messages

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/encode')
def encode_page():
    return render_template('encode.html')

@app.route('/decode')
def decode_page():
    return render_template('decode.html')

@app.route('/api/encode', methods=['POST'])
@csrf.exempt
def encode():
    try:
        ensure_upload_folder()
        
        if 'image' not in request.files:
            return jsonify({'error': 'No image file uploaded'}), 400
        
        file = request.files['image']
        message = request.form.get('message')
        password = request.form.get('password')
        
        if not all([file.filename, message, password]):
            return jsonify({'error': 'Missing required fields'}), 400
            
        if not allowed_file(file.filename):
            return jsonify({'error': 'Invalid file type'}), 400

        # Save original image
        input_filename = secure_filename(file.filename)
        input_path = os.path.join(app.config['UPLOAD_FOLDER'], f'input_{input_filename}')
        output_path = os.path.join(app.config['UPLOAD_FOLDER'], f'encoded_{input_filename}')
        file.save(input_path)

        # Encode message
        if encode_message(input_path, message, output_path, password):
            flash('Message encoded successfully!', 'success')
            return send_file(output_path, 
                           as_attachment=True,
                           download_name='encoded_image.png',
                           mimetype='image/png')
        else:
            flash('Encoding failed!', 'error')
            return jsonify({'error': 'Encoding failed'}), 500

    except Exception as e:
        flash(str(e), 'error')
        return jsonify({'error': str(e)}), 500

@app.route('/api/decode', methods=['POST'])
@csrf.exempt
def decode():
    try:
        ensure_upload_folder()
        
        if 'image' not in request.files:
            return jsonify({'error': 'No image file uploaded'}), 400
        
        file = request.files['image']
        password = request.form.get('password')
        
        if not all([file.filename, password]):
            return jsonify({'error': 'Missing required fields'}), 400
            
        if not allowed_file(file.filename):
            return jsonify({'error': 'Invalid file type'}), 400

        # Save and decode image
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        message = decode_message(filepath, password)
        if message:
            flash('Message decoded successfully!', 'success')
            return jsonify({
                'success': True,
                'message': message
            })
        else:
            flash('No message found or invalid password', 'error')
            return jsonify({'error': 'Decoding failed'}), 400

    except Exception as e:
        flash(str(e), 'error')
        return jsonify({'error': str(e)}), 500

@app.after_request
def add_header(response):
    """Add headers to both force latest IE rendering engine or Chrome Frame,
       and also to cache the rendered page for 10 minutes."""
    response.headers['X-UA-Compatible'] = 'IE=Edge,chrome=1'
    response.headers['Cache-Control'] = 'public, max-age=0'
    return response

@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
    response.headers.add('Access-Control-Allow-Methods', 'POST, OPTIONS')
    return response

@app.errorhandler(404)
def not_found_error(error):
    return redirect(url_for('index'))

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    # Ensure upload folder exists on startup
    ensure_upload_folder()
    # Run the app in debug mode
    app.run(debug=True, port=5000)
