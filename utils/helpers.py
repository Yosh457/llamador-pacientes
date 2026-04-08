# utils/helpers.py
from datetime import datetime
import pytz
from flask_login import current_user

def obtener_hora_chile():
    """Retorna la fecha y hora actual en Santiago de Chile."""
    cl_tz = pytz.timezone('America/Santiago')
    return datetime.now(cl_tz)

def registrar_log_sistema(accion, detalles, usuario=None):
    """
    Registra un evento en la tabla 'log_sistema'.
    Usa Lazy Import para evitar ciclos con models.py
    """
    from models import db, LogSistema

    try:
        user_id = None
        user_nombre = "Sistema/Anónimo"

        if usuario:
            user_id = usuario.id
            user_nombre = usuario.nombre_completo
        elif current_user and current_user.is_authenticated:
            user_id = current_user.id
            user_nombre = current_user.nombre_completo

        nuevo_log = LogSistema(
            usuario_id=user_id,
            usuario_nombre=user_nombre,
            accion=accion,
            detalles=detalles,
            timestamp=obtener_hora_chile()
        )
        db.session.add(nuevo_log)
        db.session.commit()
    except Exception as e:
        print(f"Error al registrar log: {e}")