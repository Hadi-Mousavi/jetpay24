"""
Shared upload validation for all order attachment paths.

Used by:
  - AttachmentForm (order detail attach)
  - views.order_create (multi-file creation-time attachments)
  - views.order_send_message (message attachments)
"""

import mimetypes

from django.core.exceptions import ValidationError

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB

ALLOWED_EXTENSIONS = frozenset({
    'pdf',
    'jpg', 'jpeg', 'png',
    'doc', 'docx',
    'xls', 'xlsx',
    'zip',
})

# Blocked unconditionally regardless of ALLOWED_EXTENSIONS overlap.
BLOCKED_EXTENSIONS = frozenset({
    'exe', 'msi', 'bat', 'cmd', 'com', 'scr', 'pif', 'vbs', 'vbe',
    'js', 'jse', 'wsf', 'wsh', 'ps1', 'ps2',
    'html', 'htm', 'xhtml',
    'svg',
    'php', 'php3', 'php4', 'php5', 'phtml',
    'sh', 'bash', 'zsh', 'csh',
    'py', 'rb', 'pl', 'lua',
    'dll', 'so', 'dylib',
    'jar', 'class',
})

# Extension → expected MIME prefixes. Only checked when the OS resolves the MIME.
# This prevents e.g. a renamed .exe saved as .pdf from passing silently
# in environments where mimetypes has good coverage.
_EXPECTED_MIME_PREFIX = {
    'pdf':  'application/pdf',
    'jpg':  'image/jpeg',
    'jpeg': 'image/jpeg',
    'png':  'image/png',
    'doc':  'application/msword',
    'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml',
    'xls':  'application/vnd.ms-excel',
    'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml',
    'zip':  ('application/zip', 'application/x-zip', 'application/octet-stream'),
}


def validate_upload(upload_file):
    """
    Validate extension, MIME type (best-effort), and size of an uploaded file.
    Raises django.core.exceptions.ValidationError with Persian messages on failure.
    Does nothing if upload_file is None or empty.
    """
    if not upload_file:
        return

    name = upload_file.name or ''
    ext  = name.rsplit('.', 1)[-1].lower() if '.' in name else ''

    # 1. Blocked extension
    if ext in BLOCKED_EXTENSIONS:
        raise ValidationError(
            f'بارگذاری فایل‌های اجرایی یا اسکریپت مجاز نیست. (.{ext})'
        )

    # 2. Must be in allow-list
    if ext not in ALLOWED_EXTENSIONS:
        allowed_display = '، '.join(sorted(ALLOWED_EXTENSIONS))
        raise ValidationError(
            f'فرمت فایل مجاز نیست. فرمت‌های پذیرفته‌شده: {allowed_display}'
        )

    # 3. Size limit
    if hasattr(upload_file, 'size') and upload_file.size > MAX_UPLOAD_BYTES:
        mb = upload_file.size / (1024 * 1024)
        raise ValidationError(
            f'حجم فایل ({mb:.1f} MB) از حداکثر مجاز ۱۰ مگابایت بیشتر است.'
        )

    # 4. MIME plausibility (best-effort; mimetypes uses filename, not content)
    guessed_mime, _ = mimetypes.guess_type(name)
    if guessed_mime and ext in _EXPECTED_MIME_PREFIX:
        expected = _EXPECTED_MIME_PREFIX[ext]
        if isinstance(expected, str):
            expected = (expected,)
        if not any(guessed_mime.startswith(e) for e in expected):
            raise ValidationError(
                'نوع فایل با پسوند آن مطابقت ندارد. لطفاً فایل را بررسی کنید.'
            )
