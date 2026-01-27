import qrcode
import io
import os
from django.core.files.base import ContentFile
from django.conf import settings


def generate_qr_code(visitor):
    """Generate QR code for visitor"""

    # Create QR code data
    qr_data = {
        "id": str(visitor.id),
        "name": visitor.name,
        "email": visitor.email,
        "qr_code": visitor.qr_code,
        "visit_date": str(visitor.visit_date),
        "visit_time": str(visitor.visit_time),
    }

    # Generate QR code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(str(qr_data))
    qr.make(fit=True)

    # Create QR code image
    img = qr.make_image(fill_color="black", back_color="white")

    # Save to BytesIO
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)

    # Create Django file
    filename = f"qr_{visitor.qr_code}.png"
    qr_file = ContentFile(buffer.read(), name=filename)

    return qr_file
