from .comic import comic_bp
from .tag import tag_bp

def register_blueprints(app):
    app.register_blueprint(comic_bp, url_prefix='/api/v1/comic')
    app.register_blueprint(tag_bp, url_prefix='/api/v1/tag')
