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
            # Scale to exactly match window size
            scaled_pix = pix.scaled(self.width(), self.height(), 
                                  Qt.AspectRatioMode.IgnoreAspectRatio,  # Changed to IgnoreAspectRatio
                                  Qt.TransformationMode.SmoothTransformation)
            palette = central_widget.palette()
            palette.setBrush(QPalette.Window, QBrush(scaled_pix))
            central_widget.setAutoFillBackground(True)
            central_widget.setPalette(palette)
            print(f"✅ Background image '{bg_path}' loaded successfully.")
        else:
            print(f"⚠️ Warning: Background image '{bg_path}' not found or failed to load.")


        # Layout: two columns (left and right) each with 3 digits
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(40, 40, 40, 10)
        main_layout.setSpacing(0)

        col_style = """
            QLabel {
                color: #ffffff;
                font-weight: bold;
            }
        """

        # Left column
        left_container = QWidget()
        left_layout = QVBoxLayout(left_container)
        left_layout.setSpacing(4)
        left_layout.setAlignment(Qt.AlignBottom)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_container.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Expanding)

        self.left_labels = []
        for i in range(3):
            lbl = QLabel("0")
            # lbl.setAlignment(Qt.AlignCenter)
            lbl.setFont(QFont("Montserrat", 75))
            lbl.setStyleSheet(col_style)
            left_layout.addWidget(lbl)
            self.left_labels.append(lbl)

        # Spacer between columns
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        # Right column
        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)
        right_layout.setSpacing(4)
        right_layout.setAlignment(Qt.AlignBottom)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_container.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Expanding)
        self.right_labels = []
        for i in range(3):
            lbl = QLabel("0")
            lbl.setFont(QFont("Montserrat", 75))
            lbl.setStyleSheet(col_style)
            right_layout.addWidget(lbl)
            self.right_labels.append(lbl)

        main_layout.addWidget(left_container, 0)
        main_layout.addWidget(spacer, 1)
        main_layout.addWidget(right_container, 0)

        # Keep dark palette applied from main()
        self.showFullScreen()

    def setup_signals(self):
        self.signals.digits_received.connect(self.update_digits_display)
        self.signals.status_update.connect(lambda s: None)

    def calculate_speed(self, column, current_rotations):
        current_time = time.time()
        prev_rot = self.prev_rotations[column]
        prev_time = self.prev_time[column]
        
        if prev_rot == 0:  # First measurement
            speed = 0
            path_increment = 0
        else:
            # Calculate rotations difference
            rotations_diff = current_rotations - prev_rot
            # Calculate path increment in meters
            path_increment = (rotations_diff * self.CIRCLE_LENGTH) / 100  # Convert cm to meters
            # Calculate time difference in seconds
            time_diff = current_time - prev_time
            # Calculate speed in cm/s
            speed = (path_increment * 100) / time_diff if time_diff > 0 else 0
            # Convert to km/h
            speed = (speed * 3.6)  # Convert m/s to km/h
        
        # Update total path
        if self.active_timers[column]:
            self.total_path[column] += path_increment
        
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
                    labels[2].setText(f"{self.total_path[column]:.1f}")
            elif not self.active_timers[column]:
                # Show 00:00:00 when timer is not active
                labels = self.left_labels if column == '1' else self.right_labels
                if len(labels) > 1:
                    labels[1].setText("00:00:00")
                    labels[2].setText("0.0")


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
                background: rgba(255,255,255,0.08);
                border-radius: 8px;
                padding: 12px;
                min-width: 10;
                min-height: 10px;
                font-weight: bold;
            }
        """
        normal_style = """
            QLabel {
                color: #ffffff;
                background: rgba(0,0,0,0.4);
                border-radius: 8px;
                padding: 12px;
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
    window.show()
    
    print("🎯 GUI Application started!")
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()