# utils/sockets.py
from flask import request
from flask_socketio import join_room, leave_room, emit

def get_room_name(establecimiento_id):
    """Genera el nombre de la sala para un establecimiento específico."""
    return f"establecimiento_{establecimiento_id}"

def register_socket_events(socketio):
    """
    Registra todos los eventos WebSocket del sistema.

    ✔ Evita imports circulares
    ✔ Maneja rooms por establecimiento
    ✔ Permite debugging y validación de conexión
    """

    @socketio.on('connect')
    def handle_connect():
        print(f"[Socket] 🟢 Cliente conectado: {request.sid}")

    @socketio.on('disconnect')
    def handle_disconnect():
        print(f"[Socket] 🔴 Cliente desconectado: {request.sid}")

    @socketio.on('unirse_sala_espera')
    def handle_join_room(data):
        """Une una pantalla a la sala de su establecimiento y le envía el estado inicial."""
        establecimiento_id = data.get('establecimiento_id')

        if not establecimiento_id:
            print(f"[Socket] ⚠️ Cliente {request.sid} sin establecimiento_id")
            return
        
        try:
            establecimiento_id = int(establecimiento_id)
        except ValueError:
            print(f"[Socket] ⚠️ establecimiento_id inválido: {establecimiento_id}")
            return

        room = get_room_name(establecimiento_id)
        join_room(room)

        print(f"[Socket] 📺 Cliente {request.sid} unido a: {room}")

        # Confirmación al cliente (muy útil para debugging)
        emit(
            'conexion_establecida',
            {
                'status': 'ok',
                'room': room
            },
            to=request.sid
        )
        
        # ==========================================================
        # OBTENER Y EMITIR EL ESTADO INICIAL A LA PANTALLA
        # ==========================================================
        # Importación local (Lazy Import) para evitar ciclos
        from models import Llamado, LlamadoEvento, Establecimiento 

        establecimiento = Establecimiento.query.get(establecimiento_id)
        nombre_est = establecimiento.nombre if establecimiento else "Sala de Espera"

        # 1. Obtener Historial (Últimos 5 llamados de anuncio)
        historial_db = LlamadoEvento.query.filter(
            LlamadoEvento.establecimiento_id == establecimiento_id,
            LlamadoEvento.tipo_evento.in_(['PRIMER_LLAMADO', 'SEGUNDO_LLAMADO', 'TERCER_LLAMADO'])
        ).order_by(LlamadoEvento.id.desc()).limit(5).all()

        historial_data = [{
            "id": h.id,
            "box": h.box.nombre if h.box else "Sin Box",
            "timestamp": h.fecha_evento.isoformat(),
            "pacientes": h.pacientes_snapshot
        } for h in historial_db]

        # 2. Obtener Llamado Activo Actual
        llamado_activo = Llamado.query.filter_by(establecimiento_id=establecimiento_id, estado='ACTIVO').first()
        activo_data = None
        
        if llamado_activo:
            ultimo_evento = LlamadoEvento.query.filter_by(
                llamado_id=llamado_activo.id
            ).order_by(LlamadoEvento.id.desc()).first()

            if ultimo_evento:
                activo_data = {
                    "id": ultimo_evento.id,
                    "llamado_id": llamado_activo.id,
                    "tipo_evento": ultimo_evento.tipo_evento,
                    "box": llamado_activo.box.nombre if llamado_activo.box else "Sin Box",
                    "timestamp": ultimo_evento.fecha_evento.isoformat(),
                    "pacientes": ultimo_evento.pacientes_snapshot
                }

        # 3. Emitir Estado Inicial solo al cliente que se acaba de conectar
        emit('estado_inicial', {
            "establecimiento": nombre_est,
            "activo": activo_data,
            "historial": historial_data
        }, to=request.sid)

    # Evento para salir de la sala (opcional, pero recomendado para limpieza)
    @socketio.on('salir_sala')
    def handle_leave_room(data):
        """Permite a una pantalla salir de la sala de su establecimiento."""
        establecimiento_id = data.get('establecimiento_id')

        if not establecimiento_id:
            return

        try:
            establecimiento_id = int(establecimiento_id)
        except ValueError:
            print(f"[Socket] ⚠️ establecimiento_id inválido: {establecimiento_id}")
            return

        room = get_room_name(establecimiento_id)
        leave_room(room)

        print(f"[Socket] 🚪 Cliente {request.sid} salió de: {room}")