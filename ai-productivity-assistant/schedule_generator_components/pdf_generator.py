import io
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

def generate_schedule_pdf(schedule_text):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    lines = schedule_text.split('\n')
    y = height - 50

    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, y, "Your Personalized Schedule")
    y -= 30

    c.setFont("Helvetica", 12)
    for line in lines:
        if y < 50:
            c.showPage()
            y = height - 50
            c.setFont("Helvetica", 12)
        c.drawString(50, y, line)
        y -= 20

    c.save()
    buffer.seek(0)
    return buffer
