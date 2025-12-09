import re
from datetime import datetime
import uuid
import os
from pathlib import Path
from PIL import Image
from fastapi import UploadFile
from core.config import settings

async def process_and_save_image(file: UploadFile, folder_name: str, username: str) -> str:
    file_ext = Path(file.filename).suffix.lower()

    if file_ext not in settings.ALLOWED_DP_EXTENSIONS:
        raise ValueError(f"Invalid file type. Allowed: {', '.join(settings.ALLOWED_DP_EXTENSIONS)}")

    contents = await file.read()
    file_size = len(contents)


    if file_size > settings.MAX_DP_FILE_SIZE:
        raise ValueError(f"File too large. Maximum size: {settings.MAX_DP_FILE_SIZE / (1024 * 1024):.1f}MB")

    updated_dir_path = settings.UPLOAD_DIR_DP / folder_name
    updated_dir_path.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_id = str(uuid.uuid4())[:8]
    clean_username = re.sub(r'[^a-zA-Z0-9]', '_', username.lower())
    filename = f"teacher_{clean_username}_{timestamp}_{unique_id}{file_ext}"
    filepath = updated_dir_path / filename

    try:
        # Save temporary file
        temp_path = updated_dir_path / f"temp_{filename}"
        with open(temp_path, "wb") as f:
            f.write(contents)

        # Open and process image
        with Image.open(temp_path) as img:
            # Convert RGBA to RGB if necessary
            if img.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                img = background

            # Resize if too large (maintain aspect ratio)
            if img.width > settings.IMAGE_MAX_WIDTH or img.height > settings.IMAGE_MAX_HEIGHT:
                img.thumbnail((settings.IMAGE_MAX_WIDTH, settings.IMAGE_MAX_HEIGHT), Image.Resampling.LANCZOS)

            # Save optimized image
            img.save(filepath, quality=85, optimize=True)

        # Remove temporary file
        os.remove(temp_path)

        return filename

    except Exception as e:
        # Clean up on error
        if temp_path.exists():
            os.remove(temp_path)
        if filepath.exists():
            os.remove(filepath)
        raise ValueError(f"Failed to process image: {str(e)}")