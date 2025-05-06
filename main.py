from flask import Flask, request, render_template, redirect, url_for, jsonify, session, flash, Response, render_template_string
from markupsafe import escape
from datetime import datetime
import math
import mysql.connector
from werkzeug.security import check_password_hash, generate_password_hash
import cv2
import pytesseract
import os

# Konfigurasi path Tesseract (ubah sesuai OS kamu)
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

app = Flask(__name__)
app.secret_key = "supersecretkey"

# MySQL Config
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': '',
    'database': 'parking_system'
}

def get_connection():
    return mysql.connector.connect(**db_config)

# Camera and OCR
camera = cv2.VideoCapture(0)
last_frame = None
ocr_result = ""

HTML_PAGE = '''...'''  # Tetap sama, bisa copy dari kode kamu sebelumnya

# Login system
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, password FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if user and password == user[1]:
            session['user_id'] = user[0]
            session['username'] = username
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password', 'danger')

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# Dashboard utama
@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    rows = get_data()
    return render_template('index.html', rows=rows)

def get_data():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM vehicle")
    data = cursor.fetchall()
    cursor.close()
    conn.close()
    return data

@app.route('/mark_paid/<int:id>')
def mark_paid(id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE vehicle SET PaymentStat = 'Paid' WHERE id = %s", (id,))
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('index'))

@app.route("/ticket-scan")
def ticket_scan():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template("ticket_scan.html")

@app.route("/api/vehicle/<id>")
def get_vehicle(id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, NoPol, Image, PaymentStat, CreatedAt, UpdatedAt 
        FROM vehicle WHERE id = %s
    """, (id,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()

    if row:
        created_at = row[4]
        now = datetime.now()
        duration_hours = max((now - created_at).total_seconds() / 3600, 0)
        fee = round(int(duration_hours * 3000), -3)

        record = {
            "id": row[0],
            "NoPol": row[1],
            "Image": row[2],
            "PaymentStat": row[3],
            "CreatedAt": row[4].strftime("%Y-%m-%d %H:%M:%S"),
            "UpdatedAt": row[5].strftime("%Y-%m-%d %H:%M:%S") if row[5] else None,
            "DurationHours": round(duration_hours, 2),
            "Fee": fee
        }
        return jsonify({"success": True, "record": record})
    else:
        return jsonify({"success": False, "message": "Vehicle not found"}), 404

@app.route("/api/vehicle/pay/<id>", methods=["POST"])
def mark_as_paid(id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT CreatedAt FROM vehicle WHERE id = %s", (id,))
    row = cursor.fetchone()
    if not row:
        cursor.close()
        conn.close()
        return jsonify({"success": False, "message": "Vehicle not found"}), 404

    created_at = row[0]
    updated_at = datetime.now()
    duration_hours = max((updated_at - created_at).total_seconds() / 3600, 0)
    fee = round(int(duration_hours * 3000), -3)

    updated_str = updated_at.strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("""
        UPDATE vehicle
        SET UpdatedAt = %s, PaymentStat = %s, Fee = %s
        WHERE id = %s
    """, (updated_str, "Paid", fee, id))

    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({
        "success": True,
        "updatedAt": updated_str,
        "durationHours": round(duration_hours, 2),
        "fee": fee
    })

# OCR Features — moved to /user

HTML_PAGE = '''
<!doctype html>
<html lang="en">
  <head>
    <title>OCR Kamera - Parkir</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
      .ocr-result-box {
        font-size: 2rem;
        font-weight: bold;
        color: #2c3e50;
        background-color: #ecf0f1;
        border: 2px dashed #7f8c8d;
        padding: 20px;
        min-height: 150px;
        border-radius: 10px;
        text-align: center;
      }
      #clock {
        font-size: 2rem;
        font-weight: bold;
        margin-top: 20px;
        text-align: center;
        color: #e74c3c;
      }
    </style>
    <script>
      function updateClock() {
        const now = new Date();
        const options = { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' };
        const dateString = now.toLocaleDateString('id-ID', options);
        const timeString = now.toLocaleTimeString('id-ID');
        document.getElementById('clock').innerHTML = dateString + ' - ' + timeString;
      }
      setInterval(updateClock, 1000);
      window.onload = updateClock;
    </script>
  </head>
  <body class="bg-light">
    <div class="container py-5">
      <h1 class="text-center mb-5">🚘 Sistem E-Parking</h1>
      <div class="row">
        <div class="col-md-6 text-center">
          <img src="{{ url_for('video_feed') }}" class="img-fluid rounded border mb-3" style="max-height: 480px;">
          <form method="POST" action="/scan" class="d-flex justify-content-center gap-3">
            <button type="submit" class="btn btn-lg btn-success">Tiket</button>
            <button type="button" class="btn btn-lg btn-danger">Bantuan</button>
          </form>
        </div>
        <div class="col-md-6 d-flex align-items-center justify-content-center">
          <div class="w-100">
            <label class="form-label fs-4 mb-2 fw-bold">Nomor Plat Mobil:</label>
            <div class="ocr-result-box">
              {{ text }}
            </div>
            <div id="clock"></div>
          </div>
        </div>
      </div>
    </div>
  </body>
</html>
'''


@app.route('/user')
def user_home():
    return render_template_string(HTML_PAGE, text=ocr_result)

def generate_frames():
    global last_frame
    while True:
        success, frame = camera.read()
        if not success:
            break
        last_frame = frame.copy()
        ret, buffer = cv2.imencode('.jpg', frame)
        frame_bytes = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/scan', methods=['POST'])
def scan():
    global ocr_result, last_frame
    if last_frame is not None:
        os.makedirs("photo", exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"photo/scan_{timestamp}.jpg"
        cv2.imwrite(filename, last_frame)

        gray = cv2.cvtColor(last_frame, cv2.COLOR_BGR2GRAY)
        thresh = cv2.adaptiveThreshold(gray, 255,
                                       cv2.ADAPTIVE_THRESH_MEAN_C,
                                       cv2.THRESH_BINARY, 15, 8)

        text = pytesseract.image_to_string(thresh, lang='eng')
        ocr_result = text.strip() if text.strip() else "Tidak ada teks terdeteksi."

        with open("hasil.txt", "w", encoding="utf-8") as f:
            f.write(ocr_result)
    else:
        ocr_result = "Nomor Polisi Mobil"

    return render_template_string(HTML_PAGE, text=ocr_result)

if __name__ == '__main__':
    app.run(debug=True)


# from flask import Flask, request, render_template, redirect, url_for, jsonify, session, flash
# from markupsafe import escape
# from datetime import datetime
# import math
# import mysql.connector
# from werkzeug.security import check_password_hash, generate_password_hash


# app = Flask(__name__)
# app.secret_key = "supersecretkey"  # Use a strong secret key in production


# # Configure your MySQL connection
# db_config = {
#     'host': 'localhost',
#     'user': 'root',
#     'password': '',
#     'database': 'parking_system'
# }

# def get_connection():
#     return mysql.connector.connect(**db_config)



# @app.route('/login', methods=['GET', 'POST'])
# def login():
#     if request.method == 'POST':
#         username = request.form['username']
#         password = request.form['password']

#         conn = get_connection()
#         cursor = conn.cursor()
#         cursor.execute("SELECT id, password FROM users WHERE username = %s", (username,))
#         user = cursor.fetchone()
#         cursor.close()
#         conn.close()

#         if user and password == user[1]:  # replace with check_password_hash(user[1], password) if you hash
#             session['user_id'] = user[0]
#             session['username'] = username
#             return redirect(url_for('index'))
#         else:
#             flash('Invalid username or password', 'danger')


#         # if user and check_password_hash(user[1], password):
#         #     session['user_id'] = user[0]
#         #     session['username'] = username
#         #     return redirect(url_for('index'))
#         # else:
#         #     flash('Invalid username or password', 'danger')


#     return render_template('login.html')

# @app.route('/logout')
# def logout():
#     session.clear()
#     return redirect(url_for('login'))





# def get_data():
#     conn = get_connection()
#     cursor = conn.cursor()
#     cursor.execute("SELECT * FROM vehicle")
#     data = cursor.fetchall()
#     cursor.close()
#     conn.close()
#     return data


# @app.route('/')
# def index():
#     if 'user_id' not in session:
#         return redirect(url_for('login'))
#     rows = get_data()
#     return render_template('index.html', rows=rows)




# # @app.route('/')
# # def index():
# #     rows = get_data()
# #     return render_template('index.html', rows=rows)

# @app.route('/mark_paid/<int:id>')
# def mark_paid(id):
#     conn = get_connection()
#     cursor = conn.cursor()
#     cursor.execute("UPDATE vehicle SET PaymentStat = 'Paid' WHERE id = %s", (id,))
#     conn.commit()
#     cursor.close()
#     conn.close()
#     return redirect(url_for('index'))

# @app.route("/ticket-scan")
# def ticket_scan():
#     if 'user_id' not in session:
#         return redirect(url_for('login'))
#     return render_template("ticket_scan.html")

# # @app.route("/ticket-scan")
# # def ticket_scan():
# #     return render_template("ticket_scan.html")

# @app.route("/api/vehicle/<id>")
# def get_vehicle(id):
#     conn = get_connection()
#     cursor = conn.cursor()
#     cursor.execute("""
#         SELECT id, NoPol, Image, PaymentStat, CreatedAt, UpdatedAt 
#         FROM vehicle WHERE id = %s
#     """, (id,))
#     row = cursor.fetchone()
#     cursor.close()
#     conn.close()

#     if row:
#         created_at = row[4]
#         now = datetime.now()
#         duration_hours = max((now - created_at).total_seconds() / 3600, 0)
#         fee = round(int(duration_hours * 3000), -3)

#         record = {
#             "id": row[0],
#             "NoPol": row[1],
#             "Image": row[2],
#             "PaymentStat": row[3],
#             "CreatedAt": row[4].strftime("%Y-%m-%d %H:%M:%S"),
#             "UpdatedAt": row[5].strftime("%Y-%m-%d %H:%M:%S") if row[5] else None,
#             "DurationHours": round(duration_hours, 2),
#             "Fee": fee
#         }
#         return jsonify({"success": True, "record": record})
#     else:
#         return jsonify({"success": False, "message": "Vehicle not found"}), 404


# @app.route("/api/vehicle/pay/<id>", methods=["POST"])
# def mark_as_paid(id):
#     conn = get_connection()
#     cursor = conn.cursor()

#     # Get the created time
#     cursor.execute("SELECT CreatedAt FROM vehicle WHERE id = %s", (id,))
#     row = cursor.fetchone()
#     if not row:
#         cursor.close()
#         conn.close()
#         return jsonify({"success": False, "message": "Vehicle not found"}), 404

#     created_at = row[0]
#     updated_at = datetime.now()
#     duration_hours = max((updated_at - created_at).total_seconds() / 3600, 0)
#     fee = round(int(duration_hours * 3000), -3)

#     updated_str = updated_at.strftime("%Y-%m-%d %H:%M:%S")

#     # Update values in database
#     cursor.execute("""
#         UPDATE vehicle
#         SET UpdatedAt = %s, PaymentStat = %s, Fee = %s
#         WHERE id = %s
#     """, (updated_str, "Paid", fee, id))

#     conn.commit()
#     cursor.close()
#     conn.close()

#     return jsonify({
#         "success": True,
#         "updatedAt": updated_str,
#         "durationHours": round(duration_hours, 2),
#         "fee": fee
#     })

# if __name__ == '__main__':
#     app.run(debug=True)






# from flask import Flask, request, render_template, redirect, url_for, jsonify
# from markupsafe import escape
# from datetime import datetime
# import sqlite3
# import math

# app = Flask(__name__)

# def get_data():
#     conn = sqlite3.connect('data.db')
#     cursor = conn.cursor()
#     cursor.execute("SELECT * FROM vehicle")
#     data = cursor.fetchall()
#     conn.close()
#     return data

# @app.route('/')
# def index():
#     rows = get_data()
#     return render_template('index.html', rows=rows)

# if __name__ == '__main__':
#     app.run(debug=True)

# @app.route('/mark_paid/<int:id>')
# def mark_paid(id):
#     conn = sqlite3.connect('data.db')
#     cursor = conn.cursor()
#     cursor.execute("UPDATE vehicle SET PaymentStat = 'Paid' WHERE id = ?", (id,))
#     conn.commit()
#     conn.close()
#     return redirect(url_for('index'))

# @app.route("/ticket-scan")
# def ticket_scan():
#     return render_template("ticket_scan.html")

# @app.route("/api/vehicle/<id>")
# def get_vehicle(id):
#     conn = sqlite3.connect('data.db')
#     cursor = conn.cursor()
#     cursor.execute("SELECT id, NoPol, Image, PaymentStat, CreatedAt, UpdatedAt FROM vehicle WHERE id = ?", (id,))
#     row = cursor.fetchone()
#     conn.close()

#     if row:
#         record = {
#             "id": row[0],
#             "NoPol": row[1],
#             "Image": row[2],
#             "PaymentStat": row[3],
#             "CreatedAt": row[4],
#             "UpdatedAt": row[5]
#         }
#         return jsonify({"success": True, "record": record})
#     else:
#         return jsonify({"success": False, "message": "Vehicle not found"}), 404

# @app.route("/api/vehicle/pay/<id>", methods=["POST"])
# def mark_as_paid(id):
#     conn = sqlite3.connect('data.db')
#     cursor = conn.cursor()

#     # Get the created time
#     cursor.execute("SELECT CreatedAt FROM vehicle WHERE id = ?", (id,))
#     row = cursor.fetchone()
#     if not row:
#         conn.close()
#         return jsonify({"success": False, "message": "Vehicle not found"}), 404

#     created_at = datetime.fromisoformat(row[0])
#     updated_at = datetime.now()
#     duration_hours = max((updated_at - created_at).total_seconds() / 3600, 0)
#     fee = round(int(duration_hours * 3000), -3)  # Rp3000 per hour

#     # Update UpdatedAt, PaymentStat, and Fee
#     updated_str = updated_at.strftime("%Y-%m-%d %H:%M:%S")
#     cursor.execute("""
#         UPDATE vehicle
#         SET UpdatedAt = ?, PaymentStat = ?, Fee = ?
#         WHERE id = ?
#     """, (updated_str, "Paid", fee, id))

#     conn.commit()
#     conn.close()

#     return jsonify({
#         "success": True,
#         "updatedAt": updated_str,
#         "durationHours": round(duration_hours, 2),
#         "fee": fee
#     })
