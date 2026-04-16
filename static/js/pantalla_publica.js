// static/js/pantalla_publica.js

document.addEventListener('DOMContentLoaded', () => {
    // ==========================================
    // REFERENCIAS A ELEMENTOS DEL DOM
    // ==========================================
    const overlay = document.getElementById('start-overlay');
    const container = document.getElementById('pantalla-app-container');
    const callTypeTitle = document.getElementById('call-type-title');
    const currentCallsList = document.getElementById('current-calls-list');
    const historyList = document.getElementById('history-list');

    // ==========================================
    // TOKEN DE ACCESO (SEGURIDAD)
    // ==========================================
    // Este token se utiliza para asegurar que solo pantallas autorizadas consulten la API
    const tokenMeta = document.querySelector('meta[name="pantalla-token"]');
    if (!tokenMeta) {
        console.error("Token de acceso no encontrado en el meta tag.");
        return;
    }
    const token = tokenMeta.content;

    // ==========================================
    // VARIABLES DE ESTADO
    // ==========================================
    
    // 🔹 Cola FIFO de eventos (SOLUCIONA concurrencia y pérdida de llamados)
    let announcementQueue = [];
    let isAnnouncing = false;
    let lastEventId = null; // Puntero de sincronización para evitar procesar eventos antiguos

    // 🔹 Control de la Pantalla Principal (Para limpiar al cerrar)
    let currentCallIdOnScreen = null; // ID del Llamado (para saber cuándo cerrarlo)
    let currentEventIdOnScreen = null; // ID del Evento (Para ocultarlo del historial)
    let nombreEstablecimientoGlobal = "";

    // 🔹 Almacenamiento del historial crudo de la BD
    let lastBackendHistory = [];

    // 🔹 Audio
    let audioInitialized = false;
    let synth = null; // Sintetizador de Tone.js para el "Ding-Dong"
    let selectedVoice = null; // Voz de SpeechSynthesis seleccionada

    // 🔹 Variables Hash para evitar el parpadeo del HTML. 
    let currentActiveHash = "";
    let currentHistoryHash = "";

    // ==========================================
    // INICIALIZACIÓN DE AUDIO (REQUIERE INTERACCIÓN DEL USUARIO)
    // ==========================================
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

    // El evento 'click' en el overlay inicializa todo el sistema multimedia y comienza el ciclo de consultas a la API.
    overlay.addEventListener('click', initSystem);

    // ==========================================
    // CONFIGURACIÓN DE VOZ
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
    // AJAX POLLING (EVENT SOURCING)
    // ==========================================
    async function pollData() {
        try {
            // Construir URL de la API con token de acceso
            let url = `/pantallas/api/estado/${token}`;
            // Enviar último ID para traer solo eventos nuevos
            if (lastEventId !== null) url += `?last_id=${lastEventId}`;

            const response = await fetch(url);
            if (!response.ok) throw new Error("Error de red o token inválido");

            const data = await response.json();
            nombreEstablecimientoGlobal = data.establecimiento;

             // 🔹 Manejar el estado en la carga inicial
            if (lastEventId === null) {
                if (data.activo) {
                    currentCallIdOnScreen = data.activo.llamado_id;
                    currentEventIdOnScreen = data.activo.id;
                    updateMainScreen(data.activo);
                } else {
                    showEmptyState();
                }
            }
            // 🔹 Actualizar puntero de eventos
            lastEventId = data.last_id;
            lastBackendHistory = data.historial;

            // 🔹 Encolar eventos nuevos (FIFO)
            if (data.nuevos_eventos?.length > 0) {
                announcementQueue.push(...data.nuevos_eventos);
            }

            // 🔹 Actualizar historial visual independientemente de la cola
            updateHistoryUI();

            // 🔹 Procesar cola de anuncios
            processQueue();

        } catch (error) {
            console.error("Error polling pantalla pública:", error);
        }
    }

    // ==========================================
    // MOTOR FIFO (CLAVE DEL SISTEMA)
    // ==========================================
    function processQueue() {
        // Si ya está hablando o no hay eventos, salir
        if (isAnnouncing || announcementQueue.length === 0) return;

        isAnnouncing = true;

        const evento = announcementQueue.shift(); // Extraer el primer evento de la fila

        // 🔹 Si el evento es un cierre y corresponde al que está en pantalla, limpiamos la TV.
        if (['CIERRE', 'CANCELACION', 'EXPIRACION'].includes(evento.tipo_evento)) {
            if (evento.llamado_id === currentCallIdOnScreen) {
                showEmptyState();
            }
            // Como es un cierre, no hay voz. Pasamos inmediatamente al siguiente en la cola.
            isAnnouncing = false;
            processQueue();
            return;
        }

        // 1. Actualizar UI principal (Es un anuncio de voz)
        currentCallIdOnScreen = evento.llamado_id;
        currentEventIdOnScreen = evento.id;

        updateMainScreen(evento);

        // 🔴 MAGIA CASCADA: Refrescamos el historial para que oculte este evento y muestre el anterior
        updateHistoryUI();

        // 2. Reproducir audio y continuar al terminar (callback)
        playAnnouncement(evento, () => {
            // Callback: Se ejecuta cuando la voz termina de hablar
            // Esperar 2 segundos de respiro antes de pasar al siguiente paciente
            setTimeout(() => {
                isAnnouncing = false;
                processQueue(); // siguiente en cola
            }, 2000);
        });
    }

    // ==========================================
    // RENDER ESTADO BASE (EL MENSAJE INSTITUCIONAL)
    // ==========================================
    function showEmptyState() {
        callTypeTitle.style.display = 'none';
        currentCallsList.innerHTML = `
            <div class="waiting-message">
                <div class="waiting-text">Recuerde llegar 15 minutos antes de su cita.</div>
                <div class="waiting-text">No olvides registrar tu llegada en SOME.</div>
                <div class="center-name">${nombreEstablecimientoGlobal}</div>
            </div>`;
        currentCallIdOnScreen = null;
        currentEventIdOnScreen = null; // Al ser nulo, revelará todo el historial
        currentActiveHash = "empty"; // Resetear hash

        // 🔴 MAGIA CASCADA: Al limpiar la pantalla, el último llamado cae al historial
        updateHistoryUI();
    }

    // ==========================================
    // RENDER LLAMADO ACTIVO (OPTIMIZADO SIN PARPADEO)
    // ==========================================
    function updateMainScreen(evento) {
        // Firma única del estado actual para evitar re-render innecesario
        const newHash = `${evento.id}-${evento.tipo_evento}`;

        // Evitar re-render innecesario (anti-flicker)
        if (newHash === currentActiveHash) return;
        currentActiveHash = newHash;

        const callTitles = {
            // Mapeo de textos para el encabezado naranja según el tipo de llamado
            'PRIMER_LLAMADO': 'PRIMER LLAMADO',
            'SEGUNDO_LLAMADO': 'SEGUNDO LLAMADO',
            'TERCER_LLAMADO': 'TERCER Y ÚLTIMO LLAMADO'
        };

        callTypeTitle.textContent = callTitles[evento.tipo_evento] || 'LLAMADO EN CURSO';
        callTypeTitle.style.display = 'block';

        // Compatibilidad: soporta array o string desde backend
        let pacientes = evento.pacientes;

        if (Array.isArray(pacientes)) {
            pacientes = pacientes.map(p => p.nombre).join(', ');
        }

        const timeStr = formatTime(evento.timestamp);

        currentCallsList.innerHTML = `
        <div class="current-call-item">
            <div class="call-main-info">
                <p class="patient-name">${pacientes}</p>
                <p class="box-name">${evento.box}</p>
            </div>
            <div class="call-timestamp">${timeStr}</div>
        </div>`;
    }

    // ==========================================
    // HISTORIAL CASCADA (OPTIMIZADO SIN PARPADEO)
    // ==========================================
    function updateHistoryUI() {
        // Filtrar los eventos: Ocultar el evento actualmente en pantalla 
        // y cualquier evento futuro que aún esté esperando en la cola FIFO
        let displayHistory = lastBackendHistory.filter(h => {
            if (currentEventIdOnScreen === null) return true; // Mostrar todo si la pantalla está base
            return h.id < currentEventIdOnScreen; // Mostrar solo eventos más antiguos que el actual
        });

        // Asegurar que solo mostramos 4 cajas
        displayHistory = displayHistory.slice(0, 4);

        // Firma única del historial para evitar re-render innecesario
        const newHistoryHash = JSON.stringify(displayHistory);

        // Solo re-render si cambió el historial
        if (newHistoryHash !== currentHistoryHash) {
            currentHistoryHash = newHistoryHash;
            let histHtml = '';

            displayHistory.forEach(h => {
                let nombres = h.pacientes;

                if (Array.isArray(nombres)) {
                    nombres = nombres.map(p => p.nombre).join(', ');
                }

                // Mostrar cada paciente en línea separada para mejor legibilidad
                const pNames = nombres.split(', ').map(n =>
                    `<div class="patient-name-history">${n}</div>`
                ).join('');

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
    // FORMATO FECHA (DD/MM/YYYY HH:MM)
    // ==========================================
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
    // AUDIO + TTS (CON CALLBACK FIFO)
    // ==========================================
    function playAnnouncement(evento, onComplete) {
        // Seguridad: no ejecutar si el audio no fue inicializado
        if (!audioInitialized || !('speechSynthesis' in window)) {
            onComplete();
            return;
        }

        // Definir la frase a anunciar según el tipo de llamado y los datos del evento
        const callTexts = {
            'PRIMER_LLAMADO': 'Primer llamado para',
            'SEGUNDO_LLAMADO': 'Segundo llamado para',
            'TERCER_LLAMADO': 'Tercer y último llamado para'
        };

        let names = evento.pacientes;

        if (Array.isArray(names)) {
            names = names.map(p => p.nombre).join(', ');
        }

        // Convertir última coma en "y" para lectura natural
        if (names.includes(',')) {
            const lastCommaIndex = names.lastIndexOf(',');
            names = names.substring(0, lastCommaIndex) + ' y ' + names.substring(lastCommaIndex + 1);
        }

        // Evitar que TTS deletree "BOX"
        const boxStr = evento.box.replace(/BOX/gi, 'Box');

        // Armamos la frase completa para el anuncio
        const phrase = `${callTexts[evento.tipo_evento] || 'Llamado para'} ${names}. Diríjase a ${boxStr}.`;

        const utterance = new SpeechSynthesisUtterance(phrase);
        utterance.lang = 'es-CL';
        utterance.rate = 0.85; // Disminuimos la velocidad al 85% para mayor claridad en salas bulliciosas

        // Si encontramos una voz preferida en loadVoice(), se la asignamos
        if (selectedVoice) utterance.voice = selectedVoice;

        // Definimos el callback para cuando termine de hablar
        utterance.onend = () => onComplete();
        utterance.onerror = (e) => {
            console.error("Error en TTS:", e);
            onComplete();
        };

        // 1. Tocar el timbre musical (Ding-Dong) usando el Sintetizador de Tone.js
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