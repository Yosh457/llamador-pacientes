# 🏥 Llamador de Pacientes - Red APS

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![Flask](https://img.shields.io/badge/Flask-3.x-green.svg)
![WebSockets](https://img.shields.io/badge/WebSockets-Socket.IO-orange.svg)
![Database](https://img.shields.io/badge/Database-MySQL-blue.svg)

Sistema web en tiempo real para la **Red de Atención Primaria de Salud Municipal de Alto Hospicio**, orientado a gestionar el llamado de pacientes en salas de espera, asegurando orden, trazabilidad y visibilidad en atención.

---

## 🚀 Características Principales

### 🔔 Llamados en Tiempo Real
- Comunicación instantánea mediante **WebSockets**
- Actualización automática de pantallas (sin recarga)
- Reproducción de audio (TTS + alerta sonora)

### 👥 Gestión por Roles
- **Admin:** configuración global del sistema
- **Supervisor:** monitoreo y reportes
- **Operador:** ejecución de llamados

### 🔒 Seguridad
- Protección CSRF habilitada en formularios
- Control de acceso basado en roles (RBAC)
- Validación de propiedad de llamados (anti-IDOR)
- Captura de IP en eventos de auditoría

### 📊 Trazabilidad Completa
- Registro de eventos:
  - Creación
  - Primer / Segundo / Tercer llamado
  - Cierre / Cancelación
- Auditoría con:
  - Usuario
  - Fecha/hora
  - IP origen

---

## 🔄 Flujo del Sistema

1. Operador crea llamado desde formulario
2. Se guarda en base de datos
3. Se registra evento de auditoría
4. Se emite evento vía WebSocket
5. Pantalla pública recibe y muestra llamado en tiempo real
6. Se reproduce audio automáticamente

---

## ⚠️ Notas Técnicas

- El sistema implementa una **máquina de estados controlada**, evitando transiciones inválidas: 
  `PRIMER → SEGUNDO → TERCER → (CIERRE / CANCELACIÓN)`
- Se garantiza que cada operador tenga **un único llamado activo simultáneamente**.
- Todas las acciones generan eventos persistentes en la tabla `LlamadoEvento`, siguiendo un enfoque de **event sourcing simplificado**.
- Los eventos se emiten en tiempo real mediante **Flask-SocketIO**, únicamente después de confirmar la transacción en base de datos (post-commit), garantizando consistencia entre estado y visualización.
- Las pantallas públicas se suscriben a **salas (rooms)** por establecimiento, evitando contaminación de eventos entre recintos.
- Se implementan validaciones backend para:
  - Evitar saltos de estado
  - Prevenir accesos indebidos (anti-IDOR)
  - Asegurar consistencia transaccional
- El caché del navegador está deshabilitado para evitar inconsistencias en navegación y estados visuales.
- El sistema desacopla la lógica de negocio (backend) de la visualización (pantallas públicas), permitiendo escalabilidad y mantenimiento independiente.
---

## 🛠️ Tecnologías Utilizadas

- **Arquitectura:** Application Factory Pattern (`create_app`)
- **Backend:** Python 3 + Flask (Blueprints)
- **Tiempo Real:** Flask-SocketIO
- **Base de Datos:** MySQL + SQLAlchemy
- **Frontend:** HTML, Jinja2, JS, TailwindCSS
- **Audio:** Web Speech API + Tone.js

---

## 📂 Estructura del Proyecto

El sistema está organizado en módulos desacoplados utilizando Blueprints, lo que permite escalabilidad y mantenimiento sencillo:
```text
LlamadorPacientes/
├── blueprints/          # Lógica de rutas y controladores
│   ├── admin.py         # Gestión de recintos, boxes, pantallas y usuarios
│   ├── auth.py          # Autenticación y recuperación de clave
│   ├── llamados.py      # Lógica de creación y transición de estados
│   ├── pantallas.py     # Vista pública (TV)
│   └── reportes.py      # Dashboard de métricas y exportación Excel
├── static/              # Archivos estáticos
│   ├── css/             # Estilos personalizados (style.css)
│   ├── docs/            # Documentación del Proyecto (Manuales)
│   ├── img/             # Assets gráficos (logos institucionales)
│   └── js/              # Scripts (pantalla_publica.js, sesión, etc.)
├── templates/           # Vistas HTML (Jinja2)
│   ├── admin/           # CRUDs de mantenedores y auditoría
│   ├── auth/            # Formularios de acceso y seguridad
│   ├── llamados/        # Interfaz del operador e historial
│   ├── pantallas/       # Vista Smart TV (sala_espera.html)
│   └── reportes/        # Dashboard y KPIs
├── utils/               # Módulos transversales y utilidades
│   ├── __init__.py      # Exportador de utilidades (simplifica importaciones)
│   ├── decorators.py    # Decoradores de permisos por rol 
│   ├── email.py         # Lógica de envío de credenciales
│   ├── helpers.py       # Funciones auxiliares y captura de IP
│   └── sockets.py       # Configuración de Rooms y eventos WebSocket
├── venv/                # Entorno virtual
├── app.py               # Punto de entrada de la aplicación (Factory Pattern)
├── models.py            # Modelos de Base de Datos (SQLAlchemy)
├── extensions.py        # Inicialización de extensiones globales
├── crear_superadmin.py  # Creación de Usuario Admin
├── requirements.txt     # Dependencias del proyecto
└── .env                 # Variables de Entorno
```
---

## ⚙️ Instalación y Despliegue Local

1. Clonar el repositorio:

```bash
git clone https://github.com/Yosh457/llamador-pacientes
cd llamador-pacientes
```
2. Crear entorno virtual:

```bash
python -m venv venv
# En Windows:
venv\Scripts\activate
# En Mac/Linux:
source venv/bin/activate
```
3. Instalar dependencias:

```bash
pip install -r requirements.txt
```
4. Configurar variables de entorno (.env):

```env
SECRET_KEY=tu_clave_secreta_super_segura
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=tu_password_de_base_de_datos
MYSQL_DB=llamador_pacientes_db
FLASK_DEBUG=1
EMAIL_USUARIO=tu_correo@institucional.cl
EMAIL_CONTRASENA=tu_contraseña_de_aplicacion
```
5. Crear la base de datos:

```sql
CREATE DATABASE llamador_pacientes_db;
```
6. Crear las tablas:

```bash
flask shell
```

> Nota: El proyecto utiliza Application Factory Pattern, por lo que `app.py` inicializa automáticamente la aplicación y verifica la base de datos al ejecutarse.

Dentro de la shell interactiva de Flask ejecuta línea por línea lo siguiente:

```python
from models import db
db.create_all()
exit()
```
7. Crear el usuario admin:

```bash
python crear_superadmin.py
```
8. Ejecutar la aplicación:

```bash
python app.py
```

Accede en tu navegador a: http://localhost:5000

## ▶️ Uso rápido (Quick Start)

Una vez que el servidor esté corriendo localmente en `http://localhost:5000`:

1. **Iniciar sesión** con tu usuario administrador.
2. **Configurar el sistema** (si es la primera ejecución): ir a "Establecimientos" y "Boxes" para crearlos.
3. **Crear usuarios:** ir a "Usuarios" y crear perfiles de Operador asignándolos al establecimiento creado.
4. **Abrir la Pantalla Pública:**
   - Ir a "Pantallas"
   - Copiar el enlace de la TV
   - Abrirlo en una nueva pestaña
   - Activar pantalla completa (`F11`)
   - Hacer clic en la pantalla para habilitar el audio
5. **Probar el flujo completo:**
   - Iniciar sesión en otra ventana como Operador
   - Crear un llamado
   - Verificar actualización en tiempo real en la pantalla pública

## 🛡️ Matriz de Permisos (Resumen)

| Rol        | Crear Llamados | Historial        | Reportes | Administración |
|------------|----------------|------------------|----------|----------------|
| Admin      | ❌             | Global           | Global   | ✅             |
| Supervisor | ❌             | Por establecimiento | Local | ❌             |
| Operador   | ✅             | Propios          | ❌       | ❌             |
---
Desarrollado por **Josting Silva**  
**Analista Programador – Unidad de TICs**  
Departamento de Salud  
Municipalidad de Alto Hospicio
