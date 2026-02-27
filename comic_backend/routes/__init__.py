from .comic import comic_bp

# 注册蓝图
def register_blueprints(app):
    app.register_blueprint(comic_bp, url_prefix='/api/v1/comic')
