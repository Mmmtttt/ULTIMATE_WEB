from flask import Blueprint
from .v1 import comic_bp, tag_bp, list_bp, config_bp, recommendation_bp


def register_blueprints(app):
    app.register_blueprint(comic_bp, url_prefix='/api/v1/comic')
    app.register_blueprint(tag_bp, url_prefix='/api/v1/tag')
    app.register_blueprint(list_bp, url_prefix='/api/v1/list')
    app.register_blueprint(config_bp, url_prefix='/api/v1/config')
    app.register_blueprint(recommendation_bp, url_prefix='/api/v1/recommendation')
