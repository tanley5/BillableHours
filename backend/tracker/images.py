from io import BytesIO

from django.conf import settings
from django.core.files.base import ContentFile
from PIL import Image, UnidentifiedImageError
from rest_framework.exceptions import ValidationError


def process_uploaded_image(uploaded_file) -> ContentFile:
    """Validate and resize an uploaded image. Returns a JPEG ContentFile."""
    try:
        image = Image.open(uploaded_file)
        image.verify()
        uploaded_file.seek(0)
        image = Image.open(uploaded_file)
        image.load()
    except (UnidentifiedImageError, OSError) as exc:
        raise ValidationError({"file": "Invalid image file."}) from exc

    image = image.convert("RGB")
    max_dim = settings.PHOTO_MAX_DIMENSION
    image.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)

    buffer = BytesIO()
    image.save(buffer, format="JPEG", quality=85, optimize=True)
    name = getattr(uploaded_file, "name", "photo.jpg")
    if "." in name:
        name = name.rsplit(".", 1)[0] + ".jpg"
    else:
        name = name + ".jpg"
    return ContentFile(buffer.getvalue(), name=name)
