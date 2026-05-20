# blueprints/pantallas.py
from flask import Blueprint, render_template
from models import Pantalla

pantallas_bp = Blueprint('pantallas', __name__, template_folder='../templates', url_prefix='/pantallas')

@pantallas_bp.route('/sala/<token>')
def sala_espera(token):
    """
    Renderiza la vista a pantalla completa de la sala de espera.
    Se accede mediante un token único por establecimiento.
    Los datos en tiempo real se manejan vía Flask-SocketIO.
    """
    pantalla = Pantalla.query.filter_by(token_acceso=token, activo=True).first_or_404()
    return render_template('pantallas/sala_espera.html', pantalla=pantalla)