from app.http.controllers.page import page_bp
from app.http.controllers.download import download_bp
from app.http.controllers.api import api_bp


def register_routes(app):
    app.register_blueprint(page_bp)
    app.register_blueprint(download_bp)
    app.register_blueprint(api_bp)
