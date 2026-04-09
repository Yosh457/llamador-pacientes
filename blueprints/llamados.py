# blueprints/llamados.py
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, abort
from flask_login import login_required, current_user
from datetime import datetime, timedelta

from models import db, Llamado, LlamadoPaciente, LlamadoEvento, Box, Establecimiento
from utils import obtener_hora_chile, registrar_log_sistema, operador_required

llamados_bp = Blueprint('llamados', __name__, template_folder='../templates', url_prefix='/llamados')

# --- RUTAS DE NAVEGACIÓN ---

@llamados_bp.route('/formulario')
@login_required
@operador_required
def formulario():
    """Vista principal del Operador para gestionar sus llamados."""
    
    # 1. Obtener establecimiento del usuario
    establecimiento_id = current_user.establecimiento_id
    if not establecimiento_id:
        flash("Tu usuario no tiene un establecimiento asignado. Contacta al administrador.", "danger")
        return redirect(url_for('auth.login'))
        
    establecimiento = Establecimiento.query.get(establecimiento_id)
    
    # 2. Obtener boxes activos del establecimiento
    boxes = Box.query.filter_by(establecimiento_id=establecimiento_id, activo=True).order_by(Box.orden).all()
    
    # 3. Traer el llamado actualmente ACTIVO de este usuario (si tiene alguno)
    llamado_actual = Llamado.query.filter_by(
        usuario_creador_id=current_user.id, 
        estado='ACTIVO'
    ).first()
    
    # 4. Traer los últimos 5 llamados de este operador para el resumen rápido
    ultimos_llamados = Llamado.query.filter_by(
        usuario_creador_id=current_user.id
    ).order_by(Llamado.fecha_creacion.desc()).limit(5).all()
    
    return render_template(
        'llamados/formulario.html',
        establecimiento=establecimiento,
        boxes=boxes,
        llamado_actual=llamado_actual,
        ultimos_llamados=ultimos_llamados
    )

# --- RUTAS DE ACCIÓN (ENDPOINTS API/FORMULARIO) ---

@llamados_bp.route('/crear', methods=['POST'])
@login_required
@operador_required
def crear_llamado():
    """Genera el PRIMER llamado y crea todos los registros en cascada."""
    box_id = request.form.get('box_id')
    nombres_crudos = request.form.get('pacientes')
    establecimiento_id = current_user.establecimiento_id
    
    if not box_id or not nombres_crudos:
        flash("Debes seleccionar un box e ingresar al menos un paciente.", "danger")
        return redirect(url_for('llamados.formulario'))
    
    # 🔴 MEJORA: Validar que el Box exista, esté activo y pertenezca al establecimiento del operador
    box_seleccionado = Box.query.filter_by(id=int(box_id), establecimiento_id=establecimiento_id, activo=True).first()
    if not box_seleccionado:
        flash("El box seleccionado no es válido o no pertenece a tu establecimiento.", "danger")
        return redirect(url_for('llamados.formulario'))
        
    # Limpiar y separar nombres por salto de línea
    lineas = nombres_crudos.strip().split('\n')
    nombres_pacientes = [nombre.strip() for nombre in lineas if nombre.strip()]
    
    if not nombres_pacientes:
        flash("No se detectaron nombres de pacientes válidos.", "danger")
        return redirect(url_for('llamados.formulario'))
        
    # Verificar si el usuario ya tiene un llamado activo (solo 1 a la vez por operador)
    llamado_existente = Llamado.query.filter_by(usuario_creador_id=current_user.id, estado='ACTIVO').first()
    if llamado_existente:
        flash("Ya tienes un llamado en curso. Cierra o cancela el actual antes de iniciar otro.", "warning")
        return redirect(url_for('llamados.formulario'))

    try:
        ahora = obtener_hora_chile()
        # Expiración por defecto en 15 minutos (ajustable)
        expiracion = ahora + timedelta(minutes=15)
        
        # 1. Crear Cabecera
        nuevo_llamado = Llamado(
            establecimiento_id=establecimiento_id,
            box_id=int(box_id),
            tipo_llamado_actual='PRIMER',
            estado='ACTIVO',
            usuario_creador_id=current_user.id,
            fecha_creacion=ahora,
            fecha_actualizacion=ahora,
            fecha_expiracion=expiracion
        )
        db.session.add(nuevo_llamado)
        db.session.flush() # Obtiene el ID del llamado sin hacer commit definitivo
        
        # 2. Crear Detalle de Pacientes
        for idx, nombre in enumerate(nombres_pacientes, start=1):
            paciente = LlamadoPaciente(
                llamado_id=nuevo_llamado.id,
                paciente_nombre=nombre,
                orden_visualizacion=idx
            )
            db.session.add(paciente)
            
        # 3. Crear Evento de Auditoría (Creación/Primer Llamado)
        snapshot = ", ".join(nombres_pacientes)
        evento = LlamadoEvento(
            llamado_id=nuevo_llamado.id,
            establecimiento_id=establecimiento_id,
            box_id=int(box_id),
            tipo_evento='PRIMER_LLAMADO',
            usuario_id=current_user.id,
            usuario_nombre=current_user.nombre_completo,
            fecha_evento=ahora,
            pacientes_snapshot=snapshot,
            detalle="Operador inició el primer llamado."
        )
        db.session.add(evento)
        
        db.session.commit()
        flash("Primer llamado realizado con éxito.", "success")
        
    except Exception as e:
        db.session.rollback()
        flash(f"Error interno al crear el llamado: {str(e)}", "danger")
        
    return redirect(url_for('llamados.formulario'))

@llamados_bp.route('/transicion/<int:llamado_id>/<accion>', methods=['POST'])
@login_required
@operador_required
def transicion_llamado(llamado_id, accion):
    """Maneja las transiciones: segundo, tercer, cerrar, cancelar."""
    llamado = Llamado.query.get_or_404(llamado_id)
    
    # Validar propiedad
    if llamado.usuario_creador_id != current_user.id:
        flash("Acceso denegado. Este llamado pertenece a otro operador.", "danger")
        return redirect(url_for('llamados.formulario'))
        
    if llamado.estado != 'ACTIVO':
        flash("No se puede modificar un llamado que no está activo.", "warning")
        return redirect(url_for('llamados.formulario'))
        
    ahora = obtener_hora_chile()
    snapshot = ", ".join([p.paciente_nombre for p in llamado.pacientes])
    
    # Lógica de transición
    try:
        tipo_evento = None
        detalle_evento = ""
        
        # 🔴 MEJORA: Secuencia estricta PRIMER -> SEGUNDO -> TERCER
        if accion == 'segundo':
            if llamado.tipo_llamado_actual != 'PRIMER':
                flash("Solo puedes hacer el Segundo Llamado si estás en el Primero.", "warning")
                return redirect(url_for('llamados.formulario'))
            llamado.tipo_llamado_actual = 'SEGUNDO'
            tipo_evento = 'SEGUNDO_LLAMADO'
            detalle_evento = "Operador realizó el segundo llamado."
            
        elif accion == 'tercer':
            if llamado.tipo_llamado_actual != 'SEGUNDO':
                flash("Debes realizar el Segundo Llamado antes de hacer el Tercero.", "warning")
                return redirect(url_for('llamados.formulario'))
            llamado.tipo_llamado_actual = 'TERCER'
            tipo_evento = 'TERCER_LLAMADO'
            detalle_evento = "Operador realizó el tercer y último llamado."
            
        elif accion == 'cerrar':
            llamado.estado = 'FINALIZADO'
            llamado.fecha_cierre = ahora
            llamado.cerrado_por_usuario_id = current_user.id
            llamado.visible_en_pantalla = False
            tipo_evento = 'CIERRE'
            detalle_evento = "Paciente fue atendido. Llamado cerrado."
            
        elif accion == 'cancelar':
            llamado.estado = 'CANCELADO'
            llamado.fecha_cierre = ahora
            llamado.cerrado_por_usuario_id = current_user.id
            llamado.visible_en_pantalla = False
            tipo_evento = 'CANCELACION'
            detalle_evento = "El paciente no se presentó. Llamado cancelado."
            
        else:
            flash("Transición no válida para el estado actual del llamado.", "warning")
            return redirect(url_for('llamados.formulario'))
            
        # Registrar auditoría
        llamado.fecha_actualizacion = ahora
        
        evento = LlamadoEvento(
            llamado_id=llamado.id,
            establecimiento_id=llamado.establecimiento_id,
            box_id=llamado.box_id,
            tipo_evento=tipo_evento,
            usuario_id=current_user.id,
            usuario_nombre=current_user.nombre_completo,
            fecha_evento=ahora,
            pacientes_snapshot=snapshot,
            detalle=detalle_evento
        )
        db.session.add(evento)
        db.session.commit()
        
        mensaje = f"Acción '{accion.capitalize()}' registrada correctamente."
        flash(mensaje, "success")
        
    except Exception as e:
        db.session.rollback()
        flash(f"Error de base de datos en transición: {str(e)}", "danger")
        
    return redirect(url_for('llamados.formulario'))

# --- NUEVAS RUTAS: FASE 2B (HISTORIAL Y DETALLE) ---

@llamados_bp.route('/historial')
@login_required
def historial():
    """Vista de historial filtrable con permisos escalonados."""
    page = request.args.get('page', 1, type=int)
    fecha_filtro = request.args.get('fecha')
    box_filtro = request.args.get('box_id')
    estado_filtro = request.args.get('estado')
    
    query = Llamado.query
    
    # 🔴 Lógica de Permisos Escalonados
    if current_user.rol.nombre == 'Operador':
        # Operador: Solo ve SUS llamados
        query = query.filter(Llamado.usuario_creador_id == current_user.id)
        boxes_disponibles = Box.query.filter_by(establecimiento_id=current_user.establecimiento_id).all()
    elif current_user.rol.nombre == 'Supervisor':
        # Supervisor: Ve TODOS los llamados de SU establecimiento
        query = query.filter(Llamado.establecimiento_id == current_user.establecimiento_id)
        boxes_disponibles = Box.query.filter_by(establecimiento_id=current_user.establecimiento_id).all()
    elif current_user.rol.nombre == 'Admin':
        # Admin: Ve TODO. (Los boxes disponibles dependen del establecimiento, aquí mostramos todos para simplificar)
        boxes_disponibles = Box.query.all()
    else:
        abort(403)

    # Aplicar Filtros
    if fecha_filtro:
        try:
            fecha_obj = datetime.strptime(fecha_filtro, '%Y-%m-%d').date()
            query = query.filter(db.func.date(Llamado.fecha_creacion) == fecha_obj)
        except ValueError:
            pass

    if box_filtro and box_filtro.isdigit():
        query = query.filter(Llamado.box_id == int(box_filtro))
        
    if estado_filtro:
        query = query.filter(Llamado.estado == estado_filtro)

    pagination = query.order_by(Llamado.fecha_creacion.desc()).paginate(page=page, per_page=15, error_out=False)
    
    return render_template(
        'llamados/historial.html',
        pagination=pagination,
        boxes=boxes_disponibles,
        filtros={'fecha': fecha_filtro, 'box_id': box_filtro, 'estado': estado_filtro}
    )

@llamados_bp.route('/detalle/<int:id>')
@login_required
def detalle(id):
    """Vista de detalle completo de un llamado y su trazabilidad."""
    llamado = Llamado.query.get_or_404(id)
    
    # 🔴 Lógica de Permisos Escalonados para ver el detalle
    if current_user.rol.nombre == 'Operador' and llamado.usuario_creador_id != current_user.id:
        abort(403)
    elif current_user.rol.nombre == 'Supervisor' and llamado.establecimiento_id != current_user.establecimiento_id:
        abort(403)
        
    # Obtener los eventos ordenados cronológicamente
    eventos = LlamadoEvento.query.filter_by(llamado_id=llamado.id).order_by(LlamadoEvento.fecha_evento.asc()).all()
    
    return render_template(
        'llamados/detalle.html',
        llamado=llamado,
        eventos=eventos
    )