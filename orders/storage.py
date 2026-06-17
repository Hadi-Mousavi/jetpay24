"""
Private file storage backend for order attachments.

Security model
--------------
Files are stored at settings.PRIVATE_MEDIA_ROOT, which is a directory
that is OUTSIDE settings.MEDIA_ROOT and therefore NEVER served by:
  - Django's static() dev helper (which only serves MEDIA_ROOT)
  - Any correctly configured nginx/Apache server

The only way to read a stored file is through the authenticated views:
  - orders.views.order_attachment_download
  - orders.views.message_attachment_download

Both views enforce:
  - @login_required
  - object-level ownership check (customer owns order, or is_staff)
  - FileResponse(file.open('rb'), as_attachment=True)

base_url=None means calling .url on a FieldFile raises ValueError —
there is no public URL to expose even by accident.

Test compatibility
------------------
`location` is a Python property that reads settings.PRIVATE_MEDIA_ROOT
on every call.  This means @override_settings(PRIVATE_MEDIA_ROOT=...)
works correctly in unit tests without module-level side effects.
"""

import os

from django.core.files.storage import FileSystemStorage, Storage


class PrivateFileSystemStorage(FileSystemStorage):
    """
    File storage for sensitive order attachment files.

    Key behaviours:
      1. location  → settings.PRIVATE_MEDIA_ROOT (resolved lazily at call time)
      2. base_url  → None  (calling .url raises ValueError — no public URL)
      3. deconstruct() returns no path arguments so migrations are portable
         across machines and environments.
      4. The PRIVATE_MEDIA_ROOT directory is created automatically on first use.
    """

    def __init__(self):
        # Skip FileSystemStorage.__init__ to avoid reading settings at
        # import / module-load time.  All path resolution is deferred to the
        # location property below, keeping override_settings working in tests.
        Storage.__init__(self)
        self.base_url = None
        self.file_permissions_mode = None
        self.directory_permissions_mode = None

    # ------------------------------------------------------------------
    # location — resolved lazily from settings on every access
    # ------------------------------------------------------------------

    @property
    def location(self):
        from django.conf import settings
        path = str(settings.PRIVATE_MEDIA_ROOT)
        os.makedirs(path, exist_ok=True)
        return path

    @location.setter
    def location(self, value):
        # Intentionally ignored — we always derive location from settings.
        pass

    # ------------------------------------------------------------------
    # Migration serialization
    # ------------------------------------------------------------------

    def deconstruct(self):
        # Return only the dotted import path, no args, no kwargs.
        # This prevents hardcoded filesystem paths inside migration files.
        return ('orders.storage.PrivateFileSystemStorage', [], {})
