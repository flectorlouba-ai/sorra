"""Point d'entrée : `flask --app performyl2 ...` en ligne de commande, `performyl2:app` pour gunicorn."""
import os
from app import create_app

app = create_app(os.environ.get('YL2_ENV', 'default'))


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5020))
    app.run(host='0.0.0.0', port=port, debug=app.config.get('DEBUG', False))
