import sys
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
        self.prev_rotations = {'1': 0, '2': 0}  # Track for both columns
        self.total_path = {'1': 0, '2': 0}  # Track total path for each column
        self.prev_time = {'1': time.time(), '2': time.time()}
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
        current_time = time.time()
        prev_rot = self.prev_rotations[column]
        prev_time = self.prev_time[column]
        
        if prev_rot == 0:  # First measurement
            speed = 0
            path_increment_km = 0.00
        else:
            # Calculate rotations difference
            rotations_diff = current_rotations - prev_rot
            # Calculate path increment in kilometers
            # CIRCLE_LENGTH is in cm -> 100000 cm in 1 km
            path_increment_km = (rotations_diff * self.CIRCLE_LENGTH) / 100000.0
            # Calculate time difference in seconds
            time_diff = current_time - prev_time
            # Calculate speed in km/h
            speed = (path_increment_km / time_diff) * 3600.0 if time_diff > 0 else 0.00
        
        # Update total path in km, keep accuracy to 2 decimal places
        if self.active_timers[column]:
            self.total_path[column] = round(self.total_path[column] + path_increment_km, 3)
            self.total_path[column] = round(self.total_path[column], 3)  # Keep as float with 3 decimal places
        
        # Update previous values
        self.prev_rotations[column] = current_rotations
        self.prev_time[column] = current_time
        return round(speed, 1)
    
    def update_timers(self):
        current_time = time.time()
        
        for column in ['1', '2']:
            if self.active_timers[column] and self.start_times[column]:
                elapsed = int(current_time - self.start_times[column])
                
                # Use last calculated speed for this column
                speed = self.current_speed[column]
                # Reset only this column if its speed is 0
                if speed == 0:
                    if self.zero_since[column] is None:
                        self.zero_since[column] = current_time
                    # reset only when zero persisted longer than 2 seconds
                    if (current_time - self.zero_since[column]) > 2.0:
                        elapsed = 0
                        self.active_timers[column] = False
                        self.start_times[column] = None
                        self.total_path[column] = 0  # Reset path when timer resets
                        # keep zero_since as timestamp (or clear) -- clear to allow re-trigger later
                        self.zero_since[column] = None
                else:
                    # speed > 0: clear any zero timer
                    self.zero_since[column] = None
                
                # Format time as HH:MM:SS
                time_str = self.format_time(elapsed)
                
                # Update the second digit (timer) and third digit (path)
                labels = self.left_labels if column == '1' else self.right_labels
                if len(labels) > 1:
                    labels[1].setText(time_str)
                    labels[2].setText(f"{self.total_path[column]:.2f}")
            elif not self.active_timers[column]:
                # Show 00:00:00 when timer is not active
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

            if speed > 0:
               self.zero_since[column] = None

            # Update the appropriate column
            labels = self.left_labels if column == '1' else self.right_labels
            
            # Update speed (first digit)
            if labels:
                labels[0].setText(f"{speed}")
            
            # Start/restart timer if speed changed
            if speed > 0:
                if not self.active_timers[column]:
                    self.start_times[column] = time.time()
                    self.active_timers[column] = True
            
            # Update internal tracking
            self.prev_rotations[column] = rotations
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