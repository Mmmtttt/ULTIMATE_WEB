from flask import Flask
from flask_cors import CORS
from api import register_blueprints
from infrastructure.logger import app_logger
import json
import os


def load_server_config():
    config_path = os.path.join(os.path.dirname(__file__), '..', 'server_config.json')
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "backend": {"host": "0.0.0.0", "port": 5000},
        "frontend": {"host": "0.0.0.0", "port": 5173}
    }


SERVER_CONFIG = load_server_config()
HOST = SERVER_CONFIG.get("backend", {}).get("host", "0.0.0.0")
PORT = SERVER_CONFIG.get("backend", {}).get("port", 5000)
DEBUG = True

app = Flask(__name__)
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 300

CORS(app)

register_blueprints(app)

app.static_folder = 'static'


@app.route('/')
def index():
    return "Comic Backend API"


@app.route('/health')
def health():
    return success_response({"status": "ok"})


def success_response(data=None):
    return {
        "code": 200,
        "msg": "成功",
        "data": data
    }


if __name__ == '__main__':
    app_logger.info(f"启动服务器，地址: {HOST}:{PORT}")
    app.run(host=HOST, port=PORT, debug=DEBUG)
