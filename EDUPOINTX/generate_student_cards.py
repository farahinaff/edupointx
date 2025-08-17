import os
from sqlalchemy import create_engine, text
from PIL import Image, ImageDraw, ImageFont
import qrcode
from qrcode.constants import ERROR_CORRECT_H
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
card_width, card_height = 500, 330  # keep your card size
bg_color = (255, 248, 240)

# === QR TARGET BOX (we'll center the real QR inside this box) ===
TARGET_QR_SIZE = 160  # your previous intent
GAP_BETWEEN_QRS = 40  # space between the two QR boxes

# === FONT SETUP ===
try:
    font_title = ImageFont.truetype("arial.ttf", 24)
    font_label = ImageFont.truetype("arial.ttf", 18)
except:
    font_title = font_label = ImageFont.load_default()


def make_qr_exact(data: str, target_px: int = TARGET_QR_SIZE, prefer_border=5):
    """
    Generate a QR code at (about) target_px WITHOUT resizing.
    We:
      1) create a temp QR to learn module count,
      2) compute box_size so (modules + 2*border) * box_size <= target_px,
      3) regenerate the QR with that exact box_size.
    Returns (qr_img, actual_size_px).
    """
    # Step 1: build once to get modules_count
    tmp = qrcode.QRCode(
        version=None,
        error_correction=ERROR_CORRECT_H,
        box_size=1,
        border=prefer_border,
    )
    tmp.add_data(data)
    tmp.make(fit=True)
    modules = tmp.modules_count  # number of squares across, no border

    # Step 2: compute best border/box_size to fit target
    # Try border from prefer_border down to 4 (minimum recommended quiet zone)
    best = None
    for border in range(prefer_border, 3, -1):
        total_units = modules + 2 * border
        box_size = target_px // total_units
        if box_size >= 3:  # reasonable minimum for printing
            actual_size = total_units * box_size
            best = (border, box_size, actual_size)
            break
    if not best:
        # fallback: smallest viable box_size = 2 (very small, but still no resizing)
        border = 4
        total_units = modules + 2 * border
        box_size = max(2, target_px // total_units)
        actual_size = total_units * box_size
        best = (border, box_size, actual_size)

    border, box_size, actual_size = best

    # Step 3: build final QR with computed box_size/border (no resize afterwards)
    qr = qrcode.QRCode(
        version=None,
        error_correction=ERROR_CORRECT_H,
        box_size=box_size,
        border=border,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    return img, actual_size


# === FETCH STUDENTS FROM DB ===
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

    # QR images generated at (about) 160px WITHOUT resizing
    qr_add, add_sz = make_qr_exact(url_addpoints, TARGET_QR_SIZE, prefer_border=5)
    qr_red, red_sz = make_qr_exact(url_redeem, TARGET_QR_SIZE, prefer_border=5)

    # Create card canvas
    card = Image.new("RGB", (card_width, card_height), bg_color)
    draw = ImageDraw.Draw(card)

    # Paste logo
    try:
        logo = Image.open(LOGO_PATH).convert("RGBA").resize(LOGO_SIZE)
        card.paste(logo, (20, 20), logo)
    except Exception as e:
        print(f"⚠️ Failed to load logo: {e}")

    # --- Student info beside logo ---
    text_x = 20 + LOGO_SIZE[0] + 20  # to the right of logo
    text_y = 25  # align with logo
    draw.text((text_x, text_y), f"Name : {name}", font=font_label, fill="black")
    draw.text((text_x, text_y + 25), f"Class: {cls}", font=font_label, fill="black")

    # --- Layout for two QR slots ---
    qr_slot_left_x = 40
    qr_slot_top_y = 130  # safe margin above labels
    qr_slot_right_x = qr_slot_left_x + TARGET_QR_SIZE + GAP_BETWEEN_QRS

    # Center actual QR inside its slot (actual size may be <= target)
    add_x = qr_slot_left_x + (TARGET_QR_SIZE - add_sz) // 2
    add_y = qr_slot_top_y + (TARGET_QR_SIZE - add_sz) // 2
    red_x = qr_slot_right_x + (TARGET_QR_SIZE - red_sz) // 2
    red_y = qr_slot_top_y + (TARGET_QR_SIZE - red_sz) // 2

    # Paste QRs (no resizing)
    card.paste(qr_add, (add_x, add_y))
    card.paste(qr_red, (red_x, red_y))

    # Optional: faint divider between the slots (helps detectors)
    line_x = qr_slot_right_x - GAP_BETWEEN_QRS // 2
    draw.line(
        [(line_x, qr_slot_top_y - 10), (line_x, qr_slot_top_y + TARGET_QR_SIZE + 10)],
        fill=(210, 210, 210),
        width=2,
    )

    # Labels centered under each slot
    def center_text_in_slot(slot_x, slot_w, y, text_):
        # textbbox returns (l,t,r,b); width = r-l
        l, t, r, b = draw.textbbox((0, 0), text_, font=font_label)
        tw = r - l
        draw.text(
            (slot_x + (slot_w - tw) // 2, y), text_, font=font_label, fill="black"
        )

    label_y = qr_slot_top_y + TARGET_QR_SIZE + 8
    center_text_in_slot(qr_slot_left_x, TARGET_QR_SIZE, label_y, "Scan to Add Points")
    center_text_in_slot(qr_slot_right_x, TARGET_QR_SIZE, label_y, "Scan to Redeem")

    # Save
    filename = os.path.join(output_dir, f"{name.replace(' ', '_')}_{cls}.png")
    card.save(filename)
    print(f"✅ Saved: {filename}")
