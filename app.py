from flask import Flask, Response, render_template_string, request
import cv2
import pytesseract
import os
import serial
import time
from datetime import datetime
from threading import Thread
import atexit

# Konfigurasi path tesseract untuk Windows
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# Konfigurasi Serial untuk Arduino
# Variabel global untuk arduino
arduino = None
arduino_connected = False

def connect_arduino():
    global arduino, arduino_connected
    try:
        # Tutup koneksi yang mungkin masih terbuka
        if arduino is not None:
            try:
                arduino.close()
                time.sleep(1)  # Beri waktu untuk melepaskan port
            except:
                pass
        
        # Ganti 'COM4' dengan port Arduino Anda (misal: 'COM5' pada Windows atau '/dev/ttyUSB0' pada Linux)
        arduino = serial.Serial('COM4', 9600, timeout=1, write_timeout=1)
        arduino_connected = True
        print("Arduino terhubung!")
        # Beri waktu Arduino untuk reset setelah koneksi serial
        time.sleep(2)
    except Exception as e:
        arduino_connected = False
        print(f"PERINGATAN: Arduino tidak terhubung! Error: {str(e)}")
        
        # Coba solusi untuk error izin akses
        if "Access is denied" in str(e):
            print("Solusi yang disarankan:")
            print("1. Pastikan tidak ada program lain yang menggunakan port COM4")
            print("2. Coba cabut dan colok kembali Arduino")
            print("3. Periksa Device Manager untuk memastikan COM4 adalah port Arduino yang benar")
            print("4. Restart komputer jika masalah berlanjut")

# Fungsi untuk membersihkan koneksi Arduino saat program berakhir
def cleanup_arduino():
    global arduino, arduino_connected
    if arduino_connected and arduino:
        try:
            arduino.close()
            print("Koneksi Arduino ditutup dengan bersih")
        except:
            pass

# Register cleanup function to be called on exit
atexit.register(cleanup_arduino)

# Coba koneksi Arduino di awal
connect_arduino()

app = Flask(__name__)
camera = None  # Akan diinisialisasi nanti

# Coba inisialisasi kamera
def init_camera():
    global camera
    try:
        camera = cv2.VideoCapture(1)  # Coba kamera kedua (eksternal)
        if not camera.isOpened():
            print("Kamera eksternal (index 1) tidak terdeteksi, mencoba kamera bawaan...")
            camera = cv2.VideoCapture(0)  # Coba kamera pertama (bawaan)
            
        if not camera.isOpened():
            print("PERINGATAN: Tidak ada kamera yang terdeteksi!")
        else:
            print(f"Kamera berhasil diinisialisasi (index: {'1' if camera.get(cv2.CAP_PROP_POS_FRAMES) >= 0 else '0'})")
    except Exception as e:
        print(f"Error saat menginisialisasi kamera: {str(e)}")

# Inisialisasi kamera
init_camera()

last_frame = None
ocr_result = ""
gate_status = "TERTUTUP"

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
        .gate-status {
            font-size: 1.5rem;
            margin-top: 20px;
            padding: 10px;
            border-radius: 5px;
            text-align: center;
            font-weight: bold;
        }
        .gate-open {
            background-color: #2ecc71;
            color: white;
        }
        .gate-closed {
            background-color: #e74c3c;
            color: white;
        }
        .system-status {
            margin-top: 20px;
            padding: 10px;
            border-radius: 5px;
            text-align: left;
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
        
        function checkGateStatus() {
            fetch('/gate_status')
                .then(response => response.text())
                .then(status => {
                    const statusElement = document.getElementById('gate-status');
                    if (status === 'TERBUKA') {
                        statusElement.className = 'gate-status gate-open';
                        statusElement.textContent = 'Status Gerbang: TERBUKA';
                    } else {
                        statusElement.className = 'gate-status gate-closed';
                        statusElement.textContent = 'Status Gerbang: TERTUTUP';
                    }
                });
        }

        function checkArduinoStatus() {
            fetch('/arduino_status')
                .then(response => response.text())
                .then(status => {
                    const statusElement = document.getElementById('arduino-status');
                    if (status === 'connected') {
                        statusElement.innerHTML = '<span class="badge bg-success">Arduino Terhubung</span>';
                    } else {
                        statusElement.innerHTML = '<span class="badge bg-danger">Arduino Tidak Terhubung</span>';
                    }
                });
        }
        
        setInterval(updateClock, 1000);
        setInterval(checkGateStatus, 1000);
        setInterval(checkArduinoStatus, 5000);
        
        window.onload = function() {
            updateClock();
            checkGateStatus();
            checkArduinoStatus();
        };
    </script>
</head>
<body class="bg-light">
    <div class="container py-5">
        <h1 class="text-center mb-5">🚘 Sistem E-Parking</h1>
        <div class="row">
            <div class="col-md-6 text-center">
                <img src="{{ url_for('video_feed') }}" class="img-fluid rounded border mb-3" style="max-height: 480px;">
                <form method="POST" action="/scan" class="d-flex justify-content-center gap-3">
                    <button type="submit" class="btn btn-lg btn-success">Pesan Tiket</button>
                    <a href="/bantuan" class="btn btn-lg btn-danger">Bantuan</a>
                </form>
                <div id="gate-status" class="gate-status gate-closed mt-3">
                    Status Gerbang: TERTUTUP
                </div>
                <div class="system-status mt-3">
                    <div id="arduino-status">
                        <span class="badge bg-secondary">Memeriksa Arduino...</span>
                    </div>
                    <div class="mt-2">
                        <a href="/test_connection" class="btn btn-sm btn-primary">Tes Koneksi</a>
                        <a href="/open_gate" class="btn btn-sm btn-warning">Buka Gerbang Manual</a>
                    </div>
                </div>
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

def open_gate_with_timer():
    global gate_status, arduino, arduino_connected
    
    if not arduino_connected:
        print("Mencoba untuk menghubungkan ke Arduino...")
        connect_arduino()
    
    if arduino_connected:
        try:
            # Kirim perintah ke Arduino untuk membuka gerbang
            arduino.write(b'OPEN\n')
            gate_status = "TERBUKA"
            print("Gerbang dibuka")
            
            # Tunggu 10 detik
            time.sleep(10)
            
            # Kirim perintah untuk menutup gerbang
            arduino.write(b'CLOSE\n')
            gate_status = "TERTUTUP"
            print("Gerbang ditutup")
        except Exception as e:
            print(f"Error saat mengoperasikan gerbang: {str(e)}")
            # Coba koneksi ulang jika terjadi error
            arduino_connected = False
            gate_status = "TERTUTUP"
    else:
        print("Arduino tidak terhubung. Gerbang tidak dapat dioperasikan.")

@app.route('/')
def index():
    return render_template_string(HTML_PAGE, text=ocr_result)

@app.route('/bantuan')
def bantuan():
    return render_template_string('''
        <!doctype html>
        <html lang="en">
        <head>
            <title>Bantuan - E-Parking</title>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        </head>
        <body class="bg-light">
            <div class="container py-5">
                <h1 class="text-center mb-5">Bantuan Sistem E-Parking</h1>
                <div class="card p-4">
                    <h2>Cara Menggunakan Sistem</h2>
                    <ol>
                        <li>Posisikan kendaraan Anda di depan kamera</li>
                        <li>Klik tombol "Pesan Tiket" untuk mendapatkan tiket dan membuka gerbang</li>
                        <li>Gerbang akan otomatis terbuka selama 10 detik</li>
                        <li>Masuk ke area parkir sebelum gerbang tertutup</li>
                    </ol>
                    <h2 class="mt-4">Kontak</h2>
                    <p>Jika mengalami masalah, silakan hubungi petugas parkir atau hubungi nomor berikut: 0812-3456-7890</p>
                    <div class="text-center mt-4">
                        <a href="/" class="btn btn-primary">Kembali ke Halaman Utama</a>
                    </div>
                </div>
            </div>
        </body>
        </html>
    ''')

def generate_frames():
    global last_frame, camera
    
    # Periksa apakah kamera sudah diinisialisasi
    if camera is None or not camera.isOpened():
        # Coba inisialisasi ulang kamera
        init_camera()
        
        # Jika masih tidak bisa, kembalikan frame kosong
        if camera is None or not camera.isOpened():
            # Buat frame kosong berwarna hitam
            black_frame = np.zeros((480, 640, 3), np.uint8)
            text = "Kamera tidak terdeteksi"
            cv2.putText(black_frame, text, (50, 240), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
            
            while True:
                ret, buffer = cv2.imencode('.jpg', black_frame)
                frame_bytes = buffer.tobytes()
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
                time.sleep(1)  # Tidak perlu update terlalu sering
    
    while True:
        try:
            success, frame = camera.read()
            if not success:
                # Jika baca frame gagal, coba reset kamera
                time.sleep(0.5)
                continue
            
            last_frame = frame.copy()
            ret, buffer = cv2.imencode('.jpg', frame)
            frame_bytes = buffer.tobytes()
            
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        except Exception as e:
            print(f"Error saat mengakses kamera: {str(e)}")
            time.sleep(1)  # Jeda sebelum mencoba lagi

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), 
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/gate_status')
def get_gate_status():
    global gate_status
    return gate_status

@app.route('/arduino_status')
def arduino_status():
    global arduino_connected
    return "connected" if arduino_connected else "disconnected"

@app.route('/scan', methods=['POST'])
def scan():
    global ocr_result, last_frame
    
    if last_frame is not None:
        try:
            # Buat direktori untuk menyimpan foto
            os.makedirs("photo", exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"photo/scan_{timestamp}.jpg"
            cv2.imwrite(filename, last_frame)
            
            # Preprocessing
            gray = cv2.cvtColor(last_frame, cv2.COLOR_BGR2GRAY)
            thresh = cv2.adaptiveThreshold(gray, 255,
                                          cv2.ADAPTIVE_THRESH_MEAN_C,
                                          cv2.THRESH_BINARY, 15, 8)
            
            # OCR
            text = pytesseract.image_to_string(thresh, lang='eng')
            ocr_result = text.strip() if text.strip() else "Tidak ada teks terdeteksi."
            
            # Simpan hasil ke file
            with open("hasil.txt", "w", encoding="utf-8") as f:
                f.write(ocr_result)
            
            # Buka gerbang dalam thread terpisah agar tidak mengganggu web server
            gate_thread = Thread(target=open_gate_with_timer)
            gate_thread.daemon = True
            gate_thread.start()
        except Exception as e:
            ocr_result = f"Error saat pemrosesan gambar: {str(e)}"
            print(ocr_result)
    else:
        ocr_result = "Tidak ada gambar dari kamera."
    
    return render_template_string(HTML_PAGE, text=ocr_result)

@app.route('/open_gate', methods=['GET'])
def open_gate():
    gate_thread = Thread(target=open_gate_with_timer)
    gate_thread.daemon = True
    gate_thread.start()
    return "Perintah untuk membuka gerbang dikirim!"

@app.route('/test_connection', methods=['GET'])
def test_connection():
    global arduino_connected
    if arduino_connected:
        try:
            # Kirim perintah test ke Arduino
            arduino.write(b'TEST\n')
            time.sleep(0.5)
            response = arduino.readline().decode('utf-8').strip()
            if response == "OK":
                return "Arduino terhubung dan merespon dengan baik!"
            else:
                return f"Arduino terhubung tapi responsnya tidak sesuai: {response}"
        except Exception as e:
            arduino_connected = False
            return f"Error saat komunikasi dengan Arduino: {str(e)}"
    else:
        connect_arduino()
        if arduino_connected:
            return "Arduino berhasil terhubung setelah mencoba ulang!"
        else:
            return "Arduino tidak dapat dihubungkan. Periksa koneksi dan port serial."

if __name__ == '__main__':
    import numpy as np  # Import numpy untuk frame kosong jika kamera tidak terdeteksi
    
    # Gunakan threaded=False untuk menghindari masalah dengan koneksi serial di threads berbeda
    try:
        # Menggunakan use_reloader=False untuk menghindari masalah dengan koneksi serial saat reloading
        app.run(debug=True, host='0.0.0.0', port=5000, threaded=True, use_reloader=False)
    finally:
        # Pastikan kamera dilepas saat program berakhir
        if camera is not None:
            camera.release()
        # Pastikan koneksi Arduino ditutup
        cleanup_arduino()