`import sys
import requests
import threading
import json, time
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                               QHBoxLayout, QLabel, QPushButton, QTextEdit, 
                               QGroupBox, QFrame, QSizePolicy)
from PySide6.QtCore import QTimer, Qt, Signal, QObject
from PySide6.QtGui import QFont, QPalette, QColor, QPixmap, QBrush

# Signal class for thread-safe GUI updates
class DigitSignals(QObject):
    digits_received = Signal(list)
    status_update = Signal(str)

class DigitDisplayGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.signals = DigitSignals()
        self.current_digits_left = [0, 0, 0]
        self.current_digits_right = [0, 0, 0]
        self.paused = {'1': False, '2': False}
        self.elapsed_acc = {'1': 0.0, '2': 0.0}
        self.prev_rotations = {'1': None, '2': None}
        self.total_path = {'1': 0.0, '2': 0.0}  # Track total path for each column (km)
        self.prev_time = {'1': None, '2': None}
        self.CIRCLE_LENGTH = 20  # cm
        self.zero_since = {'1': None, '2': None}
        self.current_speed = {'1': 0, '2': 0}
        self.server_url = "http://localhost:65500/api/data"
        self.start_times = {'1': None, '2': None}  # Track start times for each column
        self.active_timers = {'1': False, '2': False}  # Track if timers are running
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_timers)
        self.timer.start(100)  # Update every 100ms
        self.init_ui()
        self.setup_signals()
        self.start_data_polling()

    def init_ui(self):
        self.setWindowTitle("Digit Display")
        self.setGeometry(0, 0, 1920, 1080)

        # Central widget with background image
        central_widget = QWidget()
        central_widget.setObjectName("central")
        self.setCentralWidget(central_widget)

        bg_path = "bg.png"
        # Prefer using QPixmap + palette to set a background image (more reliable than stylesheet here)
        pix = QPixmap(bg_path)
        if not pix.isNull():
            # Create a proper scaled background that fills the screen exactly once
            pix = pix.scaled(self.width(), self.height(), 
                                Qt.AspectRatioMode.IgnoreAspectRatio,  
                                Qt.TransformationMode.SmoothTransformation)
            
            # Set background as a stylesheet instead of palette
            central_widget.setStyleSheet(f"""
                QWidget#central {{
                    background-image: url({bg_path});
                    background-position: center;
                    background-repeat: no-repeat;
                    background-size: cover;
                }}
            """)
            print(f"✅ Background image '{bg_path}' loaded successfully.")
        else:
            print(f"⚠️ Warning: Background image '{bg_path}' not found or failed to load.")


        # Style for labels
        label_style = """
            QLabel {
                color: #ffffff;
                font-weight: bold;
            }
        """

        # Create labels with absolute positioning
        self.left_labels = []
        self.right_labels = []
        
        # Coordinates for left column (x, y positions)
        left_positions = [
            (620, 705),  # First digit (speed)
            (170, 125),  # Second digit (timer)
            (100, 705)   # Third digit (path)
        ]
        
        # Coordinates for right column
        right_positions = [
            (1075, 705),  # First digit (speed)
            (1050, 125),  # Second digit (timer)
            (1475, 705)   # Third digit (path)
        ]

        # Create and position left labels
        for _, pos in enumerate(left_positions):
            lbl = QLabel("0", central_widget)
            lbl.setFont(QFont("Montserrat", 150))
            lbl.setStyleSheet(label_style)
            lbl.setGeometry(pos[0], pos[1], 700, 125)  # x, y, width, height
            self.left_labels.append(lbl)

        # Create and position right labels
        for _, pos in enumerate(right_positions):
            lbl = QLabel("0", central_widget)
            lbl.setFont(QFont("Montserrat", 150))
            lbl.setStyleSheet(label_style)
            lbl.setGeometry(pos[0], pos[1], 700, 125)  # x, y, width, height
            self.right_labels.append(lbl)

        self.show()

    def setup_signals(self):
        self.signals.digits_received.connect(self.update_digits_display)
        self.signals.status_update.connect(lambda s: None)

    def calculate_speed(self, column, current_rotations):
        # use monotonic clock for interval measurement
        current_time = time.monotonic()
        prev_rot = self.prev_rotations[column]
        prev_time = self.prev_time[column]

        # first sample: just store state and return 0
        if prev_rot is None or prev_time is None:
            self.prev_rotations[column] = current_rotations
            self.prev_time[column] = current_time
            return 0.0

        # compute rotation delta
        rotations_diff = current_rotations - prev_rot
        if rotations_diff <= 0:
            # no forward progress -> speed 0, do not advance prev_time so subsequent real change uses older timestamp
            self.prev_rotations[column] = current_rotations
            return 0.0

        # distance in km (CIRCLE_LENGTH in cm -> 100000 cm = 1 km)
        path_increment_km = (rotations_diff * self.CIRCLE_LENGTH) / 100000.0

        # time diff; protect against tiny diffs
        time_diff = current_time - prev_time
        if time_diff < 1e-3:
            time_diff = 1e-3

        speed = (path_increment_km / time_diff) * 3600.0  # km/h

        # update totals only when timer is active and not paused
        if self.active_timers[column] and not self.paused[column]:
            self.total_path[column] = round(self.total_path[column] + path_increment_km, 3)

        # update previous state
        self.prev_rotations[column] = current_rotations
        self.prev_time[column] = current_time
        return round(speed, 1)
    
    def update_timers(self):
        current_time = time.time()
        
        for column in ['1', '2']:
            # Only update display if timer was ever started for this column
            if self.active_timers[column]:
                # Determine elapsed without advancing when paused
                if self.paused[column]:
                    elapsed = int(self.elapsed_acc[column])
                else:
                    # running: accumulated + current interval
                    if self.start_times[column] is not None:
                        elapsed = int(self.elapsed_acc[column] + (current_time - self.start_times[column]))
                    else:
                        elapsed = int(self.elapsed_acc[column])

                # Use last calculated speed for this column
                speed = self.current_speed[column]

                # If speed is zero, start/keep a zero-timer; pause only after >2s
                if speed == 0:
                    if self.zero_since[column] is None:
                        self.zero_since[column] = current_time
                    if (current_time - self.zero_since[column]) > 2.0:
                        # pause the timer (lock it), preserve elapsed_acc
                        if not self.paused[column]:
                            # accumulate current running interval before pausing
                            if self.start_times[column] is not None:
                                self.elapsed_acc[column] += (current_time - self.start_times[column])
                                self.start_times[column] = None
                            self.paused[column] = True
                        # elapsed remains the accumulated value
                        elapsed = int(self.elapsed_acc[column])
                else:
                    # speed > 0: clear zero timer and resume if paused
                    self.zero_since[column] = None
                    if self.paused[column]:
                        # resume: mark new start time, do not reset elapsed_acc
                        self.start_times[column] = current_time
                        self.paused[column] = False

                # Format time as HH:MM:SS
                time_str = self.format_time(elapsed)
                
                # Update the second digit (timer) and third digit (path)
                labels = self.left_labels if column == '1' else self.right_labels
                if len(labels) > 1:
                    labels[1].setText(time_str)
                    labels[2].setText(f"{self.total_path[column]:.2f}")
            else:
                # Timer was never started: show zeros
                labels = self.left_labels if column == '1' else self.right_labels
                if len(labels) > 1:
                    labels[1].setText("00:00:00")
                    labels[2].setText("0.00")


    def format_time(self, total_seconds):
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


    def update_digits_display(self, data):
        try:
            column = str(data[0])  # '1' for left, '2' for right
            rotations = data[1]
            
            if column not in ('1', '2'):
                return
                
            speed = self.calculate_speed(column, rotations)
            
            # store last computed speed so update_timers can use it
            self.current_speed[column] = speed

            # if speed > 0 ensure timer is started or resumed
            if speed > 0:
               self.zero_since[column] = None
               if not self.active_timers[column]:
                   # start new timer
                   self.start_times[column] = time.time()
                   self.elapsed_acc[column] = 0.0
                   self.paused[column] = False
                   self.active_timers[column] = True
               elif self.paused[column]:
                   # resume paused timer
                   self.start_times[column] = time.time()
                   self.paused[column] = False

            # Update the appropriate column
            labels = self.left_labels if column == '1' else self.right_labels
            
            # Update speed (first digit)
            if labels:
                labels[0].setText(f"{speed}")
            
            # Update internal tracking
            # self.prev_rotations[column] = rotations
            self.flash_digit_background()
            
        except Exception as e:
            print(f"Error updating display: {e}")

    def flash_digit_background(self):
        flash_style = """
            QLabel {
                color: #ffffff;
                min-width: 10;
                min-height: 10px;
                font-weight: bold;
            }
        """
        normal_style = """
            QLabel {
                color: #ffffff;
                min-width: 10px;
                min-height: 10px;
                font-weight: bold;
            }
        """
        for lbl in self.left_labels + self.right_labels:
            lbl.setStyleSheet(flash_style)
        QTimer.singleShot(180, lambda: [lbl.setStyleSheet(normal_style) for lbl in self.left_labels + self.right_labels])

    def start_data_polling(self):
        self.poll_timer = QTimer()
        self.poll_timer.timeout.connect(self.fetch_latest_data)
        self.poll_timer.start(1000)

    def fetch_latest_data(self):
        def fetch_thread():
            try:
                response = requests.get(self.server_url, timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    latest_map = data.get('data', {})
                    # emit each column's latest digits if present
                    for col_key in ('1', '2'):
                        entry = latest_map.get(col_key)
                        if entry and 'digits' in entry:
                            self.signals.digits_received.emit(entry['digits'])
                    self.signals.status_update.emit("ok")
            except requests.exceptions.RequestException:
                pass

        thread = threading.Thread(target=fetch_thread)
        thread.daemon = True
        thread.start()

    def clear_display(self):
        self.current_digits = [0, 0, 0]
        for lbl in self.left_labels + self.right_labels:
            lbl.setText("0")

def main():
    # Create the Flask server in a separate thread
    def start_flask_server():
        from flask import Flask, request, jsonify
        
        app = Flask(__name__)
        # store latest per column ('1' and '2')
        last_by_column = {}
        
        @app.route('/api/data', methods=['POST'])
        def receive_data():
            try:
                data = request.get_json()
                digits = data.get('digits', [])
                
                if len(digits) == 2 and all(isinstance(x, (int, float)) for x in digits):
                    # normalize column key as string '1' or '2'
                    col_key = str(int(digits[0]))
                    last_by_column[col_key] = {
                        'digits': [int(digits[0]), float(digits[1])],
                        'timestamp': time.time()
                    }
                    print(f"📨 Received digits for column {col_key}: {digits}")
                    return jsonify({'status': 'success', 'received_digits': digits})
                else:
                    return jsonify({'error': 'Invalid data format'}), 400
                    
            except Exception as e:
                return jsonify({'error': str(e)}), 500
        
        @app.route('/api/data', methods=['GET'])
        def get_data():
            # return the latest per column ('1' and '2')
            return jsonify({
                'total_received': len(last_by_column),
                'data': last_by_column
            })
        
        @app.route('/')
        def home():
            return '''
            <h1>Digit Receiver Server</h1>
            <p>Send POST requests to /api/data with JSON:</p>
            <pre>{"digits": [1, 2, 3]}</pre>
            <p><a href="/api/data">View received data</a></p>
            '''
        
        print("🚀 Starting Flask server on http://localhost:65500")
        app.run(host='0.0.0.0', port=65500, debug=False, use_reloader=False)
    
    # Start Flask server in background thread
    server_thread = threading.Thread(target=start_flask_server)
    server_thread.daemon = True
    server_thread.start()
    
    # Start the GUI application
    app = QApplication(sys.argv)
    
    # Set application-wide dark palette
    dark_palette = QPalette()
    dark_palette.setColor(QPalette.Window, QColor(43, 43, 43))
    dark_palette.setColor(QPalette.WindowText, Qt.white)
    dark_palette.setColor(QPalette.Base, QColor(25, 25, 25))
    dark_palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
    dark_palette.setColor(QPalette.ToolTipBase, Qt.white)
    dark_palette.setColor(QPalette.ToolTipText, Qt.white)
    dark_palette.setColor(QPalette.Text, Qt.white)
    dark_palette.setColor(QPalette.Button, QColor(53, 53, 53))
    dark_palette.setColor(QPalette.ButtonText, Qt.white)
    dark_palette.setColor(QPalette.BrightText, Qt.red)
    dark_palette.setColor(QPalette.Link, QColor(42, 130, 218))
    dark_palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
    dark_palette.setColor(QPalette.HighlightedText, Qt.black)
    app.setPalette(dark_palette)
    
    window = DigitDisplayGUI()
    # window.setScreen(app.screens()[1])  # Set to second monitor if available
    # screen = window.screen()

    # window.move(screen.geometry().topLeft())
    window.showFullScreen()
    print("🎯 GUI Application started!")
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()