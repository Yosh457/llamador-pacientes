# models.py
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import pytz

db = SQLAlchemy()

def obtener_hora_chile():
    cl_tz = pytz.timezone('America/Santiago')
    return datetime.now(cl_tz)

# ==============================================================================
# CATÁLOGOS Y CONFIGURACIÓN
# ==============================================================================

class RolAplicacion(db.Model):
    __tablename__ = 'roles_aplicacion'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(50), unique=True, nullable=False)

    usuarios = db.relationship('Usuario', back_populates='rol')


class TipoEstablecimiento(db.Model):
    __tablename__ = 'tipos_establecimiento'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(50), unique=True, nullable=False)
    activo = db.Column(db.Boolean, default=True, nullable=False)

    establecimientos = db.relationship('Establecimiento', back_populates='tipo_establecimiento')


class Establecimiento(db.Model):
    __tablename__ = 'establecimientos'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(150), unique=True, nullable=False)
    codigo = db.Column(db.String(100), unique=True, nullable=False)
    direccion = db.Column(db.String(255), nullable=True)
    telefono = db.Column(db.String(50), nullable=True)
    tipo_establecimiento_id = db.Column(db.Integer, db.ForeignKey('tipos_establecimiento.id'), nullable=False, index=True)
    activo = db.Column(db.Boolean, default=True, nullable=False)
    fecha_creacion = db.Column(db.DateTime, default=obtener_hora_chile, nullable=False)

    # Relaciones
    tipo_establecimiento = db.relationship('TipoEstablecimiento', back_populates='establecimientos')
    usuarios = db.relationship('Usuario', back_populates='establecimiento')
    boxes = db.relationship('Box', back_populates='establecimiento', cascade='all, delete-orphan')
    llamados = db.relationship('Llamado', back_populates='establecimiento')
    
    # Relación 1 a 1 estricta con Pantalla
    pantalla = db.relationship(
        'Pantalla', 
        back_populates='establecimiento', 
        uselist=False, 
        cascade='all, delete-orphan'
    )


# ==============================================================================
# USUARIOS
# ==============================================================================

class Usuario(db.Model, UserMixin):
    __tablename__ = 'usuarios'
    id = db.Column(db.Integer, primary_key=True)
    nombre_completo = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    activo = db.Column(db.Boolean, default=True, nullable=False)
    fecha_creacion = db.Column(db.DateTime, default=obtener_hora_chile, nullable=False)
    cambio_clave_requerido = db.Column(db.Boolean, default=False, nullable=False)
    reset_token = db.Column(db.String(32), unique=True, nullable=True)
    reset_token_expiracion = db.Column(db.DateTime, nullable=True)

    rol_id = db.Column(db.Integer, db.ForeignKey('roles_aplicacion.id'), nullable=False, index=True)
    establecimiento_id = db.Column(db.Integer, db.ForeignKey('establecimientos.id'), nullable=True, index=True)

    # Relaciones base
    rol = db.relationship('RolAplicacion', back_populates='usuarios')
    establecimiento = db.relationship('Establecimiento', back_populates='usuarios')

    # Relaciones operativas (Tracking de quién hace qué)
    llamados_creados = db.relationship(
        'Llamado',
        foreign_keys='Llamado.usuario_creador_id',
        back_populates='usuario_creador'
    )

    llamados_cerrados = db.relationship(
        'Llamado',
        foreign_keys='Llamado.cerrado_por_usuario_id',
        back_populates='usuario_cierre'
    )

    eventos_llamado = db.relationship('LlamadoEvento', back_populates='usuario')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


# ==============================================================================
# BOXES Y PANTALLAS
# ==============================================================================

class Box(db.Model):
    __tablename__ = 'boxes'
    id = db.Column(db.Integer, primary_key=True)
    establecimiento_id = db.Column(
        db.Integer,
        db.ForeignKey('establecimientos.id', ondelete='CASCADE'),
        nullable=False
    )
    nombre = db.Column(db.String(150), nullable=False)
    activo = db.Column(db.Boolean, default=True, nullable=False)
    orden = db.Column(db.Integer, default=1, nullable=False)
    fecha_creacion = db.Column(db.DateTime, default=obtener_hora_chile, nullable=False)

    establecimiento = db.relationship('Establecimiento', back_populates='boxes')
    llamados = db.relationship('Llamado', back_populates='box')

    __table_args__ = (
        db.UniqueConstraint('establecimiento_id', 'nombre', name='uk_boxes_establecimiento_nombre'),
        db.Index('idx_boxes_establecimiento', 'establecimiento_id'),
        db.Index('idx_boxes_establecimiento_activo_orden', 'establecimiento_id', 'activo', 'orden'),
    )


class Pantalla(db.Model):
    __tablename__ = 'pantallas'
    id = db.Column(db.Integer, primary_key=True)
    establecimiento_id = db.Column(
        db.Integer,
        db.ForeignKey('establecimientos.id', ondelete='CASCADE'),
        nullable=False
    )
    nombre = db.Column(db.String(150), nullable=False)
    token_acceso = db.Column(db.String(128), unique=True, nullable=False)
    activo = db.Column(db.Boolean, default=True, nullable=False)
    fecha_creacion = db.Column(db.DateTime, default=obtener_hora_chile, nullable=False)

    establecimiento = db.relationship('Establecimiento', back_populates='pantalla')

    __table_args__ = (
        db.UniqueConstraint('establecimiento_id', name='uk_pantallas_establecimiento'),
        db.Index('idx_pantallas_activo', 'activo'),
    )


# ==============================================================================
# LLAMADOS
# ==============================================================================

class Llamado(db.Model):
    __tablename__ = 'llamados'
    id = db.Column(db.BigInteger, primary_key=True)
    establecimiento_id = db.Column(db.Integer, db.ForeignKey('establecimientos.id'), nullable=False)
    box_id = db.Column(db.Integer, db.ForeignKey('boxes.id'), nullable=False)

    tipo_llamado_actual = db.Column(
        db.Enum('PRIMER', 'SEGUNDO', 'TERCER', name='tipo_llamado_actual_enum'),
        nullable=False,
        default='PRIMER'
    )

    estado = db.Column(
        db.Enum('ACTIVO', 'FINALIZADO', 'CANCELADO', name='estado_llamado_enum'),
        nullable=False,
        default='ACTIVO'
    )

    usuario_creador_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    fecha_creacion = db.Column(db.DateTime, default=obtener_hora_chile, nullable=False)
    fecha_actualizacion = db.Column(db.DateTime, default=obtener_hora_chile, onupdate=obtener_hora_chile, nullable=False)

    cerrado_por_usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id', ondelete='SET NULL'), nullable=True)
    fecha_cierre = db.Column(db.DateTime, nullable=True)

    establecimiento = db.relationship('Establecimiento', back_populates='llamados')
    box = db.relationship('Box', back_populates='llamados')
    usuario_creador = db.relationship('Usuario', foreign_keys=[usuario_creador_id], back_populates='llamados_creados')
    usuario_cierre = db.relationship('Usuario', foreign_keys=[cerrado_por_usuario_id], back_populates='llamados_cerrados')

    pacientes = db.relationship('LlamadoPaciente', back_populates='llamado', cascade='all, delete-orphan')
    eventos = db.relationship('LlamadoEvento', back_populates='llamado', cascade='all, delete-orphan')

    __table_args__ = (
        db.Index('idx_llamados_establecimiento_fecha', 'establecimiento_id', 'fecha_creacion'),
        db.Index('idx_llamados_establecimiento_estado_fecha', 'establecimiento_id', 'estado', 'fecha_creacion'),
        db.Index('idx_llamados_box_fecha', 'box_id', 'fecha_creacion'),
        db.Index('idx_llamados_usuario_fecha', 'usuario_creador_id', 'fecha_creacion'),
        db.Index('idx_llamados_estado_fecha', 'estado', 'fecha_creacion'),
    )


class LlamadoPaciente(db.Model):
    __tablename__ = 'llamado_pacientes'
    id = db.Column(db.BigInteger, primary_key=True)
    llamado_id = db.Column(
        db.BigInteger,
        db.ForeignKey('llamados.id', ondelete='CASCADE'),
        nullable=False
    )
    paciente_nombre = db.Column(db.String(255), nullable=False)
    orden_visualizacion = db.Column(db.Integer, default=1, nullable=False)

    llamado = db.relationship('Llamado', back_populates='pacientes')

    __table_args__ = (
        db.Index('idx_llamado_pacientes_llamado', 'llamado_id'),
        db.Index('idx_llamado_pacientes_nombre', 'paciente_nombre'),
        db.Index('idx_llamado_pacientes_llamado_orden', 'llamado_id', 'orden_visualizacion'),
    )


class LlamadoEvento(db.Model):
    __tablename__ = 'llamado_eventos'
    id = db.Column(db.BigInteger, primary_key=True)
    llamado_id = db.Column(
        db.BigInteger,
        db.ForeignKey('llamados.id', ondelete='CASCADE'),
        nullable=False
    )
    establecimiento_id = db.Column(db.Integer, db.ForeignKey('establecimientos.id'), nullable=False)
    box_id = db.Column(db.Integer, db.ForeignKey('boxes.id'), nullable=False)

    tipo_evento = db.Column(
        db.Enum(
            'CREACION',
            'PRIMER_LLAMADO',
            'SEGUNDO_LLAMADO',
            'TERCER_LLAMADO',
            'CIERRE',
            'CANCELACION',
            name='tipo_evento_llamado_enum'
        ),
        nullable=False
    )

    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id', ondelete='SET NULL'), nullable=True)
    usuario_nombre = db.Column(db.String(255), nullable=True)
    fecha_evento = db.Column(db.DateTime, default=obtener_hora_chile, nullable=False)

    pacientes_snapshot = db.Column(db.Text, nullable=False)
    detalle = db.Column(db.Text, nullable=True)
    ip_origen = db.Column(db.String(45), nullable=True)

    llamado = db.relationship('Llamado', back_populates='eventos')
    usuario = db.relationship('Usuario', back_populates='eventos_llamado')
    establecimiento = db.relationship('Establecimiento')
    box = db.relationship('Box')

    __table_args__ = (
        db.Index('idx_pantalla_polling_min', 'establecimiento_id', 'id'),
        db.Index('idx_llamado_eventos_llamado_fecha', 'llamado_id', 'fecha_evento'),
        db.Index('idx_llamado_eventos_establecimiento_fecha', 'establecimiento_id', 'fecha_evento'),
        db.Index('idx_llamado_eventos_usuario_fecha', 'usuario_id', 'fecha_evento'),
        db.Index('idx_llamado_eventos_tipo_fecha', 'tipo_evento', 'fecha_evento'),
        db.Index('idx_llamado_eventos_box_fecha', 'box_id', 'fecha_evento'),
    )


# ==============================================================================
# LOGS DEL SISTEMA
# ==============================================================================

class LogSistema(db.Model):
    __tablename__ = 'log_sistema'
    id = db.Column(db.BigInteger, primary_key=True)
    timestamp = db.Column(db.DateTime, default=obtener_hora_chile, index=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id', ondelete='SET NULL'), nullable=True, index=True)
    usuario_nombre = db.Column(db.String(255), nullable=True)
    accion = db.Column(db.String(255), nullable=False)
    detalles = db.Column(db.Text, nullable=True)
    ip_origen = db.Column(db.String(50), nullable=True)

    usuario = db.relationship('Usuario')