# Ultimate Web API - Mmmtttt
from flask import Blueprint
from .v1 import (
    actor_bp,
    author_bp,
    backup_bp,
    comic_bp,
    config_bp,
    feed_bp,
    list_bp,
    organize_bp,
    recommendation_bp,
    sync_bp,
    tag_bp,
    teledrive_bp,
    ui_state_bp,
    video_bp,
    auth_bp,
    performance_bp,
    history_bp,
    transfer_bp,
)


def register_blueprints(app):
    app.register_blueprint(comic_bp, url_prefix='/api/v1/comic')
    app.register_blueprint(tag_bp, url_prefix='/api/v1/tag')
    app.register_blueprint(list_bp, url_prefix='/api/v1/list')
    app.register_blueprint(organize_bp, url_prefix='/api/v1/organize')
    app.register_blueprint(config_bp, url_prefix='/api/v1/config')
    app.register_blueprint(recommendation_bp, url_prefix='/api/v1/recommendation')
    app.register_blueprint(backup_bp, url_prefix='/api/v1/backup')
    app.register_blueprint(author_bp, url_prefix='/api/v1/author')
    app.register_blueprint(video_bp, url_prefix='/api/v1/video')
    app.register_blueprint(actor_bp, url_prefix='/api/v1/actor')
    app.register_blueprint(sync_bp, url_prefix='/api/v1/sync')
    app.register_blueprint(feed_bp, url_prefix='/api/v1/feed')
    app.register_blueprint(ui_state_bp, url_prefix='/api/v1/ui-state')
    app.register_blueprint(teledrive_bp, url_prefix='/api/v1/teledrive')
    app.register_blueprint(auth_bp, url_prefix='/api/v1/auth')
    app.register_blueprint(performance_bp, url_prefix='/api/v1/performance')
    app.register_blueprint(history_bp, url_prefix='/api/v1/history')
    app.register_blueprint(transfer_bp, url_prefix='/api/v1/transfer')
