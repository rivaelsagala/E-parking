from flask import Flask, request, render_template, redirect, url_for, jsonify, session, flash
from markupsafe import escape
from datetime import datetime
import math
import mysql.connector
from werkzeug.security import check_password_hash, generate_password_hash


app = Flask(__name__)
app.secret_key = "supersecretkey"  # Use a strong secret key in production


# Configure your MySQL connection
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': '',
    'database': 'parking_system'
}

def get_connection():
    return mysql.connector.connect(**db_config)



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

        if user and password == user[1]:  # replace with check_password_hash(user[1], password) if you hash
            session['user_id'] = user[0]
            session['username'] = username
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password', 'danger')


        # if user and check_password_hash(user[1], password):
        #     session['user_id'] = user[0]
        #     session['username'] = username
        #     return redirect(url_for('index'))
        # else:
        #     flash('Invalid username or password', 'danger')


    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))





def get_data():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM vehicle")
    data = cursor.fetchall()
    cursor.close()
    conn.close()
    return data


@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    rows = get_data()
    return render_template('index.html', rows=rows)




# @app.route('/')
# def index():
#     rows = get_data()
#     return render_template('index.html', rows=rows)

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

# @app.route("/ticket-scan")
# def ticket_scan():
#     return render_template("ticket_scan.html")

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

    # Get the created time
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

    # Update values in database
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

if __name__ == '__main__':
    app.run(debug=True)






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
