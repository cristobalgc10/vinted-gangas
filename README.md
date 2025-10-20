# 🔍 Vinted Scraper

Sistema automatizado de scraping para encontrar productos con buen precio en Vinted.

## 📋 Características

- ✅ Búsquedas personalizadas con todos los filtros de Vinted
- ✅ Filtros adicionales: países, palabras baneadas, vendedores bloqueados
- ✅ Ejecución periódica configurable por búsqueda
- ✅ Notificaciones por Telegram (Discord y navegador próximamente)
- ✅ Interfaz web para gestionar búsquedas
- ✅ Base de datos SQLite para almacenar búsquedas y productos

## 🏗️ Arquitectura

```
vinted-scraper/
├── app/
│   ├── models.py           # Modelos de base de datos (Search, Product, Notification)
│   ├── database.py         # Configuración de SQLAlchemy
│   ├── routers/            # Rutas de la API y páginas web
│   ├── scraper/            # Lógica de scraping (Vinted y otros)
│   ├── scheduler/          # Tareas programadas (APScheduler)
│   ├── notifications/      # Sistema de notificaciones
│   └── utils/              # Utilidades y filtros
├── static/                 # CSS, JS, imágenes
├── templates/              # Templates HTML (Jinja2)
├── config.py               # Configuración centralizada
└── main.py                 # Punto de entrada
```

## 🚀 Instalación

### 1. Clonar el repositorio

```bash
git clone <tu-repo>
cd vinted-scraper
```

### 2. Crear entorno virtual

```bash
python -m venv venv

# Activar en Linux/Mac:
source venv/bin/activate

# Activar en Windows:
venv\Scripts\activate
```

### 3. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 4. Configurar variables de entorno

```bash
cp .env.example .env
# Editar .env con tus valores (Telegram bot, etc.)
```

### 5. Ejecutar la aplicación

```bash
python main.py
```

La aplicación estará disponible en:
- **Web**: http://localhost:8000
- **Documentación API**: http://localhost:8000/docs
- **Documentación alternativa**: http://localhost:8000/redoc

## 📊 Base de Datos

El proyecto usa **SQLite** por defecto (archivo `vinted_scraper.db`).

### Modelos principales:

- **Search**: Configuración de búsquedas
- **Product**: Productos encontrados
- **Notification**: Registro de notificaciones enviadas
- **ScrapingLog**: Logs de ejecuciones

La base de datos se crea automáticamente al iniciar la aplicación.

## 🔧 Configuración

Edita el archivo `.env` o `config.py`:

```python
# Aplicación
DEBUG=True                              # Modo debug
APP_NAME="Vinted Scraper"

# Base de datos
DATABASE_URL=sqlite:///./vinted_scraper.db

# Telegram (opcional)
TELEGRAM_BOT_TOKEN=tu_token_aqui
TELEGRAM_CHAT_ID=tu_chat_id_aqui

# Scraping
REQUEST_TIMEOUT=30                      # Timeout de requests
MAX_RETRIES=3                          # Reintentos en caso de error
```

## 📖 Uso (Próximamente)

### Crear una búsqueda

1. Acceder a la interfaz web
2. Crear nueva búsqueda con filtros
3. Configurar intervalo de ejecución
4. Activar la búsqueda

### Ver productos encontrados

Los productos se mostrarán en la sección "Productos" con:
- Imagen
- Título y descripción
- Precio
- Link a Vinted
- Datos del vendedor

## 🛠️ Desarrollo

### Estructura del código

- Usamos **FastAPI** para el backend
- **SQLAlchemy** como ORM
- **Jinja2** para templates
- **HTMX** para interactividad (próximamente)
- **TailwindCSS** para estilos (próximamente)

### Siguiente pasos

- [ ] Implementar scraper de Vinted
- [ ] Crear interfaz web
- [ ] Añadir sistema de notificaciones
- [ ] Implementar scheduler
- [ ] Tests unitarios

## ⚠️ Disclaimer

Este proyecto es solo para fines educativos. Asegúrate de cumplir con los términos de servicio de Vinted y respetar robots.txt.

## 📝 Licencia

MIT
