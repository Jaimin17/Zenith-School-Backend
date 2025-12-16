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
                if img.mode in ('RGBA', 'LA'):
                    background.paste(img, mask=img.split()[-1])
                else:
                    background.paste(img)
                img = background

            # Resize if too large (maintain aspect ratio)
            max_width = settings.IMAGE_MAX_WIDTH
            max_height = settings.IMAGE_MAX_HEIGHT

            if img.width > max_width or img.height > max_height:
                img.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)

            # Save optimized image
            img.save(filepath, quality=85, optimize=True)

        # Remove temporary file
        temp_path.unlink(missing_ok=True)

        return filename

    except Exception as e:
        cleanup_image(temp_path)
        cleanup_image(filepath)
        raise ValueError(f"Failed to process image: {str(e)}")


def cleanup_image(filepath: Path) -> None:
    """Safely delete an image file."""
    try:
        if filepath.exists():
            filepath.unlink()
    except Exception:
        pass



async def process_and_save_pdf(file: UploadFile, folder_name: str, assignment_title: str) -> str:
    file_ext = Path(file.filename).suffix.lower()

    if file_ext not in settings.ALLOWED_PDF_EXTENSIONS:
        raise ValueError(f"Invalid file type. Only PDF files are allowed.")

    contents = await file.read()
    file_size = len(contents)

    # Validate file size
    if file_size > settings.MAX_PDF_FILE_SIZE:
        raise ValueError(f"File too large. Maximum size: {settings.MAX_PDF_FILE_SIZE / (1024 * 1024):.1f}MB")

    # Validate it's actually a PDF by checking magic bytes
    if not contents.startswith(b'%PDF'):
        raise ValueError("File is not a valid PDF document.")

    # Create upload directory
    upload_dir_path = settings.UPLOAD_DIR_PDF / folder_name
    upload_dir_path.mkdir(parents=True, exist_ok=True)

    # Generate unique filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_id = str(uuid.uuid4())[:8]
    clean_title = re.sub(r'[^a-zA-Z0-9]', '_', assignment_title.lower())[:50]  # Limit title length
    filename = f"assignment_{clean_title}_{timestamp}_{unique_id}{file_ext}"
    filepath = upload_dir_path / filename

    try:
        # Save PDF directly without processing
        with open(filepath, "wb") as f:
            f.write(contents)

        return filename

    except Exception as e:
        # Clean up file if save failed
        if filepath.exists():
            filepath.unlink(missing_ok=True)
        raise ValueError(f"Failed to save PDF: {str(e)}")


def cleanup_pdf(filepath: Path) -> None:
    """Safely delete a PDF file."""
    try:
        if filepath and filepath.exists():
            filepath.unlink()
    except Exception:
        pass