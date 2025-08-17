import qrcode
from PIL import Image, ImageDraw, ImageFont
from sqlalchemy import create_engine, text
import os
from modules.db import DB_URL

# === DB CONNECTION ===
engine = create_engine(DB_URL)

# === BASE APP URL ===
BASE_URL = "https://edupointx.streamlit.app"

# === LOGO ===
LOGO_PATH = "assets/smapk_logo.png"
LOGO_SIZE = (60, 60)

# === OUTPUT DIR ===
output_dir = "qr_cards"
os.makedirs(output_dir, exist_ok=True)

# === CARD STYLE ===
card_width, card_height = 500, 330
bg_color = (255, 248, 240)

# === FONT SETUP ===
try:
    font_title = ImageFont.truetype("arial.ttf", 24)
    font_label = ImageFont.truetype("arial.ttf", 18)
except:
    font_title = font_label = ImageFont.load_default()

# === FETCH STUDENTS ===
with engine.connect() as conn:
    students = conn.execute(
        text("SELECT id, name, class_name FROM students ORDER BY class_name, name")
    ).fetchall()

# === GENERATE CARDS ===
for student in students:
    sid = student.id
    name = student.name
    cls = student.class_name

    # URLs
    url_addpoints = f"{BASE_URL}/?action=addpoints&sid={sid}"
    url_redeem = f"{BASE_URL}/?action=redeem&sid={sid}"

    # QR images
    qr_add = qrcode.make(url_addpoints).resize((160, 160))
    qr_redeem = qrcode.make(url_redeem).resize((160, 160))

    # Create card canvas
    card = Image.new("RGB", (card_width, card_height), bg_color)
    draw = ImageDraw.Draw(card)

    # Logo
    try:
        logo = Image.open(LOGO_PATH).convert("RGBA").resize(LOGO_SIZE)
        card.paste(logo, (20, 20), logo)
    except Exception as e:
        print(f"⚠️ Failed to load logo: {e}")

    # Student Info
    draw.text((20, 100), f"Name : {name}", font=font_label, fill="black")
    draw.text((20, 130), f"Class: {cls}", font=font_label, fill="black")

    # Paste QR codes side by side
    card.paste(qr_add, (40, 160))
    card.paste(qr_redeem, (300, 160))

    # Label below each QR
    draw.text((45, 330 - 30), "Scan to Add Points", font=font_label, fill="black")
    draw.text((305, 330 - 30), "Scan to Redeem", font=font_label, fill="black")

    # Save card
    filename = os.path.join(output_dir, f"{name.replace(' ', '_')}_id{sid}.png")
    card.save(filename)
    print(f"✅ Saved: {filename}")
