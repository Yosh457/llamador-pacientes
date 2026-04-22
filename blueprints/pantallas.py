# blueprints/pantallas.py
from flask import Blueprint, render_template, jsonify, request
from models import Pantalla, LlamadoEvento, Llamado

pantallas_bp = Blueprint('pantallas', __name__, template_folder='../templates', url_prefix='/pantallas')

@pantallas_bp.route('/sala/<token>')
def sala_espera(token):
    """
    Renderiza la vista a pantalla completa de la sala de espera.
    Se accede mediante un token único por establecimiento.
    """
    pantalla = Pantalla.query.filter_by(token_acceso=token, activo=True).first_or_404()
    return render_template('pantallas/sala_espera.html', pantalla=pantalla)

@pantallas_bp.route('/api/estado/<token>')
def api_estado(token):
    """
    Endpoint JSON consumido vía AJAX Polling.
    Utiliza Event Sourcing para la cola de audio y para el historial visual en cascada.
    """
    pantalla = Pantalla.query.filter_by(token_acceso=token, activo=True).first()
    if not pantalla:
        return jsonify({"error": "Token inválido o pantalla inactiva"}), 403

    est_id = pantalla.establecimiento_id
    last_id = request.args.get('last_id', type=int)

    # 1. Construir el Historial Visual basado en EVENTOS
    # Traemos los últimos 5 eventos de anuncio. El frontend filtrará el que está activo.
    historial_db = LlamadoEvento.query.filter(
        LlamadoEvento.establecimiento_id == est_id,
        LlamadoEvento.tipo_evento.in_(['PRIMER_LLAMADO', 'SEGUNDO_LLAMADO', 'TERCER_LLAMADO'])
    ).order_by(LlamadoEvento.id.desc()).limit(5).all()

    historial_data = []
    for h in historial_db:
        historial_data.append({
            "id": h.id, # ID del evento (clave para el filtrado frontend)
            "box": h.box.nombre if h.box else "Sin Box",
            "timestamp": h.fecha_evento.isoformat(),
            "pacientes": h.pacientes_snapshot
        })

    # 2. Lógica de Sincronización de Cola (Polling con last_id)
    # Incluimos Cierres y Cancelaciones para que el JS sepa cuándo limpiar la pantalla.
    tipos_validos = ['PRIMER_LLAMADO', 'SEGUNDO_LLAMADO', 'TERCER_LLAMADO', 'CIERRE', 'CANCELACION']

    if last_id is None:
        # Carga inicial: No encolar audios viejos, solo establecer el punto de partida
        latest = LlamadoEvento.query.filter_by(establecimiento_id=est_id).order_by(LlamadoEvento.id.desc()).first()
        
        # Enviamos el llamado activo actual para evitar que la pantalla quede en blanco al recargar
        llamado_activo = Llamado.query.filter_by(
            establecimiento_id=est_id,
            estado='ACTIVO'
        ).first()

        activo_data = None
        if llamado_activo:
            # Obtener el evento exacto asociado a este llamado activo
            ultimo_evento = LlamadoEvento.query.filter_by(
                llamado_id=llamado_activo.id
            ).order_by(LlamadoEvento.id.desc()).first()

            if ultimo_evento:
                activo_data = {
                    "id": ultimo_evento.id, # ID del Evento
                    "llamado_id": llamado_activo.id, # ID del Llamado
                    "tipo_evento": ultimo_evento.tipo_evento,
                    "box": llamado_activo.box.nombre if llamado_activo.box else "Sin Box",
                    "timestamp": ultimo_evento.fecha_evento.isoformat(),
                    "pacientes": ultimo_evento.pacientes_snapshot
                }

        return jsonify({
            "establecimiento": pantalla.establecimiento.nombre,
            "activo": activo_data,
            "nuevos_eventos": [],
            "last_id": latest.id if latest else 0,
            "historial": historial_data
        })
    else:
        # Consultas subsecuentes: Traer eventos de anuncio y cierres que sean más nuevos que last_id
        nuevos_db = LlamadoEvento.query.filter(
            LlamadoEvento.establecimiento_id == est_id,
            LlamadoEvento.id > last_id,
            LlamadoEvento.tipo_evento.in_(tipos_validos)
        ).order_by(LlamadoEvento.id.asc()).all()

        nuevos_eventos = []
        for n in nuevos_db:
            nuevos_eventos.append({
                "id": n.id,
                "llamado_id": n.llamado_id, # ID del Llamado para que JS identifique a quién cerrar
                "tipo_evento": n.tipo_evento,
                "box": n.box.nombre if n.box else "Sin Box",
                "timestamp": n.fecha_evento.isoformat(),
                "pacientes": n.pacientes_snapshot
            })

        new_last_id = nuevos_db[-1].id if nuevos_db else last_id

        return jsonify({
            "establecimiento": pantalla.establecimiento.nombre,
            "nuevos_eventos": nuevos_eventos,
            "last_id": new_last_id,
            "historial": historial_data
        })