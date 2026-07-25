import os
import logging
from flask import Flask
from app.config import Config

logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')


def create_app(config_class=None):
    config_class = config_class or Config

    app = Flask(
        __name__,
        template_folder=config_class.TEMPLATE_FOLDER,
        static_folder=config_class.STATIC_FOLDER,
    )
    app.config.from_object(config_class)

    os.makedirs(app.config['STORAGE_DIR'], exist_ok=True)

    from routes.web import register_routes
    register_routes(app)

    return app
