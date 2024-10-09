from PIL import Image
import base64

def save_image(image: Image.Image, path: str):
    """Saves a PIL image to a file."""
    image.save(path)
    print(f"Image saved to {path}.")

def encode_image(image_path):
    """Encodes an image as base64."""
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')
