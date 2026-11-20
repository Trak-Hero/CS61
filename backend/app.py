# This is where we share backend entry point (the frontend /api/* here on port 5001).
import os
from flask import Flask, jsonify
from trak_routes import trak_bp

app = Flask(__name__)
app.register_blueprint(trak_bp)

@app.get('/api/health')
def health():
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=int(os.environ.get('BACKEND_PORT', '5001')),
            debug=os.environ.get('FLASK_DEBUG') == '1')
