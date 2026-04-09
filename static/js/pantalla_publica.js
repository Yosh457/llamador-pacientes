// static/js/pantalla_publica.js

document.addEventListener('DOMContentLoaded', () => {
    // Referencias a los elementos principales del DOM
    const overlay = document.getElementById('start-overlay');
    const container = document.getElementById('pantalla-app-container');
    const callTypeTitle = document.getElementById('call-type-title');
    const currentCallsList = document.getElementById('current-calls-list');
    const historyList = document.getElementById('history-list');

    // 1. Extraer el token de acceso desde el Meta Tag del HTML
    // Este token se utiliza para asegurar que solo pantallas autorizadas consulten la API
    const tokenMeta = document.querySelector('meta[name="pantalla-token"]');
    if (!tokenMeta) {
        console.error("Token de acceso no encontrado en el meta tag.");
        return;
    }
    const token = tokenMeta.content;

    // Variables de Estado (Para Audio y Renderizado Condicional)
    let lastCallId = null;
    let lastCallType = null;
    let audioInitialized = false;
    let synth = null; // Sintetizador de Tone.js para el "Ding-Dong"
    let selectedVoice = null; // Voz de SpeechSynthesis seleccionada

    // Variables Hash para evitar el parpadeo del HTML. 
    // Guardan una "firma" del último estado renderizado.
    let currentActiveHash = "";
    let currentHistoryHash = "";

    // ==========================================
    // INICIALIZACIÓN DE AUDIO (Requiere Clic)
    // ==========================================
    // Los navegadores bloquean el audio automático. El usuario DEBE hacer clic 
    // en la pantalla oscura ("overlay") para que este bloque se ejecute.
    async function initSystem() {
        // Desbloquear Tone.js e inicializar el sintetizador
        await Tone.start();
        synth = new Tone.Synth().toDestination();
        
        // Cargar y seleccionar la mejor voz en español
        loadVoice();
        
        // Truco para desbloquear SpeechSynthesis en navegadores basados en Chromium: 
        // hacer que el navegador hable un espacio en blanco inmediatamente tras el clic.
        if ('speechSynthesis' in window) {
            let u = new SpeechSynthesisUtterance(" ");
            window.speechSynthesis.speak(u);
        }
        
        // Ocultar la pantalla negra (overlay) y mostrar la interfaz de llamados
        overlay.style.display = 'none';
        container.classList.add('ready');
        audioInitialized = true;

        // Iniciar el ciclo de consultas (AJAX Polling) inmediatamente
        pollData();
        // Configurar la consulta repetitiva cada 3000 ms (3 segundos)
        setInterval(pollData, 3000);
    }

    // El evento 'click' en el overlay inicializa todo el sistema multimedia
    overlay.addEventListener('click', initSystem);

    // ==========================================
    // CONFIGURACIÓN DE VOZ (TTS)
    // ==========================================
    function loadVoice() {
        const setVoices = () => {
            const voices = speechSynthesis.getVoices();
            if (voices.length > 0) {
                // Array de prioridad: Buscar primero acento chileno, luego mexicano, etc.
                const priorities = ['es-CL', 'es-MX', 'es-US', 'es-ES', 'es-AR'];
                for (const lang of priorities) {
                    selectedVoice = voices.find(v => v.lang === lang);
                    if (selectedVoice) break; // Detener búsqueda si encontramos una coincidencia
                }
                // Fallback de seguridad: cualquier voz en español
                if (!selectedVoice) selectedVoice = voices.find(v => v.lang.startsWith('es-'));
            }
        };
        
        // Ejecutar inmediatamente si las voces ya cargaron, sino, esperar al evento.
        if (speechSynthesis.getVoices().length > 0) {
            setVoices();
        } else {
            speechSynthesis.onvoiceschanged = setVoices;
        }
    }

    // ==========================================
    // AJAX POLLING (La consulta silenciosa a Flask)
    // ==========================================
    async function pollData() {
        try {
            // Hacemos el Fetch al endpoint seguro en pantallas.py usando el token
            const response = await fetch(`/pantallas/api/estado/${token}`);
            if (!response.ok) throw new Error("Error de red o token inválido");
            
            const data = await response.json();
            
            // 1. Actualizar el DOM condicionalmente (Textos en pantalla)
            updateUI(data);
            
            // 2. Revisar si hay que emitir sonido/voz para un nuevo evento
            checkAnnouncement(data.activo);
            
        } catch (error) {
            console.error("Error obteniendo estado de la pantalla:", error);
        }
    }

    // Función auxiliar para mantener el formato original de la fecha (dd/mm/yyyy hh:mm)
    function formatTime(isoString) {
        if (!isoString) return '';
        const date = new Date(isoString);
        const day = String(date.getDate()).padStart(2, '0');
        const month = String(date.getMonth() + 1).padStart(2, '0');
        const year = date.getFullYear();
        const hours = String(date.getHours()).padStart(2, '0');
        const minutes = String(date.getMinutes()).padStart(2, '0');
        return `${day}/${month}/${year} ${hours}:${minutes}`;
    }

    // ==========================================
    // RENDERIZADO DEL DOM (Actualización Condicional)
    // ==========================================
    function updateUI(data) {
        // --- SECCIÓN: Llamado Activo ---
        // Creamos una "firma" o Hash del estado activo actual. 
        // Si es el mismo llamado en el mismo estado, la firma no cambia.
        const newActiveHash = data.activo ? `${data.activo.id}-${data.activo.tipo_llamado}` : "empty";
        
        // SOLO redibujamos el HTML si la firma cambió. Esto evita el parpadeo
        // de la animación CSS `@keyframes pantallaFadeIn` cada 3 segundos.
        if (newActiveHash !== currentActiveHash) {
            currentActiveHash = newActiveHash;
            
            if (data.activo) {
                // Mapeo de textos para el encabezado naranja
                const callTitles = {
                    'primer': 'PRIMER LLAMADO',
                    'segundo': 'SEGUNDO LLAMADO',
                    'tercer': 'TERCER Y ÚLTIMO LLAMADO'
                };
                
                callTypeTitle.textContent = callTitles[data.activo.tipo_llamado] || 'LLAMADO EN CURSO';
                callTypeTitle.style.display = 'block';

                let html = '';
                const timeStr = formatTime(data.activo.timestamp);
                
                // Renderizamos un cuadro blanco por cada paciente en el llamado activo
                data.activo.pacientes.forEach((p, idx) => {
                    const delay = idx * 150; // Pequeño efecto cascada si hay varios pacientes
                    html += `
                    <div class="current-call-item" style="animation-delay: ${delay}ms;">
                        <div class="call-main-info">
                            <p class="patient-name">${p.nombre}</p>
                            <p class="box-name">${data.activo.box}</p>
                        </div>
                        <div class="call-timestamp">${timeStr}</div>
                    </div>`;
                });
                currentCallsList.innerHTML = html;
            } else {
                // Si no hay llamados activos (ej: el médico cerró el llamado), mostrar pantalla base
                callTypeTitle.style.display = 'none';
                currentCallsList.innerHTML = `
                    <div class="waiting-message">
                        <div class="waiting-text">Recuerde llegar 15 minutos antes de su cita.</div>
                        <div class="waiting-text">No olvides registrar tu llegada en SOME.</div>
                        <div class="center-name">${data.establecimiento}</div>
                    </div>`;
            }
        }

        // --- SECCIÓN: Historial Inferior ---
        // Convertimos el objeto JSON de historial a String para usarlo como Hash
        const newHistoryHash = JSON.stringify(data.historial);
        
        // Si el historial cambió (ej: se agregó un llamado finalizado)
        if (newHistoryHash !== currentHistoryHash) {
            currentHistoryHash = newHistoryHash;
            let histHtml = '';
            
            // Iteramos sobre los últimos 4 llamados y creamos las tarjetas oscuras
            data.historial.forEach(h => {
                const pNames = h.pacientes.map(p => `<div class="patient-name-history">${p.nombre}</div>`).join('');
                histHtml += `
                <div class="history-group">
                    <div>${pNames}</div>
                    <div class="box-name-history">${h.box}</div>
                    <div class="call-timestamp-history">${formatTime(h.timestamp)}</div>
                </div>`;
            });
            historyList.innerHTML = histHtml;
        }
    }

    // ==========================================
    // LÓGICA MULTIMEDIA: AUDIO Y TTS (Voz)
    // ==========================================
    function checkAnnouncement(activo) {
        if (!activo) return; // Si no hay llamado activo, salimos

        // Comparamos el estado de memoria con el estado recibido.
        // Entramos aquí SOLO si el ID del llamado cambió (es un paciente nuevo)
        // o si el Tipo cambió (mismo paciente, pero pasó de 1er a 2do llamado).
        if (activo.id !== lastCallId || activo.tipo_llamado !== lastCallType) {
            
            // 1. Actualizamos la memoria para no repetir el anuncio en el próximo Polling
            lastCallId = activo.id;
            lastCallType = activo.tipo_llamado;
            
            // 2. Disparamos el parlante
            playAnnouncement(activo);
        }
    }

    function playAnnouncement(activo) {
        // Bloqueo de seguridad: No hacer ruido si el overlay no ha sido clickeado
        if (!audioInitialized || !('speechSynthesis' in window)) return;
        
        // Cortar abruptamente cualquier voz que esté hablando en este momento
        // Evita que los llamados se acumulen y hablen al mismo tiempo
        window.speechSynthesis.cancel(); 

        // Definir la frase introductoria según el nivel de llamado
        const callTexts = {
            'primer': 'Primer llamado para',
            'segundo': 'Segundo llamado para',
            'tercer': 'Tercer y último llamado para'
        };
        const intro = callTexts[activo.tipo_llamado] || 'Llamado para';
        
        // Unimos los nombres con 'y' para que la voz robótica los lea fluido y no como lista
        const names = activo.pacientes.map(p => p.nombre).join(', y ');
        
        // Expresión regular: reemplaza "BOX" (mayúscula) por "Box" (Minúscula) 
        // para que la TTS lo lea como palabra (bóx) y no deletreado (B-O-X).
        const boxStr = activo.box.replace(/BOX/gi, 'Box'); 

        // Armamos la frase completa
        const phrase = `${intro} ${names}. Diríjase a ${boxStr}.`;
        
        const utterance = new SpeechSynthesisUtterance(phrase);
        utterance.lang = 'es-CL';
        utterance.rate = 0.85; // Disminuimos la velocidad al 85% para mayor claridad en salas bulliciosas
        
        // Si encontramos una voz preferida en loadVoice(), se la asignamos
        if (selectedVoice) utterance.voice = selectedVoice;

        // 1. Tocar el timbre musical (Ding-Dong) usando el Sintetizador
        if (synth) {
            synth.triggerAttackRelease("G5", "8n", Tone.now());
            synth.triggerAttackRelease("E5", "8n", Tone.now() + 0.3); // 300ms de separación
        }

        // 2. Darle 1.5 segundos al timbre para que termine de sonar antes de que la voz empiece a hablar
        setTimeout(() => {
            window.speechSynthesis.speak(utterance);
        }, 1500);
    }
});