// static/js/llamados.js
document.addEventListener('DOMContentLoaded', function() {
    
    // 1. Reloj en tiempo real
    const relojEl = document.getElementById('reloj-local');
    if (relojEl) {
        setInterval(() => {
            const now = new Date();
            relojEl.textContent = now.toLocaleTimeString('es-CL');
        }, 1000);
    }

    // 2. Manejo del Modal de Confirmación
    const modal = document.getElementById('confirmation-modal');
    const btnCancel = document.getElementById('cancel-action');
    const btnConfirm = document.getElementById('confirm-action');
    const modalTitle = document.getElementById('modal-title');
    const modalDesc = document.getElementById('modal-desc');
    let formToSubmit = null;

    document.querySelectorAll('.btn-confirm-action').forEach(btn => {
        btn.addEventListener('click', function(e) {
            e.preventDefault();
            formToSubmit = this.closest('form');
            const actionType = this.dataset.action;

            if (actionType === 'cerrar') {
                modalTitle.textContent = "Finalizar Atención";
                modalDesc.textContent = "¿Confirmas que el paciente fue atendido correctamente?";
                btnConfirm.className = "px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition text-sm font-semibold";
            } else if (actionType === 'cancelar') {
                modalTitle.textContent = "Cancelar Llamado";
                modalDesc.textContent = "¿Confirmas que el paciente NO se presentó a la consulta?";
                btnConfirm.className = "px-4 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700 transition text-sm font-semibold";
            }

            modal.classList.remove('hidden');
        });
    });

    if (btnCancel) {
        btnCancel.addEventListener('click', () => {
            modal.classList.add('hidden');
            formToSubmit = null;
        });
    }

    if (btnConfirm) {
        btnConfirm.addEventListener('click', () => {
            if (formToSubmit) {
                // Prevenir múltiples clics
                btnConfirm.disabled = true;
                btnConfirm.textContent = "Procesando...";
                formToSubmit.submit();
            }
        });
    }
});