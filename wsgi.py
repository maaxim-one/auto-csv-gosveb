import os
from app import create_app

app = create_app()
app.config['MAX_CONTENT_LENGTH'] = 1000 * 1024 * 1024

if __name__ == '__main__':
    with app.app_context():
        from app.utils import cleanup_stale_temp_files
        cleanup_stale_temp_files()
    app.run(host='0.0.0.0', port=5000, debug=os.environ.get('FLASK_DEBUG', '0') == '1')
