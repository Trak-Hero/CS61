
# forwards api to backend
#run by "pip install flask requests" and then "BACKEND_URL=http://localhost:5001 python app.py" or wtv localhost is
# will be on my http://localhost:8000
import os
import requests
from flask import Flask, Response, request, send_file

BACKEND = os.environ.get("BACKEND_URL", "http://localhost:5001").rstrip("/")
FORWARD = {"content-type", "x-role", "x-student-id"}
app = Flask(__name__)


@app.get("/")
def index():
    return send_file(os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html"))

@app.route("/api/<path:path>", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
def proxy(path):
    try:
        r = requests.request(request.method, f"{BACKEND}/api/{path}", params=request.args, data=request.get_data(), timeout=10,
        headers={k: v for k, v in request.headers if k.lower() in FORWARD})
    except requests.RequestException:
        return {"error": f"Backend unreachable at {BACKEND}"}, 502
    return Response(r.content, r.status_code, content_type=r.headers.get("Content-Type", "application/json"))


if __name__ == "__main__":
    app.run(port=int(os.environ.get("PORT", 8000)), debug=True)
