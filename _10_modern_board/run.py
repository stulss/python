import os
import sys

# Windows cp949 터미널 호환성
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

from app import create_app

app = create_app()

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('FLASK_ENV', 'development') == 'development'
    print(f"[START] Modern Board server starting at: http://127.0.0.1:{port}")
    app.run(host='0.0.0.0', port=port, debug=debug)

