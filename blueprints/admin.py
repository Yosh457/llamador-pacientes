# blueprints/admin.py
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from sqlalchemy import or_

# Modelos actualizados al diseño v1 del Llamador
from models import (
    db, Usuario, RolAplicacion, Establecimiento, 
    TipoEstablecimiento, Box, Pantalla, LogSistema, LlamadoEvento
)

# Utilidades 
from utils import registrar_log_sistema, admin_required, enviar_credenciales_nuevo_usuario

# Instanciamos el blueprint
admin_bp = Blueprint('admin', __name__, template_folder='../templates', url_prefix='/admin')

# --- PROTECCIÓN GLOBAL DEL BLUEPRINT ---
@admin_bp.before_request
@login_required
@admin_required
def before_request():
    """
    Se ejecuta antes de cada petición a /admin/*.
    Garantiza que nadie sin sesión o sin rol de Admin pueda acceder a estas rutas.
    """
    pass

# --- RUTAS PRINCIPALES ---

@admin_bp.route('/panel')
def panel():
    """
    Vista principal del Panel de Administración.
    Muestra estadísticas rápidas del sistema de llamados y tabla de usuarios.
    """
    page = request.args.get('page', 1, type=int)
    busqueda = request.args.get('busqueda', '')
    rol_filtro = request.args.get('rol_filtro', '')
    
    query = Usuario.query

    # Filtro por texto (Nombre o Email)
    if busqueda:
        query = query.filter(
            or_(Usuario.nombre_completo.ilike(f'%{busqueda}%'),
                Usuario.email.ilike(f'%{busqueda}%'))
        )
    
    # Filtro por Rol de Aplicación
    if rol_filtro:
        query = query.filter(Usuario.rol_id == rol_filtro)
    
    # Paginación de usuarios
    pagination = query.order_by(Usuario.id).paginate(page=page, per_page=10, error_out=False)
    roles_para_filtro = RolAplicacion.query.order_by(RolAplicacion.nombre).all()
    
    # Estadísticas Rápidas del Llamador de Pacientes
    stats = {
        'total_usuarios': Usuario.query.count(),
        'establecimientos_activos': Establecimiento.query.filter_by(activo=True).count(),
        'boxes_activos': Box.query.filter_by(activo=True).count(),
        'pantallas_activas': Pantalla.query.filter_by(activo=True).count()
    }

    return render_template('admin/panel.html', 
                           pagination=pagination,
                           roles_para_filtro=roles_para_filtro,
                           busqueda=busqueda,
                           rol_filtro=rol_filtro,
                           stats=stats)

# --- GESTIÓN DE USUARIOS ---

@admin_bp.route('/crear_usuario', methods=['GET', 'POST'])
def crear_usuario():
    """
    Formulario para registrar nuevos usuarios operadores/supervisores.
    Se les debe asignar obligatoriamente un Establecimiento.
    """
    roles = RolAplicacion.query.order_by(RolAplicacion.nombre).all()
    establecimientos = Establecimiento.query.filter_by(activo=True).order_by(Establecimiento.nombre).all()

    if request.method == 'POST':
        nombre = request.form.get('nombre_completo', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '').strip()
        rol_id = request.form.get('rol_id')
        establecimiento_id = request.form.get('establecimiento_id')
        forzar_cambio = request.form.get('forzar_cambio_clave') == '1'
        
        # 🔴 Validaciones backend
        if not nombre or not email or not password or not rol_id:
            flash('Todos los campos obligatorios deben completarse.', 'danger')
            return render_template('admin/crear_usuario.html', roles=roles, establecimientos=establecimientos, datos_previos=request.form)
        
        # Validación de email duplicado
        if Usuario.query.filter_by(email=email).first():
            flash('Error: El correo electrónico ya se encuentra registrado.', 'danger')
            return render_template('admin/crear_usuario.html', roles=roles, establecimientos=establecimientos, datos_previos=request.form)

        # Validación: SuperAdmin puede no tener establecimiento, Operadores SÍ necesitan.
        rol_seleccionado = RolAplicacion.query.get(rol_id)
        if rol_seleccionado and rol_seleccionado.nombre != 'Admin' and not establecimiento_id:
            flash('Error: Los Operadores y Supervisores deben pertenecer a un Establecimiento.', 'danger')
            return render_template('admin/crear_usuario.html', roles=roles, establecimientos=establecimientos, datos_previos=request.form)

        est_final = int(establecimiento_id) if establecimiento_id else None

        try:
            nuevo_usuario = Usuario(
                nombre_completo=nombre,
                email=email,
                rol_id=int(rol_id),
                establecimiento_id=est_final,
                cambio_clave_requerido=forzar_cambio,
                activo=True
            )

            nuevo_usuario.set_password(password)

            db.session.add(nuevo_usuario)
            db.session.commit()

            registrar_log_sistema(
                "Creación Usuario",
                f"Admin creó a {nombre} ({email}).",
                usuario=current_user
            )

            if enviar_credenciales_nuevo_usuario(nuevo_usuario, password):
                flash(f'Usuario creado con éxito. Credenciales enviadas a {email}.', 'success')
            else:
                flash(f'Usuario creado, pero FALLÓ el envío del correo. Entregar clave manual: {password}', 'warning')

            return redirect(url_for('admin.panel'))

        except Exception as e:
            db.session.rollback()
            flash(f'Error de base de datos: {str(e)}', 'danger')

    return render_template('admin/crear_usuario.html', roles=roles, establecimientos=establecimientos, datos_previos=request.form)

@admin_bp.route('/editar_usuario/<int:id>', methods=['GET', 'POST'])
def editar_usuario(id):
    usuario = Usuario.query.get_or_404(id)
    roles = RolAplicacion.query.order_by(RolAplicacion.nombre).all()
    establecimientos = Establecimiento.query.filter_by(activo=True).order_by(Establecimiento.nombre).all()

    if request.method == 'POST':
        email_nuevo = request.form.get('email', '').strip().lower()
        nombre_nuevo = request.form.get('nombre_completo', '').strip()
        rol_id = request.form.get('rol_id')
        establecimiento_id = request.form.get('establecimiento_id')
        forzar_cambio = request.form.get('forzar_cambio_clave') == '1'
        password = request.form.get('password', '').strip()

        # Validación de duplicidad de email
        usuario_existente = Usuario.query.filter_by(email=email_nuevo).first()
        if usuario_existente and usuario_existente.id != id:
            flash('Error: Ese correo ya pertenece a otro usuario en el sistema.', 'danger')
            return render_template(
                'admin/editar_usuario.html',
                usuario=usuario,
                roles=roles,
                establecimientos=establecimientos
            )

        # Validación de establecimiento según rol
        rol_seleccionado = RolAplicacion.query.get(rol_id)
        if rol_seleccionado and rol_seleccionado.nombre != 'Admin' and not establecimiento_id:
            flash('Error: Los Operadores y Supervisores deben pertenecer a un Establecimiento.', 'danger')
            return render_template(
                'admin/editar_usuario.html',
                usuario=usuario,
                roles=roles,
                establecimientos=establecimientos
            )

        usuario.nombre_completo = nombre_nuevo
        usuario.email = email_nuevo
        usuario.rol_id = int(rol_id)
        usuario.establecimiento_id = int(establecimiento_id) if establecimiento_id else None
        usuario.cambio_clave_requerido = forzar_cambio

        if password:
            usuario.set_password(password)
            flash('Contraseña actualizada correctamente.', 'info')

        try:
            db.session.commit()
            registrar_log_sistema(
                "Edición Usuario",
                f"Admin editó perfil de {usuario.nombre_completo}.",
                usuario=current_user
            )
            flash('Usuario actualizado con éxito.', 'success')
            return redirect(url_for('admin.panel'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error al actualizar la base de datos: {str(e)}', 'danger')

    return render_template(
        'admin/editar_usuario.html',
        usuario=usuario,
        roles=roles,
        establecimientos=establecimientos
    )

@admin_bp.route('/toggle_activo/<int:id>', methods=['POST'])
def toggle_activo(id):
    usuario = Usuario.query.get_or_404(id)

    if usuario.id == current_user.id:
        flash('Medida de seguridad: No puedes desactivar tu propia cuenta.', 'danger')
        return redirect(url_for('admin.panel'))

    try:
        usuario.activo = not usuario.activo

        db.session.commit()

        estado = "activado" if usuario.activo else "desactivado"

        registrar_log_sistema(
            "Cambio Estado Usuario",
            f"Usuario {usuario.nombre_completo} fue {estado}.",
            usuario=current_user
        )

        flash(f'Usuario {usuario.nombre_completo} {estado} correctamente.', 'success')

    except Exception as e:
        db.session.rollback()

        registrar_log_sistema(
            "Error Cambio Estado",
            f"Error al cambiar estado de {usuario.nombre_completo}: {str(e)}",
            usuario=current_user
        )

        flash('Ocurrió un error al cambiar el estado del usuario.', 'danger')

    return redirect(url_for('admin.panel'))

# --- VISTAS DE AUDITORÍA (SEPARADAS SEGÚN LA ESTRUCTURA ACORDADA) ---

@admin_bp.route('/ver_logs')
def ver_logs():
    """Historial de auditoría administrativa y de sistema."""
    page = request.args.get('page', 1, type=int)
    usuario_filtro = request.args.get('usuario_id')
    accion_filtro = request.args.get('accion')

    query = LogSistema.query.order_by(LogSistema.timestamp.desc())

    if usuario_filtro and usuario_filtro.isdigit():
        query = query.filter(LogSistema.usuario_id == int(usuario_filtro))
    if accion_filtro:
        query = query.filter(LogSistema.accion == accion_filtro)

    pagination = query.paginate(page=page, per_page=15, error_out=False)
    todos_los_usuarios = Usuario.query.order_by(Usuario.nombre_completo).all()
    acciones_unicas = [r[0] for r in db.session.query(LogSistema.accion).distinct().all()]

    return render_template('admin/ver_logs.html', 
                           pagination=pagination,
                           todos_los_usuarios=todos_los_usuarios,
                           acciones_posibles=acciones_unicas,
                           filtros={'usuario_id': usuario_filtro, 'accion': accion_filtro})

@admin_bp.route('/ver_auditoria')
def ver_auditoria():
    """Historial Operativo (Trazabilidad Fina de Llamados)."""
    page = request.args.get('page', 1, type=int)
    est_filtro = request.args.get('establecimiento_id')
    evento_filtro = request.args.get('tipo_evento')

    query = LlamadoEvento.query.order_by(LlamadoEvento.fecha_evento.desc())

    if est_filtro and est_filtro.isdigit():
        query = query.filter(LlamadoEvento.establecimiento_id == int(est_filtro))
    if evento_filtro:
        query = query.filter(LlamadoEvento.tipo_evento == evento_filtro)

    pagination = query.paginate(page=page, per_page=15, error_out=False)
    
    establecimientos = Establecimiento.query.order_by(Establecimiento.nombre).all()
    tipos_evento = ['CREACION', 'PRIMER_LLAMADO', 'SEGUNDO_LLAMADO', 'TERCER_LLAMADO', 'CIERRE', 'CANCELACION', 'EXPIRACION']

    return render_template('admin/ver_auditoria.html', 
                           pagination=pagination,
                           establecimientos=establecimientos,
                           tipos_evento=tipos_evento,
                           filtros={'establecimiento_id': est_filtro, 'tipo_evento': evento_filtro})

# --- GESTIÓN BÁSICA (RUTAS PLACEHOLDER PARA HTMLs A FUTURO) ---

@admin_bp.route('/establecimientos')
def establecimientos():
    # TODO: Implementar CRUD completo en el futuro
    lista = Establecimiento.query.order_by(Establecimiento.nombre).all()
    return render_template('admin/establecimientos.html', establecimientos=lista)

@admin_bp.route('/boxes', methods=['GET', 'POST'])
def boxes():
    """CRUD Básico de Boxes para desbloquear la operación del Operador."""
    establecimientos = Establecimiento.query.filter_by(activo=True).order_by(Establecimiento.nombre).all()
    
    if request.method == 'POST':
        est_id = request.form.get('establecimiento_id', '').strip()
        nombre = request.form.get('nombre', '').strip()
        orden_raw = request.form.get('orden', '1').strip()
        
        if not est_id or not nombre:
            flash('El Establecimiento y el Nombre del box son obligatorios.', 'danger')
            return render_template(
                'admin/boxes.html',
                boxes=Box.query.order_by(Box.establecimiento_id, Box.orden, Box.nombre).all(),
                establecimientos=establecimientos,
                filtro_actual='',
                datos_previos=request.form
            )

        if not est_id.isdigit():
            flash('El establecimiento seleccionado no es válido.', 'danger')
            return render_template(
                'admin/boxes.html',
                boxes=Box.query.order_by(Box.establecimiento_id, Box.orden, Box.nombre).all(),
                establecimientos=establecimientos,
                filtro_actual='',
                datos_previos=request.form
            )

        orden = int(orden_raw) if orden_raw.isdigit() and int(orden_raw) > 0 else 1
        est_id_int = int(est_id)
            
        # Validar nombre duplicado dentro del mismo establecimiento
        existe_nombre = Box.query.filter_by(
            establecimiento_id=est_id_int,
            nombre=nombre
        ).first()

        if existe_nombre:
            flash(f'Ya existe un box llamado "{nombre}" en ese establecimiento.', 'warning')
            return render_template(
                'admin/boxes.html',
                boxes=Box.query.order_by(Box.establecimiento_id, Box.orden, Box.nombre).all(),
                establecimientos=establecimientos,
                filtro_actual='',
                datos_previos=request.form
            )

        # Validar orden duplicado dentro del mismo establecimiento
        existe_orden = Box.query.filter_by(
            establecimiento_id=est_id_int,
            orden=orden
        ).first()

        if existe_orden:
            flash(f'Ya existe un box con el orden {orden} en ese establecimiento.', 'warning')
            return render_template(
                'admin/boxes.html',
                boxes=Box.query.order_by(Box.establecimiento_id, Box.orden, Box.nombre).all(),
                establecimientos=establecimientos,
                filtro_actual='',
                datos_previos=request.form
            )
            
        try:
            nuevo_box = Box(
                establecimiento_id=est_id_int,
                nombre=nombre,
                orden=orden,
                activo=True
            )
            db.session.add(nuevo_box)
            db.session.commit()
            
            registrar_log_sistema(
                "Creación Box", 
                f"Box '{nombre}' creado para el establecimiento ID {est_id_int}.", 
                usuario=current_user
            )
            flash('Box creado exitosamente.', 'success')
            
        except Exception as e:
            db.session.rollback()
            registrar_log_sistema(
                "Error Creación Box",
                f"Error al crear box '{nombre}' para establecimiento ID {est_id_int}: {str(e)}",
                usuario=current_user
            )
            flash('Ocurrió un error al crear el box.', 'danger')
            
            return render_template(
                'admin/boxes.html',
                boxes=Box.query.order_by(Box.establecimiento_id, Box.orden, Box.nombre).all(),
                establecimientos=establecimientos,
                filtro_actual='',
                datos_previos=request.form
            )
            
        return redirect(url_for('admin.boxes'))

    # Lógica GET: Listar y Filtrar
    est_filtro = request.args.get('establecimiento_id', '').strip()
    query = Box.query
    
    if est_filtro and est_filtro.isdigit():
        query = query.filter_by(establecimiento_id=int(est_filtro))
        
    lista_boxes = query.order_by(Box.establecimiento_id, Box.orden, Box.nombre).all()
    
    return render_template(
        'admin/boxes.html', 
        boxes=lista_boxes, 
        establecimientos=establecimientos, 
        filtro_actual=est_filtro
    )

@admin_bp.route('/editar_box/<int:id>', methods=['POST'])
def editar_box(id):
    """Edita nombre, establecimiento y orden de un box existente."""
    box = Box.query.get_or_404(id)

    est_id = request.form.get('establecimiento_id', '').strip()
    nombre = request.form.get('nombre', '').strip()
    orden_raw = request.form.get('orden', '1').strip()

    if not est_id or not nombre:
        flash('El Establecimiento y el Nombre del box son obligatorios.', 'danger')
        return redirect(url_for('admin.boxes'))

    if not est_id.isdigit():
        flash('El establecimiento seleccionado no es válido.', 'danger')
        return redirect(url_for('admin.boxes'))

    orden = int(orden_raw) if orden_raw.isdigit() and int(orden_raw) > 0 else 1
    est_id_int = int(est_id)

    # Validar nombre duplicado, excluyendo el box actual
    existe_nombre = Box.query.filter(
        Box.establecimiento_id == est_id_int,
        Box.nombre == nombre,
        Box.id != box.id
    ).first()

    if existe_nombre:
        flash(f'Ya existe otro box llamado "{nombre}" en ese establecimiento.', 'warning')
        return redirect(url_for('admin.boxes'))

    # Validar orden duplicado, excluyendo el box actual
    existe_orden = Box.query.filter(
        Box.establecimiento_id == est_id_int,
        Box.orden == orden,
        Box.id != box.id
    ).first()

    if existe_orden:
        flash(f'Ya existe otro box con el orden {orden} en ese establecimiento.', 'warning')
        return redirect(url_for('admin.boxes'))

    try:
        box.establecimiento_id = est_id_int
        box.nombre = nombre
        box.orden = orden

        db.session.commit()

        registrar_log_sistema(
            "Edición Box",
            f"Box ID {box.id} actualizado a '{nombre}' (Establecimiento ID {est_id_int}, Orden {orden}).",
            usuario=current_user
        )
        flash('Box actualizado correctamente.', 'success')

    except Exception as e:
        db.session.rollback()
        registrar_log_sistema(
            "Error Edición Box",
            f"Error al editar box ID {box.id}: {str(e)}",
            usuario=current_user
        )
        flash('Ocurrió un error al actualizar el box.', 'danger')

    return redirect(url_for('admin.boxes'))

@admin_bp.route('/toggle_box/<int:id>', methods=['POST'])
def toggle_box(id):
    """Activa o desactiva un box rápidamente."""
    box = Box.query.get_or_404(id)

    try:
        box.activo = not box.activo
        db.session.commit()

        estado = "activado" if box.activo else "desactivado"
        registrar_log_sistema(
            "Cambio Estado Box",
            f"El box '{box.nombre}' fue {estado}.",
            usuario=current_user
        )
        flash(f"Box '{box.nombre}' {estado} correctamente.", 'success')

    except Exception as e:
        db.session.rollback()
        registrar_log_sistema(
            "Error Cambio Estado Box",
            f"Error al cambiar estado del box '{box.nombre}': {str(e)}",
            usuario=current_user
        )
        flash("Ocurrió un error al cambiar el estado del box.", 'danger')

    return redirect(url_for('admin.boxes'))

@admin_bp.route('/pantallas')
def pantallas():
    # TODO: Implementar CRUD completo en el futuro
    lista = Pantalla.query.order_by(Pantalla.establecimiento_id).all()
    return render_template('admin/pantallas.html', pantallas=lista)