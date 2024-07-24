        # <!-- <button onclick="location.href='{{ url_for('cctv_dashboard') }}'">View CCTV Camera Dashboard</button> -->



import os
from flask import Flask, render_template, jsonify, request, send_from_directory
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import json
import threading
import cv2
import time
from dotenv import load_dotenv
import matplotlib.pyplot as plt
import numpy as np

load_dotenv()

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploaded_videos'
app.config['ALERTS_FILE'] = 'alerts.json'
app.config['PREVIOUS_ACCIDENTS_FOLDER'] = 'static/accidents'
app.config['GRAPH_FOLDER'] = 'static/graphs'

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['PREVIOUS_ACCIDENTS_FOLDER'], exist_ok=True)
os.makedirs(app.config['GRAPH_FOLDER'], exist_ok=True)

if not os.path.exists(app.config['ALERTS_FILE']):
    with open(app.config['ALERTS_FILE'], 'w') as f:
        json.dump([], f)

def check_for_accident(frame, background_subtractor, min_area=500):
    fg_mask = background_subtractor.apply(frame)
    fg_mask = cv2.threshold(fg_mask, 200, 255, cv2.THRESH_BINARY)[1]
    fg_mask = cv2.dilate(fg_mask, None, iterations=2)
    contours, _ = cv2.findContours(fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for contour in contours:
        if cv2.contourArea(contour) < min_area:
            continue
        return True
    return False

def detect_accidents(video_source=0):
    cap = cv2.VideoCapture(video_source)
    background_subtractor = cv2.createBackgroundSubtractorMOG2(history=500, varThreshold=50, detectShadows=False)
    frame_count = 0
    accident_detected = False
    alert = None

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
        if check_for_accident(frame, background_subtractor):
            if not accident_detected:
                accident_detected = True
                frame_count = 0
                timestamp = time.strftime('%Y-%m-%d_%H-%M-%S')
                alert = {
                    'time': timestamp,
                    'location': '1234 Example St, City, Country',
                    'photos': []
                }
                
            if accident_detected and frame_count < 3:
                photo_path = os.path.join(app.config['PREVIOUS_ACCIDENTS_FOLDER'], f"accident_{timestamp}_{frame_count}.jpg")
                cv2.imwrite(photo_path, frame)
                alert['photos'].append(photo_path)
                frame_count += 1

            if frame_count == 3:
                save_alert(alert)
                threading.Thread(target=send_email_alert, args=(alert,)).start()
                accident_detected = False

        time.sleep(1)
    cap.release()

def send_email_alert(alert):
    smtp_server = 'smtp.gmail.com'
    smtp_port = 587
    sender_email = 'abhishekdubalgonde7846@gmail.com'
    receiver_email = 'zganesh123zade@gmail.com'
    password = 'vmoj nhip imrp wytx'

    subject = "Accident Detected"
    body = f"An accident was detected at {alert['time']}.\nLocation: {alert['location']}"

    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = receiver_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    for photo in alert['photos']:
        with open(photo, 'rb') as attachment:
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(attachment.read())
            encoders.encode_base64(part)
            part.add_header('Content-Disposition', f"attachment; filename= {os.path.basename(photo)}")
            msg.attach(part)

    text = msg.as_string()

    try:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(sender_email, password)
            server.sendmail(sender_email, receiver_email, text)
        print("Email sent successfully")
    except Exception as e:
        print(f"Failed to send email: {e}")

def save_alert(alert):
    try:
        with open(app.config['ALERTS_FILE'], 'r+') as f:
            alerts = json.load(f)
            alerts.append(alert)
            f.seek(0)
            json.dump(alerts, f, indent=4)
    except Exception as e:
        print(f"Error saving alert: {e}")

@app.route('/')
def index():
    try:
        with open(app.config['ALERTS_FILE'], 'r') as f:
            alerts = json.load(f)
    except Exception as e:
        alerts = []
        print(f"Error reading alerts: {e}")
    previous_accidents = os.listdir(app.config['PREVIOUS_ACCIDENTS_FOLDER'])
    return render_template('index.html', alerts=alerts, previous_accidents=previous_accidents)

@app.route('/alerts')
def get_alerts():
    try:
        with open(app.config['ALERTS_FILE'], 'r') as f:
            alerts = json.load(f)
    except Exception as e:
        alerts = []
        print(f"Error reading alerts: {e}")
    return jsonify(alerts)

@app.route('/upload_video', methods=['POST'])
def upload_video():
    if 'video' not in request.files:
        return 'No video part', 400

    file = request.files['video']
    if file.filename == '':
        return 'No selected file', 400

    file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
    file.save(file_path)
    
    threading.Thread(target=detect_accidents, args=(file_path,)).start()
    
    return 'Video uploaded successfully', 200

@app.route('/graph')
def graph_page():
    return render_template('graphical_analysis.html')

@app.route('/cctv_dashboard')
def cctv_dashboard():
    return render_template('cctv_dashboard.html')

@app.route('/generate_graph')
def generate_graph():
    try:
        with open(app.config['ALERTS_FILE'], 'r') as f:
            alerts = json.load(f)
    except Exception as e:
        alerts = []
        print(f"Error reading alerts: {e}")
    
    dates = [alert['time'].split('_')[0] for alert in alerts]
    unique_dates = list(set(dates))
    counts = [dates.count(date) for date in unique_dates]
    
    plt.figure(figsize=(10, 5))
    plt.bar(unique_dates, counts, color='blue')
    plt.xlabel('Date')
    plt.ylabel('Number of Accidents')
    plt.title('Accidents per Day')
    plt.xticks(rotation=45)
    
    graph_path = os.path.join(app.config['GRAPH_FOLDER'], 'accidents_per_day.png')
    plt.savefig(graph_path)
    plt.close()

    return send_from_directory(app.config['GRAPH_FOLDER'], 'accidents_per_day.png')

if __name__ == '__main__':
    app.run(debug=True)
