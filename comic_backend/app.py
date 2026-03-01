from flask import Flask
from flask_cors import CORS
from api import register_blueprints
from infrastructure.logger import app_logger
from application.list_app_service import ListAppService
from infrastructure.backup_manager import init_backup_system, shutdown_backup_system
import json
import os
import atexit


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


def init_default_data():
    try:
        list_service = ListAppService()
        list_service.ensure_default_list()
        app_logger.info("默认清单初始化完成")
    except Exception as e:
        app_logger.error(f"初始化默认清单失败: {e}")


def init_backup():
    """初始化定时备份系统"""
    try:
        init_backup_system()
        # 注册退出时关闭备份系统
        atexit.register(shutdown_backup_system)
        app_logger.info("定时备份系统初始化完成")
    except Exception as e:
        app_logger.error(f"初始化定时备份系统失败: {e}")


def success_response(data=None):
    return {
        "code": 200,
        "msg": "成功",
        "data": data
    }


if __name__ == '__main__':
    init_default_data()
    init_backup()
    app_logger.info(f"启动服务器，地址: {HOST}:{PORT}")
    app.run(host=HOST, port=PORT, debug=DEBUG)
