# blueprints/pantallas.py
from flask import Blueprint, render_template, jsonify
from models import Pantalla, Llamado

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
    Endpoint JSON consumido vía AJAX Polling desde la pantalla pública.
    Devuelve el llamado activo actual y los últimos 4 finalizados/cancelados.
    """
    pantalla = Pantalla.query.filter_by(token_acceso=token, activo=True).first()
    if not pantalla:
        return jsonify({"error": "Token inválido o pantalla inactiva"}), 403

    est_id = pantalla.establecimiento_id

    # 1. Buscar el Llamado Activo más reciente
    llamado_activo = Llamado.query.filter_by(
        establecimiento_id=est_id,
        estado='ACTIVO',
        visible_en_pantalla=True
    ).order_by(Llamado.fecha_actualizacion.desc()).first()

    activo_data = None
    if llamado_activo:
        activo_data = {
            "id": llamado_activo.id,
            "box": llamado_activo.box.nombre,
            "tipo_llamado": llamado_activo.tipo_llamado_actual.lower(), # primer, segundo, tercer
            "timestamp": llamado_activo.fecha_actualizacion.isoformat(),
            "pacientes": [{"nombre": p.paciente_nombre} for p in llamado_activo.pacientes]
        }

    # 2. Buscar Historial (Últimos 4 llamados que ya NO están activos)
    historial = Llamado.query.filter(
        Llamado.establecimiento_id == est_id,
        Llamado.estado != 'ACTIVO'
    ).order_by(Llamado.fecha_actualizacion.desc()).limit(4).all()

    historial_data = []
    for h in historial:
        historial_data.append({
            "box": h.box.nombre,
            "timestamp": h.fecha_actualizacion.isoformat(),
            "pacientes": [{"nombre": p.paciente_nombre} for p in h.pacientes]
        })

    return jsonify({
        "establecimiento": pantalla.establecimiento.nombre,
        "activo": activo_data,
        "historial": historial_data
    })