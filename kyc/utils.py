"""
KYC-specific upload validation.

Allowed formats: JPG, JPEG, PNG — max 10 MB — magic bytes verified.

Follows the same layered approach as orders/utils.py but restricted to
the image types required for identity and bank-card documents.
"""
import filetype
from django.core.exceptions import ValidationError

MAX_KYC_IMAGE_BYTES = 10 * 1024 * 1024   # 10 MB
_MAGIC_READ_BYTES   = 261                  # enough for filetype detection

_ALLOWED_EXTENSIONS = frozenset({'jpg', 'jpeg', 'png'})
_ALLOWED_MIMES      = frozenset({'image/jpeg', 'image/png'})


def validate_kyc_image(upload_file):
    """
    Validate a KYC image upload:
      1. Extension must be jpg / jpeg / png
      2. Size ≤ 10 MB
      3. Magic bytes must confirm JPEG or PNG content

    Raises ``django.core.exceptions.ValidationError`` with Persian messages
    on failure.  Does nothing if *upload_file* is falsy.

    The file read pointer is reset to 0 after the magic-bytes read so the
    storage backend always receives the complete file.
    """
    if not upload_file:
        return

    name = upload_file.name or ''
    ext  = name.rsplit('.', 1)[-1].lower() if '.' in name else ''

    # 1. Extension check
    if ext not in _ALLOWED_EXTENSIONS:
        raise ValidationError('فقط فرمت‌های JPG، JPEG و PNG مجاز هستند.')

    # 2. Size check
    if hasattr(upload_file, 'size') and upload_file.size > MAX_KYC_IMAGE_BYTES:
        mb = upload_file.size / (1024 * 1024)
        raise ValidationError(
            f'حجم فایل ({mb:.1f} MB) از حداکثر مجاز ۱۰ مگابایت بیشتر است.'
        )

    # 3. Magic bytes check
    upload_file.seek(0)
    header = upload_file.read(_MAGIC_READ_BYTES)
    upload_file.seek(0)

    detected_mime = filetype.guess_mime(header)
    if not detected_mime or detected_mime not in _ALLOWED_MIMES:
        raise ValidationError(
            'محتوای فایل با نوع تصویر مطابقت ندارد. '
            'فایل ممکن است تغییر نام داده‌شده یا خراب باشد.'
        )
