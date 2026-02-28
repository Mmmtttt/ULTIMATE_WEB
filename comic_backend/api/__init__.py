from flask import Blueprint
from .v1 import comic_bp, tag_bp


def register_blueprints(app):
    app.register_blueprint(comic_bp, url_prefix='/api/v1/comic')
    app.register_blueprint(tag_bp, url_prefix='/api/v1/tag')
