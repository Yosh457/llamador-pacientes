# extensions.py
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
# Importar SocketIO para comunicación en tiempo real
from flask_socketio import SocketIO

login_manager = LoginManager()
csrf = CSRFProtect()

# Instancia global de SocketIO
socketio = SocketIO(cors_allowed_origins="*")