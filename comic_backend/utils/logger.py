import logging
import os
from config import Config

# 确保日志目录存在
os.makedirs(Config.LOGS_DIR, exist_ok=True)

# 配置应用日志
app_logger = logging.getLogger('app')
app_logger.setLevel(logging.INFO)

# 配置错误日志
error_logger = logging.getLogger('error')
error_logger.setLevel(logging.ERROR)

# 配置访问日志
access_logger = logging.getLogger('access')
access_logger.setLevel(logging.INFO)

# 创建文件处理器
app_handler = logging.FileHandler(os.path.join(Config.LOGS_DIR, 'app.log'), encoding='utf-8')
error_handler = logging.FileHandler(os.path.join(Config.LOGS_DIR, 'error.log'), encoding='utf-8')
access_handler = logging.FileHandler(os.path.join(Config.LOGS_DIR, 'access.log'), encoding='utf-8')

# 设置日志格式
formatter = logging.Formatter('[%(asctime)s] [%(levelname)s] [%(module)s] %(message)s')
app_handler.setFormatter(formatter)
error_handler.setFormatter(formatter)
access_handler.setFormatter(formatter)

# 添加处理器到日志器
app_logger.addHandler(app_handler)
error_logger.addHandler(error_handler)
access_logger.addHandler(access_handler)

# 导出日志器

