"""
Punto de entrada principal de la aplicación Vinted Scraper.

Este archivo:
1. Crea la aplicación FastAPI
2. Configura archivos estáticos y templates
3. Registra las rutas (routers)
4. Inicializa la base de datos
5. Arranca el scheduler automático
6. Gestiona el ciclo de vida de la aplicación

⭐ VERSIÓN MEJORADA:
- Task Manager actualizado con get_task_manager()
- Mejor manejo de errores en startup
- Logs más informativos
- Health check mejorado con info del scheduler
"""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager

from config import settings
from app.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Gestiona el ciclo de vida de la aplicación.
    
    Lifespan es una función especial de FastAPI que se ejecuta:
    - ANTES de que la app empiece a recibir peticiones (startup)
    - DESPUÉS de que la app termine (shutdown)
    
    Uso del context manager (async with):
    - Todo ANTES del 'yield' se ejecuta al INICIAR
    - Todo DESPUÉS del 'yield' se ejecuta al TERMINAR
    """
    # ========================================================================
    # --- STARTUP ---
    # ========================================================================
    print("\n" + "="*80)
    print("🚀 VINTED SCRAPER - INICIANDO")
    print("="*80)
    
    # 1. Inicializar base de datos (crear tablas si no existen)
    print("\n📊 Inicializando base de datos...")
    try:
        init_db()
        print("✅ Base de datos lista")
    except Exception as e:
        print(f"❌ Error inicializando BD: {e}")
        raise
    
    # 2. Inicializar configuración por defecto si no existe
    print("\n⚙️  Verificando configuración...")
    from app.database import SessionLocal
    from app.models import Settings
    
    db = SessionLocal()
    try:
        settings_record = db.query(Settings).filter(Settings.id == 1).first()
        if not settings_record:
            print("   📝 Creando configuración por defecto...")
            default_settings = Settings(id=1)
            db.add(default_settings)
            db.commit()
            db.refresh(default_settings)
            print("   ✅ Configuración inicializada")
            print(f"      • Dominio: {default_settings.vinted_domain}")
            print(f"      • Notificaciones de errores: {'Activadas' if default_settings.scheduler_error_notifications_enabled else 'Desactivadas'}")
        else:
            print(f"   ✅ Configuración cargada")
            print(f"      • Dominio: {settings_record.vinted_domain}")
            print(f"      • User-Agents: {'Rotativo' if settings_record.user_agent_rotation else 'Fijo'}")
            print(f"      • Proxies: {'Activados' if settings_record.proxies_enabled else 'Desactivados'}")
            print(f"      • Notificaciones de errores: {'Activadas (' + str(settings_record.scheduler_error_threshold) + ' fallos)' if settings_record.scheduler_error_notifications_enabled else 'Desactivadas'}")
    except Exception as e:
        print(f"   ⚠️  Error al inicializar configuración: {e}")
        print("   Continuando con valores por defecto...")
    finally:
        db.close()
    
    # 3. Iniciar el scheduler para ejecuciones automáticas
    print("\n📅 Iniciando scheduler...")
    try:
        # ⭐ CAMBIO IMPORTANTE: Usar get_task_manager() en lugar de get_scheduler()
        from app.scheduler.task_manager import get_task_manager
        
        task_manager = get_task_manager()
        task_manager.start()
        
        # Obtener estadísticas del scheduler
        status = task_manager.get_status()
        print(f"   ✅ Scheduler iniciado")
        print(f"      • Búsquedas activas: {status['search_jobs_count']}")
        print(f"      • Jobs de mantenimiento: {status['maintenance_jobs_count']}")
        print(f"      • Total de jobs: {status['jobs_count']}")
        
        # Mostrar próximas ejecuciones si hay
        if status['next_executions']:
            print(f"\n   ⏰ Próximas ejecuciones:")
            for job in status['next_executions'][:3]:
                print(f"      • {job['name']}: {job['next_run']}")
    
    except ImportError as e:
        print(f"   ❌ Error importando task_manager: {e}")
        print("   El servidor continuará SIN scheduler automático")
    except Exception as e:
        print(f"   ❌ Error iniciando scheduler: {e}")
        print("   El servidor continuará SIN scheduler automático")
    
    # 4. Información final
    print("\n" + "="*80)
    print("✅ APLICACIÓN LISTA")
    print("="*80)
    print(f"📍 Servidor: http://localhost:8000")
    print(f"📚 API Docs: http://localhost:8000/docs")
    print(f"📊 Dashboard: http://localhost:8000/")
    print(f"📅 Scheduler: http://localhost:8000/scheduler")
    print(f"⚙️  Configuración: http://localhost:8000/settings")
    print("="*80 + "\n")
    
    yield  # La aplicación se ejecuta aquí (manejando peticiones)
    
    # ========================================================================
    # --- SHUTDOWN ---
    # ========================================================================
    print("\n" + "="*80)
    print("🛑 VINTED SCRAPER - DETENIENDO")
    print("="*80)
    
    # Detener el scheduler de forma ordenada
    try:
        from app.scheduler.task_manager import get_task_manager
        task_manager = get_task_manager()
        task_manager.stop()
        print("✅ Scheduler detenido correctamente")
    except Exception as e:
        print(f"⚠️  Error deteniendo scheduler: {e}")
    
    print("="*80)
    print("👋 ¡HASTA PRONTO!")
    print("="*80 + "\n")


# ============================================================================
# CREAR LA APLICACIÓN FASTAPI
# ============================================================================

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Sistema de scraping automático para encontrar productos en Vinted con scheduler avanzado y notificaciones",
    lifespan=lifespan,
    debug=settings.DEBUG
)


# ============================================================================
# EXCEPTION HANDLERS
# ============================================================================

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    """
    Maneja errores de validación de Pydantic de forma más clara.
    Útil para debugging durante el desarrollo.
    """
    print(f"❌ Error de validación en {request.method} {request.url.path}")
    for error in exc.errors():
        print(f"   • {error['loc']}: {error['msg']}")
    
    return JSONResponse(
        status_code=422,
        content={
            "detail": exc.errors(),
            "body": str(exc.body) if hasattr(exc, 'body') else None
        }
    )


# ============================================================================
# ARCHIVOS ESTÁTICOS Y TEMPLATES
# ============================================================================

# Montar archivos estáticos (CSS, JS, imágenes)
# Esto hace que /static/css/style.css sea accesible en la web
try:
    app.mount("/static", StaticFiles(directory="static"), name="static")
except RuntimeError:
    print("⚠️  Carpeta 'static' no encontrada, continuando sin archivos estáticos")

# Configurar templates Jinja2
# Esto nos permite renderizar HTML con datos dinámicos
templates = Jinja2Templates(directory="templates")

# ⭐ Filtro para banderas Unicode a partir de código país
def country_flag(code):
    """
    Convierte un código de país (ES, FR, etc.) en su emoji de bandera.
    Ejemplo: country_flag("ES") -> "🇪🇸"
    """
    if not code or len(code) != 2:
        return ""
    code = code.upper()
    OFFSET = 127397  # Offset Unicode para banderas
    return chr(ord(code[0]) + OFFSET) + chr(ord(code[1]) + OFFSET)

templates.env.filters["country_flag"] = country_flag

# ⭐ Filtro para formatear fechas de forma amigable
def format_date(dt, format='%d/%m/%Y %H:%M'):
    """
    Formatea una fecha de forma amigable.
    """
    if not dt:
        return "N/A"
    try:
        return dt.strftime(format)
    except:
        return str(dt)

templates.env.filters["format_date"] = format_date

# ⭐ Filtro para formatear números con separador de miles
def format_number(num):
    """
    Formatea un número con separador de miles.
    Ejemplo: 1234567 -> "1,234,567"
    """
    if num is None:
        return "0"
    try:
        return "{:,.0f}".format(float(num))
    except:
        return str(num)

templates.env.filters["format_number"] = format_number

# Hacer templates disponible globalmente en la app
app.state.templates = templates


# ============================================================================
# REGISTRAR ROUTERS
# ============================================================================

from app.routers import web, api, settings_web, settings_api

# Router web (páginas HTML) - sin prefijo, rutas en la raíz
app.include_router(web.router, tags=["Web"])

# Router web de configuración (página /settings)
app.include_router(settings_web.router, tags=["Settings Web"])

# Router API (endpoints REST) - con prefijo /api
app.include_router(api.router, prefix="/api", tags=["API"])

# Router API de configuración
app.include_router(settings_api.router, prefix="/api", tags=["Settings API"])


# ============================================================================
# ENDPOINTS ESPECIALES
# ============================================================================

@app.get("/health")
async def health_check():
    """
    Endpoint de health check mejorado.
    
    Útil para monitoreo y verificar que:
    - La app está viva
    - La BD está accesible
    - El scheduler está funcionando
    """
    from app.database import SessionLocal
    
    # Verificar BD
    db_healthy = False
    try:
        db = SessionLocal()
        db.execute("SELECT 1")
        db.close()
        db_healthy = True
    except Exception as e:
        print(f"⚠️  Health check - BD no accesible: {e}")
    
    # Verificar Scheduler
    scheduler_healthy = False
    scheduler_info = {}
    try:
        from app.scheduler.task_manager import get_task_manager
        task_manager = get_task_manager()
        status = task_manager.get_status()
        scheduler_healthy = status['running']
        scheduler_info = {
            "running": status['running'],
            "jobs": status['jobs_count'],
            "active_searches": status['search_jobs_count']
        }
    except Exception as e:
        print(f"⚠️  Health check - Scheduler no accesible: {e}")
    
    # Respuesta
    overall_healthy = db_healthy and scheduler_healthy
    
    return {
        "status": "healthy" if overall_healthy else "degraded",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "components": {
            "database": "healthy" if db_healthy else "unhealthy",
            "scheduler": "healthy" if scheduler_healthy else "unhealthy"
        },
        "scheduler": scheduler_info if scheduler_healthy else None
    }


@app.get("/version")
async def version_info():
    """
    Información de versión de la aplicación.
    """
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "debug": settings.DEBUG
    }


# ============================================================================
# EJECUTAR SERVIDOR
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    
    # Uvicorn es el servidor ASGI que ejecuta FastAPI
    uvicorn.run(
        "main:app",  # Formato: "archivo:variable"
        host="0.0.0.0",  # Escuchar en todas las interfaces
        port=8000,
        reload=True,  # Auto-reload cuando cambiamos código (solo en desarrollo)
        log_level="info"
    )