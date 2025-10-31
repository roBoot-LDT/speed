# from flask import Flask, request, jsonify

# app = Flask(__name__)

# # Store received data
# received_data = []

# @app.route('/api/data', methods=['POST'])
# def receive_data():
#     try:
#         data = request.get_json()
        
#         # Validate the data
#         if not data or 'digits' not in data:
#             return jsonify({'error': 'No digits provided'}), 400
        
#         digits = data['digits']
        
#         # Validate it's a list of 3 digits
#         if not isinstance(digits, list) or len(digits) != 3:
#             return jsonify({'error': 'Must be a list of exactly 3 digits'}), 400
        
#         if not all(isinstance(x, (int, float)) for x in digits):
#             return jsonify({'error': 'All elements must be numbers'}), 400
        
#         # Store the data
#         received_data.append({
#             'digits': digits,
#             'timestamp': '...'  # You can add datetime here if needed
#         })
        
#         print(f"Received digits: {digits}")
        
#         return jsonify({
#             'status': 'success',
#             'message': 'Data received successfully',
#             'received_digits': digits
#         }), 200
        
#     except Exception as e:
#         return jsonify({'error': str(e)}), 500

# @app.route('/api/data', methods=['GET'])
# def get_data():
#     return jsonify({
#         'total_received': len(received_data),
#         'data': received_data
#     })

# @app.route('/')
# def home():
#     return '''
#     <h1>Data Receiver Server</h1>
#     <p>Send POST requests to /api/data with JSON:</p>
#     <pre>{"digits": [1, 2, 3]}</pre>
#     <p><a href="/api/data">View received data</a></p>
#     '''

# if __name__ == '__main__':
#     print("Server starting... Awaiting data on http://localhost:5000/api/data")
#     app.run(host='0.0.0.0', port=5000, debug=True)