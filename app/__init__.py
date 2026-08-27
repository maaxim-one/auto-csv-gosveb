import os
import uuid
import logging
import time
from flask import Flask, request, g, session
from flask import current_app as _current_app
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

    @app.after_request
    def set_security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        if app.config.get('PREFERRED_URL_DOMAIN'):
            response.headers['Strict-Transport-Security'] = (
                'max-age=31536000; includeSubDomains'
            )
        return response

    @app.before_request
    def csrf_protect():
        if request.method == 'POST' and request.headers.get('X-Requested-With') != 'XMLHttpRequest':
            testing = _current_app.config.get('TESTING', False)
            if testing:
                return
            csrf_token = request.headers.get('X-CSRF-Token')
            form_csrf = request.form.get('_csrf_token')
            if not csrf_token and form_csrf:
                csrf_token = form_csrf
            if not csrf_token:
                return app.response_class(
                    'CSRF validation failed', status=403
                )

            stored_token = session.get('_csrf_token')
            if stored_token and csrf_token != stored_token:
                return app.response_class(
                    'CSRF validation failed', status=403
                )

    @app.before_request
    def generate_csrf_token():
        if request.method in ('GET', 'HEAD', 'OPTIONS'):
            if '_csrf_token' not in session:
                session['_csrf_token'] = uuid.uuid4().hex

    @app.before_request
    def detect_origin():
        g.origin = request.headers.get('Origin', '')

    @app.before_request
    def rate_limit_check():
        if request.method == 'POST':
            from flask import current_app
            client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
            if not hasattr(current_app, '_rate_limit_store'):
                current_app._rate_limit_store = {} # type: ignore
            store = current_app._rate_limit_store # type: ignore
            now = time.time()
            if client_ip not in store:
                store[client_ip] = []
            store[client_ip] = [t for t in store[client_ip] if now - t < 60]
            if len(store[client_ip]) > 30:
                return app.response_class(
                    'Too many requests. Please try again later.',
                    status=429
                )
            store[client_ip].append(now)

    return app
