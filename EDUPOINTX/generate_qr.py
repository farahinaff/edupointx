# generate_qr.py
import qrcode
import pandas as pd

BASE_URL = "https://edupointx.streamlit.app/?sid="

# Example list of student IDs (you can load from DB if needed)
student_list = [
    {"id": 1, "name": "Ali"},
    {"id": 2, "name": "Aisyah"},
    {"id": 3, "name": "Firdaus"},
]

for student in student_list:
    qr_url = f"{BASE_URL}{student['id']}"
    img = qrcode.make(qr_url)
    img.save(f"qr_students/qr_{student['name']}_id{student['id']}.png")
    print(f"QR saved for {student['name']} → {qr_url}")
