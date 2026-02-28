from flask import Flask
from flask_cors import CORS
from config import Config
from routes import register_blueprints
from utils.logger import app_logger

# 创建Flask应用
app = Flask(__name__)

# 配置CORS
CORS(app)

# 注册蓝图
register_blueprints(app)

# 静态文件配置
app.static_folder = 'static'

@app.route('/')
def index():
    """根路径"""
    return "Comic Backend API"

@app.route('/health')
def health():
    """健康检查"""
    return success_response({"status": "ok"})

def success_response(data=None):
    """成功响应"""
    return {
        "code": 200,
        "msg": "成功",
        "data": data
    }

if __name__ == '__main__':
    app_logger.info(f"启动服务器，地址: {Config.HOST}:{Config.PORT}")
    app.run(host=Config.HOST, port=Config.PORT, debug=Config.DEBUG)
