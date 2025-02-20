from PIL import Image
import os
import hashlib
from cryptography.fernet import Fernet
from base64 import b64encode
from pillow_heif import register_heif_opener

# Register HEIF/HEIC support
register_heif_opener()

def get_key_from_password(password):
    """Generate a Fernet key from a password"""
    # Hash the password and use it to create a Fernet key
    hashed = hashlib.sha256(password.encode()).digest()
    return b64encode(hashed[:32])

def convert_to_png(image_path):
    """Convert any image format to PNG"""
    try:
        with Image.open(image_path) as img:
            # Convert to RGB mode if needed
            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Create new filename with PNG extension
            new_path = os.path.splitext(image_path)[0] + '.png'
            img.save(new_path, 'PNG')
            return new_path
    except Exception as e:
        raise ValueError(f"Image conversion failed: {str(e)}")

def encode_message(image_path, message, output_path, password):
    """Encodes a secret message into an image using LSB steganography with password protection."""
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Input image '{image_path}' does not exist")
    
    try:
        # Convert image to PNG if it's not already
        if not image_path.lower().endswith('.png'):
            image_path = convert_to_png(image_path)
        
        # Encrypt message with password
        key = get_key_from_password(password)
        f = Fernet(key)
        encrypted_message = f.encrypt(message.encode()).decode()
        
        # Convert encrypted message to binary
        binary_message = ''.join([format(ord(char), '08b') for char in encrypted_message]) + '0000000000000000'
        
        # Open and convert image to RGB
        img = Image.open(image_path).convert('RGB')
        width, height = img.size
        pixels = list(img.getdata())
        
        if len(binary_message) > len(pixels) * 3:
            raise ValueError("Message is too large for this image")
        
        # Encode the message
        binary_index = 0
        new_pixels = []
        for pixel in pixels:
            new_pixel = list(pixel)
            for color_channel in range(3):
                if binary_index < len(binary_message):
                    # Clear the least significant bit and add message bit
                    new_pixel[color_channel] = new_pixel[color_channel] & ~1
                    new_pixel[color_channel] = new_pixel[color_channel] | int(binary_message[binary_index])
                    binary_index += 1
            new_pixels.append(tuple(new_pixel))
        
        # Create new image with encoded message
        new_img = Image.new('RGB', (width, height))
        new_img.putdata(new_pixels)
        new_img.save(output_path, 'PNG')
        return True
    except Exception as e:
        print(f"Error during encoding: {str(e)}")
        raise

def decode_message(image_path, password):
    """Decodes a hidden message from an image using password."""
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Input image '{image_path}' does not exist")
    
    try:
        # Extract binary message (same as before)
        img = Image.open(image_path).convert('RGB')
        pixels = list(img.getdata())
        
        binary_message = ''
        for pixel in pixels:
            for color_channel in range(3):
                binary_message += str(pixel[color_channel] & 1)
        
        # Convert binary to encrypted text
        encrypted_message = ''
        for i in range(0, len(binary_message)-16, 8):
            byte = binary_message[i:i+8]
            if byte == '00000000':
                break
            encrypted_message += chr(int(byte, 2))
        
        # Decrypt message with password
        key = get_key_from_password(password)
        f = Fernet(key)
        try:
            decrypted_message = f.decrypt(encrypted_message.encode()).decode()
            return decrypted_message
        except:
            raise ValueError("Invalid password or corrupted message")
            
    except Exception as e:
        print(f"Error during decoding: {str(e)}")
        raise

# Example Usage with error handling:
if __name__ == "__main__":

    try:
        # Specify the full path to your input image
        input_image = "E:/Pictures/sample.png"  # Change this to your actual image path
        output_image = "E:/Pictures/output.png" # Change this to your desired output path
        password = "your_password"  # Change this to your desired password
        
        if os.path.exists(input_image):
            encode_message(input_image, "Hello, this is a secret!", output_image, password)
            decode_message(output_image, password)
        else:
            print(f"Error: The image file '{input_image}' was not found.")
            print("Please make sure to:")
            print("1. Replace the input_image path with the actual path to your image")
            print("2. Verify that the image file exists in the specified location")
            print("Example: input_image = 'C:/Users/YourName/Pictures/image.png'")
    except Exception as e:
        print(f"An error occurred: {str(e)}")
