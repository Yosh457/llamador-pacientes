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
    // TOKEN DE ACCESO (SEGURIDAD Y SALAS)
    // ==========================================
    // Este token se utiliza para asegurar que solo pantallas autorizadas consulten la API
    const tokenMeta = document.querySelector('meta[name="pantalla-token"]');
    if (!tokenMeta) {
        console.error("Token de acceso no encontrado en el meta tag.");
        return;
    }

    // Extraemos el ID del establecimiento para unirnos a la Sala de WebSockets
    const estMeta = document.querySelector('meta[name="establecimiento-id"]');
    const establecimientoId = estMeta ? estMeta.content : null;

    // ==========================================
    // VARIABLES DE ESTADO Y COLA FIFO
    // ==========================================
    
    // 🔹 Cola FIFO de eventos (SOLUCIONA concurrencia y pérdida de llamados)
    let announcementQueue = [];
    let isAnnouncing = false;

    // 🔹 Control de duplicados de eventos (protección ante reconexiones)
    let procesadosIds = new Set();

    // 🔹 Control de la Pantalla Principal (Para limpiar al cerrar)
    let currentCallIdOnScreen = null; // ID del Llamado (para saber cuándo cerrarlo)
    let currentEventIdOnScreen = null; // ID del Evento (Para ocultarlo del historial)
    let nombreEstablecimientoGlobal = "";

    // 🔹 Almacenamiento del historial crudo de la BD
    let lastBackendHistory = []; // Se actualiza vía WebSockets

    // 🔹 Audio
    let audioInitialized = false;
    let synth = null; // Sintetizador de Tone.js para el "Ding-Dong"
    let selectedVoice = null; // Voz de SpeechSynthesis seleccionada

    // 🔹 Variables Hash para evitar el parpadeo del HTML. 
    let currentActiveHash = "";
    let currentHistoryHash = "";

    // ==========================================
    // WEBSOCKETS (TIEMPO REAL)
    // ==========================================
    const socket = io();

    socket.on('connect', () => {
        console.log("[WS] 🟢 Conectado al servidor WebSocket.");
        // Unirse a la sala específica de este establecimiento
        if (establecimientoId) {
            socket.emit('unirse_sala_espera', { establecimiento_id: establecimientoId });
        } else {
            console.warn("[WS] ⚠️ Falta meta tag 'establecimiento-id'.");
        }
    });

    socket.on('disconnect', () => {
        console.log("[WS] 🔴 Desconectado del servidor WebSocket.");
    });

    // Recepción del estado inicial al conectar (historial + llamado activo)
    socket.on('estado_inicial', (data) => {
        console.log("[WS] 📸 Estado inicial recibido:", data);
        nombreEstablecimientoGlobal = data.establecimiento;
        lastBackendHistory = data.historial || [];

        if (data.activo) {
            procesadosIds.add(data.activo.id);
            currentCallIdOnScreen = data.activo.llamado_id;
            currentEventIdOnScreen = data.activo.id;
            updateMainScreen(data.activo);
        } else {
            showEmptyState();
        }

        updateHistoryUI();
    });

    // Recepción de eventos en vivo
    socket.on('nuevo_evento_llamado', (evento) => {
        console.log("[WS] ⚡ Evento recibido en tiempo real:", evento.tipo_evento, evento);
        
        // Evitamos duplicados (Si el socket llega antes que el polling, lo procesamos)
        if (!procesadosIds.has(evento.id)) {
            procesadosIds.add(evento.id);

            // Mantener el historial local actualizado
            if (['PRIMER_LLAMADO', 'SEGUNDO_LLAMADO', 'TERCER_LLAMADO'].includes(evento.tipo_evento)) {
                lastBackendHistory.unshift({
                    id: evento.id,
                    box: evento.box,
                    timestamp: evento.timestamp,
                    pacientes: evento.pacientes
                });
                if (lastBackendHistory.length > 5) lastBackendHistory.pop();
            }

            announcementQueue.push(evento);
            processQueue();
        }
    });

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
    }

    // El evento 'click' en el overlay inicializa todo el sistema multimedia y comienza el ciclo de consultas a la API.
    overlay.addEventListener('click', initSystem);

    // ==========================================
    // CONFIGURACIÓN DE VOZ
    // ==========================================
    function loadVoice() {
        const setVoices = () => {
            const voices = speechSynthesis.getVoices();

            if (!voices.length) {
                console.warn("[TTS] No se encontraron voces en el sistema.");
                return;
            }

            // 1. Prioridad: Voces Femeninas de LATAM (México prioritario)
            const preferredLatamVoices = ['Paulina', 'Mia', 'Sabina'];
            selectedVoice = voices.find(v => 
                v.lang.toLowerCase().includes('mx') && 
                preferredLatamVoices.some(name => v.name.toLowerCase().includes(name.toLowerCase()))
            );

            // 2. Fallback 1: Si no hay mujeres de LATAM, cualquier voz femenina en español
            if (!selectedVoice) {
                const femaleVoices = ['Helena', 'Laura', 'Monica', 'Paulina', 'Sabina'];
                selectedVoice = voices.find(v => 
                    v.lang.toLowerCase().startsWith('es') &&
                    femaleVoices.some(name => v.name.toLowerCase().includes(name.toLowerCase()))
                );
            }

            // 3. Fallback 2: Las voces nativas de Google (si están usando Chrome)
            if (!selectedVoice) {
                selectedVoice = voices.find(v => v.name.toLowerCase().includes('google español'));
            }

            // 4. Fallback 3: Cualquier voz en español mexicano (es-MX) - ¡Aunque sea Raúl!
            if (!selectedVoice) {
                selectedVoice = voices.find(v => v.lang.toLowerCase() === 'es-mx');
            }

            // 5. Fallback Final: Literalmente la primera voz en español que encuentre
            if (!selectedVoice) {
                selectedVoice = voices.find(v => v.lang.toLowerCase().startsWith('es'));
            }

            if (selectedVoice) {
                console.log(`[TTS] Voz seleccionada: ${selectedVoice.name} (${selectedVoice.lang})`);
            } else {
                console.warn("[TTS] Advertencia: No se pudo seleccionar una voz en español.");
            }
        };

        if (speechSynthesis.getVoices().length > 0) {
            setVoices();
        } else {
            speechSynthesis.onvoiceschanged = setVoices;
        }
    }

    // ==========================================
    // MOTOR FIFO (PROCESAMIENTO DE EVENTOS)
    // ==========================================
    function processQueue() {
        // Si ya está hablando o no hay eventos, salir
        if (isAnnouncing || announcementQueue.length === 0) return;

        isAnnouncing = true;
        const evento = announcementQueue.shift(); // Extraer el primer evento de la fila

        // 🛡️ DEFENSIVO: Validar que el evento tenga tipo
        if (!evento.tipo_evento) {
            console.warn("Evento sin tipo_evento:", evento);
            isAnnouncing = false;
            processQueue();
            return;
        }

        // 🔹 Si el evento es un cierre y corresponde al que está en pantalla, limpiamos la TV.
        if (['ATENDIDO', 'NSP'].includes(evento.tipo_evento)) {
            if (evento.llamado_id === currentCallIdOnScreen) {
                showEmptyState();
            }
            // Como es un cierre, no hay voz. Pasamos inmediatamente al siguiente en la cola.
            isAnnouncing = false;
            processQueue();
            return;
        }

        // 🔹 VALIDACIÓN: Solo permitir eventos válidos de anuncio
        const eventosAnuncio = ['PRIMER_LLAMADO', 'SEGUNDO_LLAMADO', 'TERCER_LLAMADO'];

        if (!eventosAnuncio.includes(evento.tipo_evento)) {
            console.warn("Evento no reconocido (ignorado):", evento.tipo_evento);
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
        utterance.rate = 0.85; // Disminuimos la velocidad al 85% para mayor claridad

        // Asignamos la voz y respetamos su idioma nativo para evitar fallos en el navegador
        if (selectedVoice) {
            utterance.voice = selectedVoice;
            utterance.lang = selectedVoice.lang;
        } else {
            utterance.lang = 'es-MX'; // Fallback a México si no detectó ninguna voz
        }

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