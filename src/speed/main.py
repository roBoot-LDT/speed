import sys
import requests
import threading
import json
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
        self.current_digits = [0, 0, 0]
        self.server_url = "http://localhost:5000/api/data"
        self.init_ui()
        self.setup_signals()
        self.start_data_polling()

    def init_ui(self):
        self.setWindowTitle("Digit Display")
        self.setGeometry(100, 100, 1920, 1080)

        # Central widget with background image
        central_widget = QWidget()
        central_widget.setObjectName("central")
        self.setCentralWidget(central_widget)

        bg_path = "/home/nemkov/projects/speed/image.png"
        # Prefer using QPixmap + palette to set a background image (more reliable than stylesheet here)
        pix = QPixmap(bg_path)
        if not pix.isNull():
            palette = central_widget.palette()
            palette.setBrush(QPalette.Window, QBrush(pix))
            central_widget.setAutoFillBackground(True)
            central_widget.setPalette(palette)
        else:
            # Fallback to stylesheet (use file:/// absolute URL)
            central_widget.setStyleSheet(
                "QWidget#central {"
                f'background-image: url("file:///{bg_path}");'
                "background-position: center;"
                "background-repeat: no-repeat;"
                "background-attachment: fixed;"
                "}"
            )

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
            lbl.setFont(QFont("Arial", 75))
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
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setFont(QFont("Arial", 75))
            lbl.setStyleSheet(col_style)
            right_layout.addWidget(lbl)
            self.right_labels.append(lbl)

        main_layout.addWidget(left_container, 0)
        main_layout.addWidget(spacer, 1)
        main_layout.addWidget(right_container, 0)

        # Keep dark palette applied from main()
        self.show()

    def setup_signals(self):
        self.signals.digits_received.connect(self.update_digits_display)
        self.signals.status_update.connect(lambda s: None)

    def update_digits_display(self, digits):
        # Expect digits to be a list of 3 items. Show them in both columns.
        if not digits or len(digits) < 3:
            return

        self.current_digits = digits[:3]
        for i, val in enumerate(self.current_digits):
            self.left_labels[i].setText(str(val))
            self.right_labels[i].setText(str(val))

        self.flash_digit_background()

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
                    if data.get('data') and len(data['data']) > 0:
                        latest_digits = data['data'][-1]['digits']
                        self.signals.digits_received.emit(latest_digits)
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
        received_data = []
        
        @app.route('/api/data', methods=['POST'])
        def receive_data():
            try:
                data = request.get_json()
                digits = data.get('digits', [])
                
                if len(digits) == 3 and all(isinstance(x, (int, float)) for x in digits):
                    received_data.append({
                        'digits': digits,
                        'timestamp': 'real-time'
                    })
                    print(f"📨 Received digits: {digits}")
                    return jsonify({'status': 'success', 'received_digits': digits})
                else:
                    return jsonify({'error': 'Invalid data format'}), 400
                    
            except Exception as e:
                return jsonify({'error': str(e)}), 500
        
        @app.route('/api/data', methods=['GET'])
        def get_data():
            return jsonify({
                'total_received': len(received_data),
                'data': received_data
            })
        
        @app.route('/')
        def home():
            return '''
            <h1>Digit Receiver Server</h1>
            <p>Send POST requests to /api/data with JSON:</p>
            <pre>{"digits": [1, 2, 3]}</pre>
            <p><a href="/api/data">View received data</a></p>
            '''
        
        print("🚀 Starting Flask server on http://localhost:5000")
        app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
    
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
    print("💡 Use the 'Send Test Data' button to test the real-time display")
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()