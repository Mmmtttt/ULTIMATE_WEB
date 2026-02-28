import json
import os

def load_server_config():
    """从配置文件加载服务器配置"""
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'server_config.json')
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

class Config:
    HOST = SERVER_CONFIG.get("backend", {}).get("host", "0.0.0.0")
    PORT = SERVER_CONFIG.get("backend", {}).get("port", 5000)
    DEBUG = True
    
    DATA_DIR = "data"
    PICTURES_DIR = "data/pictures"
    META_DIR = "data/meta_data"
    STATIC_DIR = "static"
    COVER_DIR = "static/cover"
    LOGS_DIR = "logs"
    
    COVER_WIDTH = 800
    COVER_QUALITY = 95
    SUPPORTED_FORMATS = ['.jpg', '.jpeg', '.png', '.webp']
    
    JSON_FILE = "data/meta_data/comics_database.json"
    BACKUP_SUFFIX = ".bkp"
