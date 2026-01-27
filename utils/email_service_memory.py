#!/usr/bin/env python
"""
Memory-based Email Service for Visitor QR Codes
Generates QR codes and PDFs in memory without saving to local files
Enhanced with SMTP rate limiting for bulk operations
"""
import io
import base64
import time
import threading
from collections import defaultdict
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from django.utils.html import strip_tags
import qrcode
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Image,
    Table,
    TableStyle,
)
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from PIL import Image as PILImage, ImageDraw, ImageFont


# SMTP Rate Limiting Configuration
class EmailRateLimiter:
    """Rate limiter for SMTP email sending to prevent overwhelming the email server"""

    def __init__(self, max_emails_per_minute=10, max_emails_per_hour=100):
        self.max_emails_per_minute = max_emails_per_minute
        self.max_emails_per_hour = max_emails_per_hour
        self.minute_emails = []
        self.hour_emails = []
        self.lock = threading.Lock()

    def can_send_email(self):
        """Check if we can send an email based on rate limits"""
        with self.lock:
            current_time = time.time()

            # Clean old entries
            self.minute_emails = [
                t for t in self.minute_emails if current_time - t < 60
            ]
            self.hour_emails = [t for t in self.hour_emails if current_time - t < 3600]

            # Check limits
            if len(self.minute_emails) >= self.max_emails_per_minute:
                return False, "Minute rate limit exceeded"
            if len(self.hour_emails) >= self.max_emails_per_hour:
                return False, "Hourly rate limit exceeded"

            return True, "OK"

    def record_email_sent(self):
        """Record that an email was sent"""
        with self.lock:
            current_time = time.time()
            self.minute_emails.append(current_time)
            self.hour_emails.append(current_time)

    def get_wait_time(self):
        """Get the time to wait before next email can be sent"""
        with self.lock:
            current_time = time.time()

            # Check minute limit
            if len(self.minute_emails) >= self.max_emails_per_minute:
                oldest_minute = min(self.minute_emails)
                wait_time = 60 - (current_time - oldest_minute)
                return max(0, wait_time)

            # Check hour limit
            if len(self.hour_emails) >= self.max_emails_per_hour:
                oldest_hour = min(self.hour_emails)
                wait_time = 3600 - (current_time - oldest_hour)
                return max(0, wait_time)

            return 0


# Global rate limiter instance
email_rate_limiter = EmailRateLimiter(max_emails_per_minute=10, max_emails_per_hour=100)


def send_email_with_rate_limiting(
    subject, text_content, from_email, to_emails, html_content=None, attachments=None
):
    """Send email with rate limiting"""
    try:
        # Check rate limit
        can_send, message = email_rate_limiter.can_send_email()

        if not can_send:
            wait_time = email_rate_limiter.get_wait_time()
            print(
                f"⏳ Rate limit reached: {message}. Waiting {wait_time:.1f} seconds..."
            )
            time.sleep(wait_time)

        # Create email
        msg = EmailMultiAlternatives(subject, text_content, from_email, to_emails)

        if html_content:
            msg.attach_alternative(html_content, "text/html")

        if attachments:
            for attachment in attachments:
                msg.attach(*attachment)

        # Send email
        msg.send()

        # Record the email was sent
        email_rate_limiter.record_email_sent()

        print(f"✅ Email sent successfully to {', '.join(to_emails)}")
        return True

    except Exception as e:
        print(f"❌ Failed to send email: {str(e)}")
        return False


def send_bulk_emails_with_rate_limiting(emails_data, delay_between_emails=1.0):
    """Send multiple emails with rate limiting and delays"""
    results = {"successful": [], "failed": [], "total_processed": 0, "rate_limited": 0}

    for i, email_data in enumerate(emails_data):
        try:
            # Check rate limit before each email
            can_send, message = email_rate_limiter.can_send_email()

            if not can_send:
                wait_time = email_rate_limiter.get_wait_time()
                print(
                    f"⏳ Rate limit reached for email {i+1}/{len(emails_data)}: {message}"
                )
                print(f"⏳ Waiting {wait_time:.1f} seconds before continuing...")
                time.sleep(wait_time)
                results["rate_limited"] += 1

            # Send email
            success = send_email_with_rate_limiting(
                subject=email_data["subject"],
                text_content=email_data["text_content"],
                from_email=email_data["from_email"],
                to_emails=email_data["to_emails"],
                html_content=email_data.get("html_content"),
                attachments=email_data.get("attachments", []),
            )

            if success:
                results["successful"].append(
                    {
                        "index": i,
                        "to": email_data["to_emails"],
                        "subject": email_data["subject"],
                    }
                )
            else:
                results["failed"].append(
                    {
                        "index": i,
                        "to": email_data["to_emails"],
                        "subject": email_data["subject"],
                        "error": "Email sending failed",
                    }
                )

            results["total_processed"] += 1

            # Add delay between emails to be respectful to SMTP server
            if i < len(emails_data) - 1:  # Don't delay after the last email
                time.sleep(delay_between_emails)

        except Exception as e:
            results["failed"].append(
                {
                    "index": i,
                    "to": email_data.get("to_emails", ["unknown"]),
                    "subject": email_data.get("subject", "unknown"),
                    "error": str(e),
                }
            )
            results["total_processed"] += 1

    return results


def generate_qr_code_in_memory(visitor):
    """Generate QR code image in memory"""
    try:
        # Create QR code data
        qr_data = {
            "visitor_id": str(visitor.id),
            "name": visitor.name,
            "email": visitor.email,
            "visit_date": str(visitor.visit_date),
            "visit_time": str(visitor.visit_time),
            "purpose": visitor.get_purpose_display(),
            "qr_code": visitor.qr_code,
        }

        # Create QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(str(qr_data))
        qr.make(fit=True)

        # Create QR code image
        qr_image = qr.make_image(fill_color="black", back_color="white")

        # Convert to bytes
        img_buffer = io.BytesIO()
        qr_image.save(img_buffer, format="PNG")
        img_buffer.seek(0)

        return img_buffer.getvalue()

    except Exception as e:
        print(f"❌ QR code generation failed: {str(e)}")
        return None


def generate_enhanced_qr_image_in_memory(visitor, qr_bytes):
    """Generate enhanced QR image with visitor details in memory"""
    try:
        # Load QR code image
        qr_img = PILImage.open(io.BytesIO(qr_bytes))

        # Create a larger canvas
        canvas_width = max(400, qr_img.width + 100)
        canvas_height = qr_img.height + 150

        # Create new image with white background
        canvas = PILImage.new("RGB", (canvas_width, canvas_height), "white")

        # Paste QR code in center
        qr_x = (canvas_width - qr_img.width) // 2
        qr_y = 50
        canvas.paste(qr_img, (qr_x, qr_y))

        # Add text
        draw = ImageDraw.Draw(canvas)

        # Try to use a nice font, fallback to default
        try:
            font_large = ImageFont.truetype("arial.ttf", 20)
            font_small = ImageFont.truetype("arial.ttf", 14)
        except:
            font_large = ImageFont.load_default()
            font_small = ImageFont.load_default()

        # Add visitor name
        name_text = f"Visitor: {visitor.name}"
        name_bbox = draw.textbbox((0, 0), name_text, font=font_large)
        name_width = name_bbox[2] - name_bbox[0]
        name_x = (canvas_width - name_width) // 2
        draw.text(
            (name_x, qr_y + qr_img.height + 20),
            name_text,
            fill="black",
            font=font_large,
        )

        # Add QR code text
        qr_text = f"QR Code: {visitor.qr_code}"
        qr_bbox = draw.textbbox((0, 0), qr_text, font=font_small)
        qr_text_width = qr_bbox[2] - qr_bbox[0]
        qr_text_x = (canvas_width - qr_text_width) // 2
        draw.text(
            (qr_text_x, qr_y + qr_img.height + 50),
            qr_text,
            fill="gray",
            font=font_small,
        )

        # Add date
        date_text = f"Date: {visitor.visit_date}"
        date_bbox = draw.textbbox((0, 0), date_text, font=font_small)
        date_width = date_bbox[2] - date_bbox[0]
        date_x = (canvas_width - date_width) // 2
        draw.text(
            (date_x, qr_y + qr_img.height + 70), date_text, fill="gray", font=font_small
        )

        # Convert to bytes
        img_buffer = io.BytesIO()
        canvas.save(img_buffer, format="PNG")
        img_buffer.seek(0)

        return img_buffer.getvalue()

    except Exception as e:
        print(f"❌ Enhanced QR image generation failed: {str(e)}")
        return None


def generate_pdf_in_memory(visitor, qr_bytes):
    """Generate PDF with visitor details and QR code in memory"""
    try:
        # Create PDF in memory
        pdf_buffer = io.BytesIO()

        # Create PDF document
        doc = SimpleDocTemplate(pdf_buffer, pagesize=A4)
        story = []

        # Get styles
        styles = getSampleStyleSheet()

        # Custom styles
        title_style = ParagraphStyle(
            "CustomTitle",
            parent=styles["Heading1"],
            fontSize=24,
            spaceAfter=30,
            alignment=TA_CENTER,
            textColor=colors.darkblue,
        )

        heading_style = ParagraphStyle(
            "CustomHeading",
            parent=styles["Heading2"],
            fontSize=16,
            spaceAfter=12,
            textColor=colors.darkblue,
        )

        normal_style = ParagraphStyle(
            "CustomNormal", parent=styles["Normal"], fontSize=12, spaceAfter=6
        )

        # Title
        story.append(Paragraph("Visitor Management System", title_style))
        story.append(Paragraph("Visit Confirmation", heading_style))
        story.append(Spacer(1, 20))

        # Visitor Details Table
        visitor_data = [
            ["Name:", visitor.name],
            ["Email:", visitor.email],
            ["Phone:", visitor.phone],
            ["Visit Date:", str(visitor.visit_date)],
            ["Visit Time:", str(visitor.visit_time)],
            ["Purpose:", visitor.get_purpose_display()],
        ]

        if visitor.host_name:
            visitor_data.append(["Host:", visitor.host_name])

        visitor_data.append(["QR Code:", visitor.qr_code])

        # Create table
        visitor_table = Table(visitor_data, colWidths=[2 * inch, 4 * inch])
        visitor_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (0, -1), colors.lightgrey),
                    ("TEXTCOLOR", (0, 0), (-1, -1), colors.black),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                    ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 0), (-1, -1), 12),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
                    ("BACKGROUND", (1, 0), (1, -1), colors.beige),
                    ("GRID", (0, 0), (-1, -1), 1, colors.black),
                ]
            )
        )

        story.append(visitor_table)
        story.append(Spacer(1, 30))

        # QR Code Section
        story.append(Paragraph("Your QR Code", heading_style))
        story.append(Spacer(1, 10))

        # Add QR code image
        if qr_bytes:
            qr_img = Image(io.BytesIO(qr_bytes), width=2 * inch, height=2 * inch)
            qr_img.hAlign = "CENTER"
            story.append(qr_img)
            story.append(Spacer(1, 10))

        # QR Code text
        story.append(Paragraph(f"<b>QR Code:</b> {visitor.qr_code}", normal_style))
        story.append(Spacer(1, 20))

        # Instructions
        story.append(Paragraph("Important Instructions", heading_style))
        instructions = [
            "• Please arrive 10 minutes before your scheduled time",
            "• Present this QR code at the reception for quick verification",
            "• Bring a valid photo ID",
            "• Contact your host if you need to reschedule",
            "• Keep this document safe for your visit",
        ]

        for instruction in instructions:
            story.append(Paragraph(instruction, normal_style))

        story.append(Spacer(1, 20))

        # Footer
        story.append(
            Paragraph(
                "Thank you for visiting us!",
                ParagraphStyle(
                    "Footer",
                    parent=styles["Normal"],
                    fontSize=14,
                    alignment=TA_CENTER,
                    textColor=colors.darkblue,
                ),
            )
        )

        # Build PDF
        doc.build(story)
        pdf_buffer.seek(0)

        return pdf_buffer.getvalue()

    except Exception as e:
        print(f"❌ PDF generation failed: {str(e)}")
        return None


def send_visitor_confirmation_memory_only(visitor):
    """Send visitor confirmation email with all attachments generated in memory"""
    try:
        subject = f"Visit Confirmation - {visitor.name}"

        # Generate QR code in memory
        print("🔄 Generating QR code in memory...")
        qr_bytes = generate_qr_code_in_memory(visitor)

        if not qr_bytes:
            print("❌ Failed to generate QR code")
            return f"Failed to generate QR code for {visitor.email}"

        # Convert QR code to base64 for email embedding
        qr_image_base64 = base64.b64encode(qr_bytes).decode("utf-8")

        # Generate enhanced QR image in memory
        print("🔄 Generating enhanced QR image in memory...")
        enhanced_qr_bytes = generate_enhanced_qr_image_in_memory(visitor, qr_bytes)

        # Generate PDF in memory
        print("🔄 Generating PDF in memory...")
        pdf_bytes = generate_pdf_in_memory(visitor, qr_bytes)

        # Enhanced HTML email template with modern UI
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Visit Confirmation - {visitor.name}</title>
            <style>
                * {{ margin: 0; padding: 0; box-sizing: border-box; }}
                body {{ 
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
                    line-height: 1.6; 
                    background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
                    margin: 0;
                    padding: 20px;
                }}
                .email-container {{ 
                    max-width: 650px; 
                    margin: 0 auto; 
                    background: white;
                    border-radius: 20px;
                    overflow: hidden;
                    box-shadow: 0 20px 40px rgba(0,0,0,0.1);
                }}
                .header {{ 
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                    color: white; 
                    padding: 40px 30px; 
                    text-align: center; 
                    position: relative;
                    overflow: hidden;
                }}
                .header::before {{
                    content: '';
                    position: absolute;
                    top: -50%;
                    left: -50%;
                    width: 200%;
                    height: 200%;
                    background: radial-gradient(circle, rgba(255,255,255,0.1) 0%, transparent 70%);
                    animation: float 6s ease-in-out infinite;
                }}
                @keyframes float {{
                    0%, 100% {{ transform: translateY(0px) rotate(0deg); }}
                    50% {{ transform: translateY(-20px) rotate(180deg); }}
                }}
                .header-content {{ position: relative; z-index: 1; }}
                .header h1 {{ 
                    font-size: 2.5em; 
                    margin-bottom: 10px; 
                    font-weight: 700;
                    text-shadow: 0 2px 4px rgba(0,0,0,0.3);
                }}
                .header p {{ 
                    font-size: 1.2em; 
                    opacity: 0.9;
                    font-weight: 300;
                }}
                .content {{ 
                    padding: 40px 30px; 
                    background: #fafbfc;
                }}
                .info-card {{ 
                    background: white; 
                    padding: 30px; 
                    border-radius: 16px; 
                    margin: 25px 0; 
                    box-shadow: 0 8px 25px rgba(0,0,0,0.08);
                    border: 1px solid #e8ecf0;
                    transition: transform 0.3s ease;
                }}
                .info-card:hover {{ transform: translateY(-2px); }}
                .info-card h2 {{ 
                    color: #2d3748; 
                    font-size: 1.5em; 
                    margin-bottom: 20px; 
                    display: flex;
                    align-items: center;
                    gap: 10px;
                }}
                .info-grid {{ 
                    display: grid; 
                    grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); 
                    gap: 15px; 
                }}
                .info-item {{ 
                    display: flex; 
                    justify-content: space-between; 
                    padding: 12px 0; 
                    border-bottom: 1px solid #f1f5f9;
                }}
                .info-item:last-child {{ border-bottom: none; }}
                .info-label {{ 
                    font-weight: 600; 
                    color: #4a5568; 
                    min-width: 120px;
                }}
                .info-value {{ 
                    color: #2d3748; 
                    font-weight: 500;
                }}
                .qr-section {{ 
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                    padding: 40px 30px; 
                    border-radius: 16px; 
                    margin: 25px 0; 
                    text-align: center;
                    color: white;
                    position: relative;
                    overflow: hidden;
                }}
                .qr-section::before {{
                    content: '';
                    position: absolute;
                    top: -50%;
                    right: -50%;
                    width: 200%;
                    height: 200%;
                    background: radial-gradient(circle, rgba(255,255,255,0.1) 0%, transparent 70%);
                    animation: float 8s ease-in-out infinite reverse;
                }}
                .qr-content {{ position: relative; z-index: 1; }}
                .qr-section h3 {{ 
                    font-size: 1.8em; 
                    margin-bottom: 25px; 
                    font-weight: 700;
                    text-shadow: 0 2px 4px rgba(0,0,0,0.3);
                }}
                .qr-code-display {{ 
                    background: rgba(255,255,255,0.15); 
                    backdrop-filter: blur(10px);
                    padding: 25px; 
                    border-radius: 12px; 
                    margin: 20px 0;
                    border: 1px solid rgba(255,255,255,0.2);
                }}
                .qr-text {{ 
                    font-size: 2em; 
                    font-weight: 700; 
                    margin: 15px 0; 
                    font-family: 'Courier New', monospace; 
                    background: rgba(255,255,255,0.2); 
                    padding: 15px 25px; 
                    border-radius: 8px; 
                    display: inline-block; 
                    border: 2px solid rgba(255,255,255,0.3);
                    letter-spacing: 2px;
                }}
                .qr-instruction {{ 
                    font-size: 1.1em; 
                    margin: 15px 0; 
                    opacity: 0.9;
                }}
                .attachments {{ 
                    background: rgba(255,255,255,0.1); 
                    padding: 20px; 
                    border-radius: 12px; 
                    margin: 20px 0;
                    border: 1px solid rgba(255,255,255,0.2);
                }}
                .attachments h4 {{ 
                    margin: 0 0 15px 0; 
                    font-size: 1.2em;
                    display: flex;
                    align-items: center;
                    gap: 8px;
                }}
                .attachments ul {{ 
                    margin: 0; 
                    padding-left: 20px; 
                    list-style: none;
                }}
                .attachments li {{ 
                    margin: 8px 0; 
                    padding-left: 20px;
                    position: relative;
                }}
                .attachments li::before {{
                    content: '✓';
                    position: absolute;
                    left: 0;
                    color: #4ade80;
                    font-weight: bold;
                }}
                .instructions {{ 
                    background: white; 
                    padding: 30px; 
                    border-radius: 16px; 
                    margin: 25px 0; 
                    box-shadow: 0 8px 25px rgba(0,0,0,0.08);
                    border-left: 5px solid #667eea;
                }}
                .instructions h3 {{ 
                    color: #2d3748; 
                    font-size: 1.4em; 
                    margin-bottom: 20px;
                    display: flex;
                    align-items: center;
                    gap: 10px;
                }}
                .instructions ul {{ 
                    list-style: none; 
                    padding: 0;
                }}
                .instructions li {{ 
                    margin: 12px 0; 
                    padding: 12px 0 12px 30px; 
                    position: relative;
                    border-bottom: 1px solid #f1f5f9;
                }}
                .instructions li:last-child {{ border-bottom: none; }}
                .instructions li::before {{
                    content: '→';
                    position: absolute;
                    left: 0;
                    color: #667eea;
                    font-weight: bold;
                    font-size: 1.2em;
                }}
                .highlight {{ 
                    background: linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%); 
                    padding: 25px; 
                    border-radius: 16px; 
                    margin: 25px 0; 
                    border-left: 5px solid #2196f3;
                    box-shadow: 0 8px 25px rgba(33, 150, 243, 0.1);
                }}
                .highlight h3 {{ 
                    color: #1976d2; 
                    font-size: 1.3em; 
                    margin-bottom: 15px;
                    display: flex;
                    align-items: center;
                    gap: 10px;
                }}
                .highlight p {{ 
                    margin: 10px 0; 
                    color: #1565c0;
                    font-weight: 500;
                }}
                .footer {{ 
                    text-align: center; 
                    margin-top: 40px; 
                    padding: 30px;
                    background: #f8fafc;
                    color: #64748b;
                    border-top: 1px solid #e2e8f0;
                }}
                .footer p {{ margin: 8px 0; }}
                .footer small {{ 
                    font-size: 0.9em; 
                    opacity: 0.8;
                }}
                .badge {{
                    display: inline-block;
                    padding: 4px 12px;
                    background: #667eea;
                    color: white;
                    border-radius: 20px;
                    font-size: 0.8em;
                    font-weight: 600;
                    margin-left: 8px;
                }}
                @media (max-width: 600px) {{
                    .email-container {{ margin: 10px; border-radius: 15px; }}
                    .header, .content {{ padding: 20px; }}
                    .info-grid {{ grid-template-columns: 1fr; }}
                    .qr-text {{ font-size: 1.5em; }}
                    .header h1 {{ font-size: 2em; }}
                }}
            </style>
        </head>
        <body>
            <div class="email-container">
                <div class="header">
                    <div class="header-content">
                        <h1>🎉 Visit Confirmed!</h1>
                        <p>Your visit has been successfully registered with C4i4 Lab</p>
                    </div>
                </div>
                
                <div class="content">
                    <div class="info-card">
                        <h2>👤 Visitor Information</h2>
                        <div class="info-grid">
                            <div class="info-item">
                                <span class="info-label">Name:</span>
                                <span class="info-value">{visitor.name}</span>
                            </div>
                            <div class="info-item">
                                <span class="info-label">Email:</span>
                                <span class="info-value">{visitor.email}</span>
                            </div>
                            <div class="info-item">
                                <span class="info-label">Phone:</span>
                                <span class="info-value">{visitor.phone}</span>
                            </div>
                            <div class="info-item">
                                <span class="info-label">Date:</span>
                                <span class="info-value">{visitor.visit_date}</span>
                            </div>
                            <div class="info-item">
                                <span class="info-label">Time:</span>
                                <span class="info-value">{visitor.visit_time}</span>
                            </div>
                            <div class="info-item">
                                <span class="info-label">Purpose:</span>
                                <span class="info-value">{visitor.get_purpose_display()}</span>
                            </div>
                           
                            {f'<div class="info-item"><span class="info-label">Host:</span><span class="info-value">{visitor.host_name}</span></div>' if visitor.host_name else ''}
                        </div>
                    </div>
                    
                    <div class="qr-section">
                        <div class="qr-content">
                        <h3>📱 Your QR Code</h3>
                            <div class="qr-code-display">
                                <div class="qr-text">{visitor.qr_code}</div>
                                <div class="qr-instruction">Present this QR code upon arrival for quick verification</div>
                            </div>
                            <div class="attachments">
                                <h4>📎 Downloadable Attachments</h4>
                                <ul>
                                    <li><strong>PDF Document:</strong> Complete visitor confirmation with QR code</li>
                                    <li><strong>QR Code Image:</strong> QR code with visitor details for easy access</li>
                                </ul>
                                <p style="margin: 15px 0 0 0; font-size: 0.9em; opacity: 0.8;">
                                    💡 <strong>Tip:</strong> Download the PDF for printing or save the QR code image to your phone for easy access during verification.
                                </p>
                            </div>
                        </div>
                    </div>
                    
                    <div class="instructions">
                        <h3>📋 Important Instructions</h3>
                        <ul>
                            <li>Please arrive 10 minutes before your scheduled time</li>
                            <li>Present your QR code at the reception for quick verification</li>
                            <li>Bring a valid photo ID for security purposes</li>
                            <li>Contact your host if you need to reschedule your visit</li>
                            <li>Follow all safety protocols and building guidelines</li>
                        </ul>
                    </div>
                    
                    <div class="highlight">
                        <h3>🔔 What's Next?</h3>
                        <p>1. <strong>Save this email</strong> - Keep it handy for your visit</p>
                        <p>2. <strong>Download attachments</strong> - PDF and images for offline access</p>
                        <p>3. <strong>Show QR code</strong> - At reception for quick check-in</p>
                        <p>4. <strong>Enjoy your visit</strong> - We look forward to seeing you!</p>
                    </div>
                </div>
                
                <div class="footer">
                    <p><strong>Thank you for choosing C4i4 Lab Visitor Management System!</strong></p>
                    <p>Centre for Industry 4.0 - Innovation & Excellence</p>
                    <p><small>This is an automated message. Please do not reply to this email.</small></p>
                </div>
            </div>
        </body>
        </html>
        """

        # Plain text version
        text_content = f"""
        Visit Confirmation - {visitor.name}
        =====================================
        
        Dear {visitor.name},
        
        Your visit has been successfully registered! Here are your visit details:
        
        Visitor Information:
        - Name: {visitor.name}
        - Email: {visitor.email}
        - Phone: {visitor.phone}
        - Date: {visitor.visit_date}
        - Time: {visitor.visit_time}
        - Purpose: {visitor.get_purpose_display()}
        {f'- Host: {visitor.host_name}' if visitor.host_name else ''}
        
        Your QR Code: {visitor.qr_code}
        
        📎 ATTACHMENTS INCLUDED:
        - PDF Document: Complete visitor confirmation with QR code
        - QR Code Image: QR code with visitor details for easy access
        
        💡 TIP: Download the PDF for printing or save the QR code image to your phone for easy access during verification.
        
        Important Instructions:
        - Please arrive 10 minutes before your scheduled time
        - Present your QR code at the reception for quick verification
        - Bring a valid photo ID
        - Contact your host if you need to reschedule
        
        What's Next?
        1. Save this email - Keep it handy for your visit
        2. Download attachments - PDF and images for offline access
        3. Show QR code - At reception for quick check-in
        
        Thank you for choosing our Visitor Management System!
        
        This is an automated message. Please do not reply to this email.
        """

        print(f"=== EMAIL SENT TO: {visitor.email} ===")
        print(f"SUBJECT: {subject}")
        print("HTML Content prepared")
        print("=" * 50)

        # Try to send actual email
        try:
            msg = EmailMultiAlternatives(
                subject, text_content, "testkirantondchore@gmail.com", [visitor.email]
            )
            msg.attach_alternative(html_content, "text/html")

            # Attach only PDF and enhanced QR image (as requested)
            if pdf_bytes:
                msg.attach(
                    f"visitor_confirmation_{visitor.qr_code}.pdf",
                    pdf_bytes,
                    "application/pdf",
                )
                print("✅ Visitor confirmation PDF attached")

            # Attach enhanced QR image if generated successfully
            if enhanced_qr_bytes:
                msg.attach(
                    f"visitor_qr_code_{visitor.qr_code}.png",
                    enhanced_qr_bytes,
                    "image/png",
                )
                print("✅ Enhanced QR code image attached")

            msg.send()
            print("✅ Email sent successfully via SMTP")
        except Exception as smtp_error:
            print(f"⚠️  SMTP error: {smtp_error}")
            print("📧 Email content printed above for manual sending")

        return f"Confirmation email sent to {visitor.email}"

    except Exception as e:
        print(f"Email send failed: {str(e)}")
        return f"Failed to send email to {visitor.email}: {str(e)}"


def send_reschedule_notification(visitor, old_date, old_time, new_date, new_time):
    """Send reschedule notification email to visitor with new QR code and PDF"""
    try:
        # Create email subject and content
        subject = f"Visit Rescheduled - {visitor.name} - New Date: {new_date}"

        # Generate new QR code and PDF for the rescheduled visit
        print("🔄 Generating new QR code and PDF for rescheduled visit...")
        qr_bytes = generate_qr_code_in_memory(visitor)
        enhanced_qr_bytes = generate_enhanced_qr_image_in_memory(visitor, qr_bytes)
        pdf_bytes = generate_pdf_in_memory(visitor, qr_bytes)

        # Convert QR code to base64 for email embedding
        qr_image_base64 = base64.b64encode(qr_bytes).decode("utf-8") if qr_bytes else ""

        # Enhanced HTML content for reschedule notification
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Visit Rescheduled - {visitor.name}</title>
            <style>
                * {{ margin: 0; padding: 0; box-sizing: border-box; }}
                body {{ 
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
                    line-height: 1.6; 
                    background: linear-gradient(135deg, #fef2f2 0%, #fecaca 100%);
                    margin: 0;
                    padding: 20px;
                }}
                .email-container {{ 
                    max-width: 650px; 
                    margin: 0 auto; 
                    background: white;
                    border-radius: 20px;
                    overflow: hidden;
                    box-shadow: 0 20px 40px rgba(220, 38, 38, 0.1);
                }}
                .header {{ 
                    background: linear-gradient(135deg, #dc2626 0%, #b91c1c 100%); 
                    color: white; 
                    padding: 40px 30px; 
                    text-align: center; 
                    position: relative;
                    overflow: hidden;
                }}
                .header::before {{
                    content: '';
                    position: absolute;
                    top: -50%;
                    left: -50%;
                    width: 200%;
                    height: 200%;
                    background: radial-gradient(circle, rgba(255,255,255,0.1) 0%, transparent 70%);
                    animation: float 6s ease-in-out infinite;
                }}
                @keyframes float {{
                    0%, 100% {{ transform: translateY(0px) rotate(0deg); }}
                    50% {{ transform: translateY(-20px) rotate(180deg); }}
                }}
                .header-content {{ position: relative; z-index: 1; }}
                .header h1 {{ 
                    font-size: 2.5em; 
                    margin-bottom: 10px; 
                    font-weight: 700;
                    text-shadow: 0 2px 4px rgba(0,0,0,0.3);
                }}
                .header p {{ 
                    font-size: 1.2em; 
                    opacity: 0.9;
                    font-weight: 300;
                }}
                .content {{ 
                    padding: 40px 30px; 
                    background: #fafbfc;
                }}
                .alert-card {{ 
                    background: linear-gradient(135deg, #fef2f2 0%, #fecaca 100%); 
                    padding: 30px; 
                    border-radius: 16px; 
                    margin: 25px 0; 
                    border-left: 5px solid #dc2626;
                    box-shadow: 0 8px 25px rgba(220, 38, 38, 0.1);
                }}
                .alert-card h2 {{ 
                    color: #dc2626; 
                    font-size: 1.5em; 
                    margin-bottom: 15px; 
                    display: flex;
                    align-items: center;
                    gap: 10px;
                }}
                .info-card {{ 
                    background: white; 
                    padding: 30px; 
                    border-radius: 16px; 
                    margin: 25px 0; 
                    box-shadow: 0 8px 25px rgba(0,0,0,0.08);
                    border: 1px solid #e8ecf0;
                }}
                .info-card h3 {{ 
                    color: #2d3748; 
                    font-size: 1.4em; 
                    margin-bottom: 20px;
                    display: flex;
                    align-items: center;
                    gap: 10px;
                }}
                .info-table {{ 
                    width: 100%; 
                    border-collapse: collapse;
                    margin: 20px 0;
                }}
                .info-table td {{ 
                    padding: 12px 0; 
                    border-bottom: 1px solid #f1f5f9;
                }}
                .info-table .label {{ 
                    font-weight: 600; 
                    color: #4a5568; 
                    width: 30%;
                }}
                .info-table .value {{ 
                    color: #2d3748; 
                    font-weight: 500;
                }}
                .old-value {{ 
                    color: #dc2626; 
                    background: #fef2f2;
                    padding: 4px 8px;
                    border-radius: 4px;
                }}
                .new-value {{ 
                    color: #16a34a; 
                    background: #f0fdf4;
                    padding: 4px 8px;
                    border-radius: 4px;
                    font-weight: 700;
                }}
                .qr-section {{ 
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                    padding: 40px 30px; 
                    border-radius: 16px; 
                    margin: 25px 0; 
                    text-align: center;
                    color: white;
                    position: relative;
                    overflow: hidden;
                }}
                .qr-section::before {{
                    content: '';
                    position: absolute;
                    top: -50%;
                    right: -50%;
                    width: 200%;
                    height: 200%;
                    background: radial-gradient(circle, rgba(255,255,255,0.1) 0%, transparent 70%);
                    animation: float 8s ease-in-out infinite reverse;
                }}
                .qr-content {{ position: relative; z-index: 1; }}
                .qr-section h3 {{ 
                    font-size: 1.8em; 
                    margin-bottom: 25px; 
                    font-weight: 700;
                    text-shadow: 0 2px 4px rgba(0,0,0,0.3);
                }}
                .qr-code-display {{ 
                    background: rgba(255,255,255,0.15); 
                    backdrop-filter: blur(10px);
                    padding: 25px; 
                    border-radius: 12px; 
                    margin: 20px 0;
                    border: 1px solid rgba(255,255,255,0.2);
                }}
                .qr-text {{ 
                    font-size: 2em; 
                    font-weight: 700; 
                    margin: 15px 0; 
                    font-family: 'Courier New', monospace; 
                    background: rgba(255,255,255,0.2); 
                    padding: 15px 25px; 
                    border-radius: 8px; 
                    display: inline-block; 
                    border: 2px solid rgba(255,255,255,0.3);
                    letter-spacing: 2px;
                }}
                .notice-card {{ 
                    background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%); 
                    padding: 25px; 
                    border-radius: 16px; 
                    margin: 25px 0; 
                    border-left: 5px solid #f59e0b;
                    box-shadow: 0 8px 25px rgba(245, 158, 11, 0.1);
                }}
                .notice-card h4 {{ 
                    color: #92400e; 
                    margin: 0 0 15px 0; 
                    font-size: 1.2em;
                    display: flex;
                    align-items: center;
                    gap: 8px;
                }}
                .notice-card ul {{ 
                    color: #92400e; 
                    margin: 0; 
                    padding-left: 20px; 
                    list-style: none;
                }}
                .notice-card li {{ 
                    margin: 8px 0; 
                    padding-left: 20px;
                    position: relative;
                }}
                .notice-card li::before {{
                    content: '⚠️';
                    position: absolute;
                    left: 0;
                }}
                .instructions-card {{ 
                    background: linear-gradient(135deg, #f0fdf4 0%, #bbf7d0 100%); 
                    padding: 25px; 
                    border-radius: 16px; 
                    margin: 25px 0; 
                    border-left: 5px solid #16a34a;
                    box-shadow: 0 8px 25px rgba(22, 163, 74, 0.1);
                }}
                .instructions-card h4 {{ 
                    color: #16a34a; 
                    margin: 0 0 15px 0; 
                    font-size: 1.2em;
                    display: flex;
                    align-items: center;
                    gap: 8px;
                }}
                .instructions-card ul {{ 
                    color: #16a34a; 
                    margin: 0; 
                    padding-left: 20px; 
                    list-style: none;
                }}
                .instructions-card li {{ 
                    margin: 8px 0; 
                    padding-left: 20px;
                    position: relative;
                }}
                .instructions-card li::before {{
                    content: '✓';
                    position: absolute;
                    left: 0;
                    color: #16a34a;
                    font-weight: bold;
                }}
                .footer {{ 
                    text-align: center; 
                    margin-top: 40px; 
                    padding: 30px;
                    background: #f8fafc;
                    color: #64748b;
                    border-top: 1px solid #e2e8f0;
                }}
                .footer p {{ margin: 8px 0; }}
                .footer small {{ 
                    font-size: 0.9em; 
                    opacity: 0.8;
                }}
                @media (max-width: 600px) {{
                    .email-container {{ margin: 10px; border-radius: 15px; }}
                    .header, .content {{ padding: 20px; }}
                    .qr-text {{ font-size: 1.5em; }}
                    .header h1 {{ font-size: 2em; }}
                }}
            </style>
        </head>
        <body>
            <div class="email-container">
                <div class="header">
                    <div class="header-content">
                        <h1>🔄 Visit Rescheduled</h1>
                        <p>C4i4 Lab - Centre for Industry 4.0</p>
                    </div>
                </div>
                
                <div class="content">
                    <div class="alert-card">
                        <h2>⚠️ Important: Your Visit Has Been Rescheduled</h2>
                    <p>Hello {visitor.name}, your visit to C4i4 Lab has been rescheduled. Please note the new date and time below.</p>
                </div>
                
                    
                    <div class="info-card">
                        <h3>📅 Updated Visit Details</h3>
                        <table class="info-table">
                            <tr>
                                <td class="label">Name:</td>
                                <td class="value">{visitor.name}</td>
                        </tr>
                        <tr>
                                <td class="label">Email:</td>
                                <td class="value">{visitor.email}</td>
                        </tr>
                            <tr>
                                <td class="label">Previous Date:</td>
                                <td class="value"><span class="old-value">{old_date}</span></td>
                        </tr>
                            <tr>
                                <td class="label">Previous Time:</td>
                                <td class="value"><span class="old-value">{old_time}</span></td>
                        </tr>
                            <tr>
                                <td class="label">New Date:</td>
                                <td class="value"><span class="new-value">{new_date}</span></td>
                        </tr>
                            <tr>
                                <td class="label">New Time:</td>
                                <td class="value"><span class="new-value">{new_time}</span></td>
                        </tr>
                        <tr>
                                <td class="label">Purpose:</td>
                                <td class="value">{visitor.get_purpose_display()}</td>
                        </tr>
                       
                    </table>
                </div>
                
                    <div class="qr-section">
                        <div class="qr-content">
                            <h3>📱 Your New QR Code</h3>
                            <div class="qr-code-display">
                                <div class="qr-text">{visitor.qr_code}</div>
                                <div class="qr-instruction">Present this QR code upon arrival</div>
                            </div>
                    </div>
                </div>
                
                    <div class="notice-card">
                        <h4>⚠️ Important Notice</h4>
                        <ul>
                        <li><strong>Your previous QR code is now expired</strong></li>
                        <li>Please use the new date and time for your visit</li>
                        <li>Use the new QR code provided above for verification</li>
                        <li>Download the attached PDF for offline access</li>
                    </ul>
                </div>
                
                    <div class="instructions-card">
                        <h4>✅ Updated Instructions</h4>
                        <ul>
                        <li>Please arrive on time for your <strong>new scheduled visit</strong></li>
                        <li>Bring a valid ID for verification</li>
                        <li>Present the new QR code at the reception desk</li>
                        <li>Follow all safety protocols and guidelines</li>
                    </ul>
                    </div>
                </div>
                
                <div class="footer">
                    <p><strong>If you have any questions about this reschedule, please contact us at your earliest convenience.</strong></p>
                    <p><small>This is an automated message. Please do not reply to this email.</small></p>
                </div>
            </div>
        </body>
        </html>
        """

        # Plain text content
        text_content = f"""
        Visit Rescheduled - C4i4 Lab
        
        Hello {visitor.name}!
        
        Your visit to C4i4 Lab has been rescheduled. Please note the new details below:
        
        Updated Visit Details:
        - Name: {visitor.name}
        - Email: {visitor.email}
        - Previous Date: {old_date}
        - Previous Time: {old_time}
        - NEW DATE: {new_date}
        - NEW TIME: {new_time}
        - Purpose: {visitor.get_purpose_display()}
        - NEW QR Code: {visitor.qr_code}
        
        Important Notice:
        - Your previous QR code is now expired
        - Please use the new date and time for your visit
        - Use the new QR code provided above for verification
        - Download the attached PDF for offline access
        
        Updated Instructions:
        - Please arrive on time for your NEW scheduled visit
        - Bring a valid ID for verification
        - Present the new QR code at the reception desk
        - Follow all safety protocols and guidelines
        
        If you have any questions about this reschedule, please contact us at your earliest convenience.
        
        This is an automated message. Please do not reply to this email.
        """

        # Create email
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[visitor.email],
        )

        # Attach HTML content
        email.attach_alternative(html_content, "text/html")

        # Attach only PDF and enhanced QR image (as requested)
        if pdf_bytes:
            email.attach(
                f"visitor_confirmation_{visitor.qr_code}.pdf",
                pdf_bytes,
                "application/pdf",
            )
            print("✅ New visitor confirmation PDF attached")

        if enhanced_qr_bytes:
            email.attach(
                f"visitor_qr_code_{visitor.qr_code}.png",
                enhanced_qr_bytes,
                "image/png",
            )
            print("✅ New QR code image attached")

        # Send email
        email.send()

        print(
            f"Reschedule notification email with new QR code and PDF sent successfully to {visitor.email}"
        )
        return True

    except Exception as e:
        print(
            f"Failed to send reschedule notification email to {visitor.email}: {str(e)}"
        )
        return False


def send_host_notification(visitor):
    """Send notification email to host about visitor registration"""
    try:
        subject = f"New Visitor Registration - {visitor.name} - {visitor.visit_date}"

        # Enhanced HTML email template for host notification
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>New Visitor Registration - {visitor.name}</title>
            <style>
                * {{ margin: 0; padding: 0; box-sizing: border-box; }}
                body {{ 
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
                    line-height: 1.6; 
                    background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%);
                    margin: 0;
                    padding: 20px;
                }}
                .email-container {{ 
                    max-width: 650px; 
                    margin: 0 auto; 
                    background: white;
                    border-radius: 20px;
                    overflow: hidden;
                    box-shadow: 0 20px 40px rgba(0,0,0,0.1);
                }}
                .header {{ 
                    background: linear-gradient(135deg, #0ea5e9 0%, #0284c7 100%); 
                    color: white; 
                    padding: 40px 30px; 
                    text-align: center; 
                    position: relative;
                    overflow: hidden;
                }}
                .header::before {{
                    content: '';
                    position: absolute;
                    top: -50%;
                    left: -50%;
                    width: 200%;
                    height: 200%;
                    background: radial-gradient(circle, rgba(255,255,255,0.1) 0%, transparent 70%);
                    animation: float 6s ease-in-out infinite;
                }}
                @keyframes float {{
                    0%, 100% {{ transform: translateY(0px) rotate(0deg); }}
                    50% {{ transform: translateY(-20px) rotate(180deg); }}
                }}
                .header-content {{ position: relative; z-index: 1; }}
                .header h1 {{ 
                    font-size: 2.5em; 
                    margin-bottom: 10px; 
                    font-weight: 700;
                    text-shadow: 0 2px 4px rgba(0,0,0,0.3);
                }}
                .header p {{ 
                    font-size: 1.2em; 
                    opacity: 0.9;
                    font-weight: 300;
                }}
                .content {{ 
                    padding: 40px 30px; 
                    background: #fafbfc;
                }}
                .info-card {{ 
                    background: white; 
                    padding: 30px; 
                    border-radius: 16px; 
                    margin: 25px 0; 
                    box-shadow: 0 8px 25px rgba(0,0,0,0.08);
                    border: 1px solid #e8ecf0;
                    transition: transform 0.3s ease;
                }}
                .info-card:hover {{ transform: translateY(-2px); }}
                .info-card h2 {{ 
                    color: #2d3748; 
                    font-size: 1.5em; 
                    margin-bottom: 20px; 
                    display: flex;
                    align-items: center;
                    gap: 10px;
                }}
                .info-grid {{ 
                    display: grid; 
                    grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); 
                    gap: 15px; 
                }}
                .info-item {{ 
                    display: flex; 
                    justify-content: space-between; 
                    padding: 12px 0; 
                    border-bottom: 1px solid #f1f5f9;
                }}
                .info-item:last-child {{ border-bottom: none; }}
                .info-label {{ 
                    font-weight: 600; 
                    color: #4a5568; 
                    min-width: 120px;
                }}
                .info-value {{ 
                    color: #2d3748; 
                    font-weight: 500;
                }}
                .highlight {{ 
                    background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%); 
                    padding: 25px; 
                    border-radius: 16px; 
                    margin: 25px 0; 
                    border-left: 5px solid #f59e0b;
                    box-shadow: 0 8px 25px rgba(245, 158, 11, 0.1);
                }}
                .highlight h3 {{ 
                    color: #92400e; 
                    font-size: 1.3em; 
                    margin-bottom: 15px;
                    display: flex;
                    align-items: center;
                    gap: 10px;
                }}
                .highlight p {{ 
                    margin: 10px 0; 
                    color: #92400e;
                    font-weight: 500;
                }}
                .instructions {{ 
                    background: white; 
                    padding: 30px; 
                    border-radius: 16px; 
                    margin: 25px 0; 
                    box-shadow: 0 8px 25px rgba(0,0,0,0.08);
                    border-left: 5px solid #0ea5e9;
                }}
                .instructions h3 {{ 
                    color: #2d3748; 
                    font-size: 1.4em; 
                    margin-bottom: 20px;
                    display: flex;
                    align-items: center;
                    gap: 10px;
                }}
                .instructions ul {{ 
                    list-style: none; 
                    padding: 0;
                }}
                .instructions li {{ 
                    margin: 12px 0; 
                    padding: 12px 0 12px 30px; 
                    position: relative;
                    border-bottom: 1px solid #f1f5f9;
                }}
                .instructions li:last-child {{ border-bottom: none; }}
                .instructions li::before {{
                    content: '→';
                    position: absolute;
                    left: 0;
                    color: #0ea5e9;
                    font-weight: bold;
                    font-size: 1.2em;
                }}
                .footer {{ 
                    text-align: center; 
                    margin-top: 40px; 
                    padding: 30px;
                    background: #f8fafc;
                    color: #64748b;
                    border-top: 1px solid #e2e8f0;
                }}
                .footer p {{ margin: 8px 0; }}
                .footer small {{ 
                    font-size: 0.9em; 
                    opacity: 0.8;
                }}
                .badge {{
                    display: inline-block;
                    padding: 4px 12px;
                    background: #0ea5e9;
                    color: white;
                    border-radius: 20px;
                    font-size: 0.8em;
                    font-weight: 600;
                    margin-left: 8px;
                }}
                @media (max-width: 600px) {{
                    .email-container {{ margin: 10px; border-radius: 15px; }}
                    .header, .content {{ padding: 20px; }}
                    .info-grid {{ grid-template-columns: 1fr; }}
                    .header h1 {{ font-size: 2em; }}
                }}
            </style>
        </head>
        <body>
            <div class="email-container">
                <div class="header">
                    <div class="header-content">
                        <h1>👋 New Visitor Registration</h1>
                        <p>Someone has registered to visit you at C4i4 Lab</p>
                    </div>
                </div>
                
                <div class="content">
                    <div class="info-card">
                        <h2>👤 Visitor Information</h2>
                        <div class="info-grid">
                            <div class="info-item">
                                <span class="info-label">Name:</span>
                                <span class="info-value">{visitor.name}</span>
                            </div>
                            <div class="info-item">
                                <span class="info-label">Email:</span>
                                <span class="info-value">{visitor.email}</span>
                            </div>
                            <div class="info-item">
                                <span class="info-label">Phone:</span>
                                <span class="info-value">{visitor.phone}</span>
                            </div>
                            <div class="info-item">
                                <span class="info-label">Company:</span>
                                <span class="info-value">{visitor.company or 'Not provided'}</span>
                            </div>
                            <div class="info-item">
                                <span class="info-label">Visitor Type:</span>
                                <span class="info-value">{visitor.get_visitor_type_display()}</span>
                            </div>
                            <div class="info-item">
                                <span class="info-label">Category:</span>
                                <span class="info-value">{visitor.get_visitor_category_display()}</span>
                            </div>
                            <div class="info-item">
                                <span class="info-label">Visit Date:</span>
                                <span class="info-value">{visitor.visit_date}</span>
                            </div>
                            <div class="info-item">
                                <span class="info-label">Visit Time:</span>
                                <span class="info-value">{visitor.visit_time}</span>
                            </div>
                            <div class="info-item">
                                <span class="info-label">Purpose:</span>
                                <span class="info-value">{visitor.get_purpose_display()}</span>
                            </div>
                          
                            <div class="info-item">
                                <span class="info-label">QR Code:</span>
                                <span class="info-value">{visitor.qr_code}</span>
                            </div>
                        </div>
                    </div>
                    
                    <div class="highlight">
                        <h3>🔔 Action Required</h3>
                        <p>1. <strong>Confirm availability</strong> - Please confirm you're available for this visit</p>
                        <p>2. <strong>Prepare for meeting</strong> - Review visitor details and purpose</p>
                        <p>3. <strong>Contact visitor</strong> - Reach out if you need to reschedule</p>
                        <p>4. <strong>Be ready</strong> - Visitor will arrive with QR code for verification</p>
                    </div>
                    
                    <div class="instructions">
                        <h3>📋 Host Instructions</h3>
                        <ul>
                            <li>Please confirm your availability for the scheduled visit</li>
                            <li>Review the visitor's purpose and prepare accordingly</li>
                            <li>Contact the visitor if you need to reschedule</li>
                            <li>Be available at the scheduled time to meet the visitor</li>
                            <li>Guide the visitor through the verification process</li>
                            <li>Ensure all safety protocols are followed during the visit</li>
                        </ul>
                    </div>
                </div>
                
                <div class="footer">
                    <p><strong>Thank you for hosting visitors at C4i4 Lab!</strong></p>
                    <p>Centre for Industry 4.0 - Innovation & Excellence</p>
                    <p><small>This is an automated notification. Please contact the visitor directly if needed.</small></p>
                </div>
            </div>
        </body>
        </html>
        """

        # Plain text version
        text_content = f"""
        New Visitor Registration - {visitor.name}
        =====================================
        
        Hello {visitor.host_name},
        
        A new visitor has registered to visit you at C4i4 Lab. Here are the details:
        
        Visitor Information:
        - Name: {visitor.name}
        - Email: {visitor.email}
        - Phone: {visitor.phone}
        - Company: {visitor.company or 'Not provided'}
        - Visitor Type: {visitor.get_visitor_type_display()}
        - Category: {visitor.get_visitor_category_display()}
        - Visit Date: {visitor.visit_date}
        - Visit Time: {visitor.visit_time}
        - Purpose: {visitor.get_purpose_display()}
        - QR Code: {visitor.qr_code}
        
        Action Required:
        1. Confirm availability - Please confirm you're available for this visit
        2. Prepare for meeting - Review visitor details and purpose
        3. Contact visitor - Reach out if you need to reschedule
        4. Be ready - Visitor will arrive with QR code for verification
        
        Host Instructions:
        - Please confirm your availability for the scheduled visit
        - Review the visitor's purpose and prepare accordingly
        - Contact the visitor if you need to reschedule
        - Be available at the scheduled time to meet the visitor
        - Guide the visitor through the verification process
        - Ensure all safety protocols are followed during the visit
        
        Thank you for hosting visitors at C4i4 Lab!
        
        This is an automated notification. Please contact the visitor directly if needed.
        """

        print(f"=== HOST NOTIFICATION EMAIL SENT TO: {visitor.host_email} ===")
        print(f"SUBJECT: {subject}")
        print("HTML Content prepared")
        print("=" * 50)

        # Try to send actual email
        try:
            msg = EmailMultiAlternatives(
                subject,
                text_content,
                "testkirantondchore@gmail.com",
                [visitor.host_email],
            )
            msg.attach_alternative(html_content, "text/html")
            msg.send()
            print("✅ Host notification email sent successfully via SMTP")
        except Exception as smtp_error:
            print(f"⚠️  SMTP error: {smtp_error}")
            print("📧 Email content printed above for manual sending")

        return f"Host notification email sent to {visitor.host_email}"

    except Exception as e:
        print(f"Host notification email send failed: {str(e)}")
        return f"Failed to send host notification to {visitor.host_email}: {str(e)}"


def send_bulk_host_notification(
    host_name, host_email, visitors, visit_date, visit_time, purpose
):
    """Send summary email to host about bulk visitor registrations"""
    try:
        # Get purpose display name
        purpose_choices = {
            "business_meeting": "Business Meeting",
            "interview": "Interview",
            "delivery": "Delivery",
            "maintenance": "Maintenance",
            "training": "Training",
            "i_factory_visit": "iFactory Visit",
            "i_factory_training": "iFactory Training",
            "other": "Other",
        }
        purpose_display = purpose_choices.get(purpose, purpose)

        visitor_count = len(visitors)
        subject = (
            f"Bulk Visitor Registration - {visitor_count} Visitors on {visit_date}"
        )

        # Build visitor list HTML
        visitor_rows = ""
        for i, visitor in enumerate(visitors, 1):
            visitor_rows += f"""
            <tr style="border-bottom: 1px solid #e2e8f0;">
                <td style="padding: 15px; text-align: center; font-weight: 600; color: #667eea;">{i}</td>
                <td style="padding: 15px; font-weight: 500; color: #2d3748;">{visitor['name']}</td>
                <td style="padding: 15px; color: #4a5568;">{visitor['email']}</td>
                <td style="padding: 15px; font-family: 'Courier New', monospace; color: #667eea; font-weight: 600;">{visitor['qr_code']}</td>
            </tr>
            """

        # Enhanced HTML email template for bulk host notification
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Bulk Visitor Registration - {visitor_count} Visitors</title>
            <style>
                * {{ margin: 0; padding: 0; box-sizing: border-box; }}
                body {{ 
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
                    line-height: 1.6; 
                    background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%);
                    margin: 0;
                    padding: 20px;
                }}
                .email-container {{ 
                    max-width: 800px; 
                    margin: 0 auto; 
                    background: white;
                    border-radius: 20px;
                    overflow: hidden;
                    box-shadow: 0 20px 40px rgba(0,0,0,0.1);
                }}
                .header {{ 
                    background: linear-gradient(135deg, #0ea5e9 0%, #0284c7 100%); 
                    color: white; 
                    padding: 40px 30px; 
                    text-align: center; 
                    position: relative;
                    overflow: hidden;
                }}
                .header::before {{
                    content: '';
                    position: absolute;
                    top: -50%;
                    left: -50%;
                    width: 200%;
                    height: 200%;
                    background: radial-gradient(circle, rgba(255,255,255,0.1) 0%, transparent 70%);
                    animation: float 6s ease-in-out infinite;
                }}
                @keyframes float {{
                    0%, 100% {{ transform: translateY(0px) rotate(0deg); }}
                    50% {{ transform: translateY(-20px) rotate(180deg); }}
                }}
                .header-content {{ position: relative; z-index: 1; }}
                .header h1 {{ 
                    font-size: 2.5em; 
                    margin-bottom: 10px; 
                    font-weight: 700;
                    text-shadow: 0 2px 4px rgba(0,0,0,0.3);
                }}
                .header p {{ 
                    font-size: 1.2em; 
                    opacity: 0.9;
                    font-weight: 300;
                }}
                .badge {{
                    display: inline-block;
                    padding: 8px 20px;
                    background: rgba(255,255,255,0.2);
                    border-radius: 30px;
                    font-size: 1.1em;
                    font-weight: 600;
                    margin-top: 10px;
                    border: 2px solid rgba(255,255,255,0.3);
                }}
                .content {{ 
                    padding: 40px 30px; 
                    background: #fafbfc;
                }}
                .summary-card {{ 
                    background: white; 
                    padding: 30px; 
                    border-radius: 16px; 
                    margin: 25px 0; 
                    box-shadow: 0 8px 25px rgba(0,0,0,0.08);
                    border: 1px solid #e8ecf0;
                }}
                .summary-card h2 {{ 
                    color: #2d3748; 
                    font-size: 1.5em; 
                    margin-bottom: 20px; 
                    display: flex;
                    align-items: center;
                    gap: 10px;
                }}
                .info-grid {{ 
                    display: grid; 
                    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); 
                    gap: 15px; 
                    margin-top: 20px;
                }}
                .info-item {{ 
                    display: flex; 
                    flex-direction: column;
                    padding: 15px; 
                    background: #f8fafc;
                    border-radius: 8px;
                    border-left: 4px solid #0ea5e9;
                }}
                .info-label {{ 
                    font-weight: 600; 
                    color: #4a5568; 
                    font-size: 0.9em;
                    margin-bottom: 5px;
                }}
                .info-value {{ 
                    color: #2d3748; 
                    font-weight: 500;
                    font-size: 1.1em;
                }}
                .visitors-table {{ 
                    background: white; 
                    padding: 30px; 
                    border-radius: 16px; 
                    margin: 25px 0; 
                    box-shadow: 0 8px 25px rgba(0,0,0,0.08);
                    border: 1px solid #e8ecf0;
                    overflow-x: auto;
                }}
                .visitors-table h2 {{ 
                    color: #2d3748; 
                    font-size: 1.5em; 
                    margin-bottom: 20px; 
                    display: flex;
                    align-items: center;
                    gap: 10px;
                }}
                table {{ 
                    width: 100%; 
                    border-collapse: collapse;
                    margin-top: 15px;
                }}
                th {{ 
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                    color: white; 
                    padding: 15px; 
                    text-align: left;
                    font-weight: 600;
                    font-size: 0.95em;
                    text-transform: uppercase;
                    letter-spacing: 0.5px;
                }}
                th:first-child {{ border-radius: 8px 0 0 0; }}
                th:last-child {{ border-radius: 0 8px 0 0; }}
                td {{ 
                    padding: 15px; 
                    color: #4a5568;
                }}
                tr:hover {{ background: #f8fafc; }}
                .instructions {{ 
                    background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%); 
                    padding: 30px; 
                    border-radius: 16px; 
                    margin: 25px 0; 
                    border-left: 5px solid #f59e0b;
                    box-shadow: 0 8px 25px rgba(245, 158, 11, 0.1);
                }}
                .instructions h3 {{ 
                    color: #92400e; 
                    font-size: 1.3em; 
                    margin-bottom: 15px;
                    display: flex;
                    align-items: center;
                    gap: 10px;
                }}
                .instructions ul {{ 
                    list-style: none; 
                    padding: 0;
                    margin-top: 15px;
                }}
                .instructions li {{ 
                    margin: 12px 0; 
                    padding: 12px 0 12px 30px; 
                    position: relative;
                    color: #92400e;
                    font-weight: 500;
                }}
                .instructions li::before {{
                    content: '✓';
                    position: absolute;
                    left: 0;
                    color: #f59e0b;
                    font-weight: bold;
                    font-size: 1.2em;
                }}
                .footer {{ 
                    text-align: center; 
                    margin-top: 40px; 
                    padding: 30px;
                    background: #f8fafc;
                    color: #64748b;
                    border-top: 1px solid #e2e8f0;
                }}
                .footer p {{ margin: 8px 0; }}
                @media (max-width: 600px) {{
                    .email-container {{ margin: 10px; border-radius: 15px; }}
                    .header, .content {{ padding: 20px; }}
                    .info-grid {{ grid-template-columns: 1fr; }}
                    .header h1 {{ font-size: 2em; }}
                    table {{ font-size: 0.9em; }}
                }}
            </style>
        </head>
        <body>
            <div class="email-container">
                <div class="header">
                    <div class="header-content">
                        <h1>👥 Bulk Visitor Registration</h1>
                        <p>You have {visitor_count} visitors scheduled</p>
                        <div class="badge">{visitor_count} Visitors</div>
                    </div>
                </div>
                
                <div class="content">
                    <div class="summary-card">
                        <h2>📅 Visit Summary</h2>
                        <div class="info-grid">
                            <div class="info-item">
                                <span class="info-label">Visit Date</span>
                                <span class="info-value">{visit_date}</span>
                            </div>
                            <div class="info-item">
                                <span class="info-label">Visit Time</span>
                                <span class="info-value">{visit_time}</span>
                            </div>
                           
                            <div class="info-item">
                                <span class="info-label">Purpose</span>
                                <span class="info-value">{purpose_display}</span>
                            </div>
                            <div class="info-item">
                                <span class="info-label">Total Visitors</span>
                                <span class="info-value">{visitor_count}</span>
                            </div>
                            <div class="info-item">
                                <span class="info-label">Host</span>
                                <span class="info-value">{host_name}</span>
                            </div>
                        </div>
                    </div>
                    
                    <div class="visitors-table">
                        <h2>👤 Visitor List</h2>
                        <table>
                            <thead>
                                <tr>
                                    <th>#</th>
                                    <th>Name</th>
                                    <th>Email</th>
                                    <th>QR Code</th>
                                </tr>
                            </thead>
                            <tbody>
                                {visitor_rows}
                            </tbody>
                        </table>
                    </div>
                    
                    <div class="instructions">
                        <h3>⚠️ Action Required</h3>
                        <ul>
                            <li>Confirm your availability for {visit_date} at {visit_time}</li>
                            <li>Review the list of {visitor_count} visitors above</li>
                            <li>Prepare meeting materials and agenda for the visit</li>
                            <li>Contact visitors directly if you need to reschedule</li>
                            <li>Be available at the scheduled time to meet all visitors</li>
                            <li>Each visitor will arrive with their unique QR code for verification</li>
                            <li>Ensure all safety protocols are followed during the visit</li>
                        </ul>
                    </div>
                    
                    <div class="footer">
                        <p><strong>C4i4 Lab - Visitor Management System</strong></p>
                        <p>This is an automated notification for bulk visitor registration.</p>
                        <p>Each visitor has received their individual confirmation email with QR code.</p>
                        <p style="margin-top: 15px; font-size: 0.9em;">If you have any questions, please contact the visitors directly.</p>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """

        # Plain text version
        visitor_list_text = "\n".join(
            [
                f"{i}. {v['name']} - {v['email']} - QR: {v['qr_code']}"
                for i, v in enumerate(visitors, 1)
            ]
        )

        text_content = f"""
        Bulk Visitor Registration - {visitor_count} Visitors
        =====================================================
        
        Hello {host_name},
        
        You have {visitor_count} visitors scheduled to visit you at C4i4 Lab.
        
        Visit Details:
        - Date: {visit_date}
        - Time: {visit_time}
        - Purpose: {purpose_display}
        - Total Visitors: {visitor_count}
        
        Visitor List:
        {visitor_list_text}
        
        Action Required:
        1. Confirm your availability for {visit_date} at {visit_time}
        2. Review the list of {visitor_count} visitors above
        3. Prepare meeting materials and agenda for the visit
        4. Contact visitors directly if you need to reschedule
        5. Be available at the scheduled time to meet all visitors
        6. Each visitor will arrive with their unique QR code for verification
        7. Ensure all safety protocols are followed during the visit
        
        Note: Each visitor has received their individual confirmation email with QR code and PDF attachment.
        
        Thank you for hosting visitors at C4i4 Lab!
        
        This is an automated notification. Please contact the visitors directly if needed.
        """

        print(f"=== BULK HOST NOTIFICATION EMAIL SENT TO: {host_email} ===")
        print(f"SUBJECT: {subject}")
        print(f"VISITOR COUNT: {visitor_count}")
        print("HTML Content prepared")
        print("=" * 50)

        # Try to send actual email
        try:
            msg = EmailMultiAlternatives(
                subject,
                text_content,
                "testkirantondchore@gmail.com",
                [host_email],
            )
            msg.attach_alternative(html_content, "text/html")
            msg.send()
            print("✅ Bulk host notification email sent successfully via SMTP")
        except Exception as smtp_error:
            print(f"⚠️  SMTP error: {smtp_error}")
            print("📧 Email content printed above for manual sending")

        return f"Bulk host notification email sent to {host_email} for {visitor_count} visitors"

    except Exception as e:
        print(f"Bulk host notification email send failed: {str(e)}")
        return f"Failed to send bulk host notification to {host_email}: {str(e)}"
