"""Point d'entrée : `flask --app kimba ...` en ligne de commande, `kimba:app` pour gunicorn."""
import os
from app import create_app

app = create_app(os.environ.get('KIMBA_ENV', 'default'))


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5020))
    app.run(host='0.0.0.0', port=port, debug=app.config.get('DEBUG', False))
