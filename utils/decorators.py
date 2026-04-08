# utils/decorators.py
from functools import wraps
from flask import abort, redirect, url_for, flash, request
from flask_login import current_user

def check_password_change(f):
    """Verifica si el usuario debe cambiar su contraseña obligatoriamente."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.is_authenticated and current_user.cambio_clave_requerido:
            if request.endpoint not in ['auth.cambiar_clave', 'auth.logout']:
                flash('Debes cambiar tu contraseña para continuar.', 'warning')
                return redirect(url_for('auth.cambiar_clave'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """Solo permite acceso al Rol 'Admin'."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.rol or current_user.rol.nombre != 'Admin':
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

def operador_required(f):
    """Solo permite acceso al Rol 'Operador'."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.rol or current_user.rol.nombre != 'Operador':
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

def supervisor_required(f):
    """Solo permite acceso al Rol 'Supervisor'."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.rol or current_user.rol.nombre != 'Supervisor':
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

def roles_required(*roles_permitidos):
    """Permite acceso a uno o más roles."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated or not current_user.rol:
                abort(403)
            if current_user.rol.nombre not in roles_permitidos:
                abort(403)
            return f(*args, **kwargs)
        return decorated_function
    return decorator