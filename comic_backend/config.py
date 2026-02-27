class Config:
    # 服务器配置
    PORT = 5000
    DEBUG = True
    
    # 路径配置
    DATA_DIR = "data"
    PICTURES_DIR = "data/pictures"
    META_DIR = "data/meta_data"
    STATIC_DIR = "static"
    COVER_DIR = "static/cover"
    LOGS_DIR = "logs"
    
    # 图片配置
    COVER_WIDTH = 500
    COVER_QUALITY = 85
    SUPPORTED_FORMATS = ['.jpg', '.jpeg', '.png', '.webp']
    
    # JSON配置
    JSON_FILE = "data/meta_data/comics_database.json"
    BACKUP_SUFFIX = ".bak"
