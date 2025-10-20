"""
Router web para la página de configuración - ACTUALIZADO

Cambios:
- user_agent_list (Text) - Lista de User-Agents
- user_agent_rotation (Boolean) - Rotar User-Agents
"""

from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.models import Settings
from app.schemas import MessageResponse
from datetime import datetime

router = APIRouter()


def get_or_create_settings(db: Session) -> Settings:
    """
    Obtiene la configuración o la crea si no existe.
    """
    settings = db.query(Settings).filter(Settings.id == 1).first()
    
    if not settings:
        settings = Settings(id=1)
        db.add(settings)
        db.commit()
        db.refresh(settings)
    
    return settings


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request, db: Session = Depends(get_db)):
    """
    Página de configuración de la aplicación.
    """
    settings = get_or_create_settings(db)
    
    return request.app.state.templates.TemplateResponse(
        "settings.html",
        {
            "request": request,
            "settings": settings
        }
    )


@router.post("/settings/update")
async def update_settings_form(
    request: Request,
    db: Session = Depends(get_db),
    # Notificaciones
    push_notifications_enabled: Optional[str] = Form(None),
    webhook_url: Optional[str] = Form(None),
    telegram_bot_token: Optional[str] = Form(None),
    telegram_chat_id: Optional[str] = Form(None),
    discord_webhook_url: Optional[str] = Form(None),
    discord_bot_token: Optional[str] = Form(None),
    # Scraping - ACTUALIZADO
    user_agent: str = Form(...),  # Mantener para compatibilidad
    user_agent_list: Optional[str] = Form(None),  # NUEVO
    user_agent_rotation: Optional[str] = Form(None),  # NUEVO
    default_headers: Optional[str] = Form(None),
    max_products_per_search: int = Form(...),
    proxies_enabled: Optional[str] = Form(None),
    proxy_list: Optional[str] = Form(None),
    proxy_rotation: Optional[str] = Form(None),
    # Filtros globales
    global_banned_words: Optional[str] = Form(None),
    global_min_price: float = Form(0.0),
    global_banned_sellers: Optional[str] = Form(None),
    # Gestión de datos
    auto_delete_products_days: int = Form(...),
    auto_mark_notified_hours: int = Form(...),
    max_products_in_db: int = Form(...),
    # Preferencias de interfaz
    theme: str = Form(...),
    language: str = Form(...),
    currency: str = Form(...),
    vinted_domain: str = Form(...)
):
    """
    Actualizar configuración desde el formulario.
    """
    settings = get_or_create_settings(db)
    
    # Convertir checkboxes (vienen como "on" o None)
    settings.push_notifications_enabled = push_notifications_enabled == "on"
    settings.proxies_enabled = proxies_enabled == "on"
    settings.proxy_rotation = proxy_rotation == "on"
    settings.user_agent_rotation = user_agent_rotation == "on"  # NUEVO
    
    # Actualizar campos de texto (convertir vacíos a None)
    settings.webhook_url = webhook_url if webhook_url else None
    settings.telegram_bot_token = telegram_bot_token if telegram_bot_token else None
    settings.telegram_chat_id = telegram_chat_id if telegram_chat_id else None
    settings.discord_webhook_url = discord_webhook_url if discord_webhook_url else None
    settings.discord_bot_token = discord_bot_token if discord_bot_token else None
    
    # Scraping - ACTUALIZADO
    settings.user_agent = user_agent  # Mantener para compatibilidad
    
    # NUEVO: User-Agent List
    if user_agent_list and user_agent_list.strip():
        settings.user_agent_list = user_agent_list.strip()
    else:
        # Fallback: si está vacío, usar user_agent antiguo
        settings.user_agent_list = user_agent
    
    settings.max_products_per_search = max_products_per_search
    settings.proxy_list = proxy_list if proxy_list else None
    
    # Parsear headers JSON si existe
    if default_headers:
        import json
        try:
            settings.default_headers = json.loads(default_headers)
        except:
            settings.default_headers = None
    else:
        settings.default_headers = None
    
    # Filtros globales
    settings.global_banned_words = global_banned_words if global_banned_words else None
    settings.global_min_price = global_min_price
    settings.global_banned_sellers = global_banned_sellers if global_banned_sellers else None
    
    # Gestión de datos
    settings.auto_delete_products_days = auto_delete_products_days
    settings.auto_mark_notified_hours = auto_mark_notified_hours
    settings.max_products_in_db = max_products_in_db
    
    # Preferencias de interfaz
    settings.theme = theme
    settings.language = language
    settings.currency = currency
    settings.vinted_domain = vinted_domain
    
    # Actualizar timestamp
    settings.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(settings)

    # Recargar scheduler si cambió auto_mark_notified_hours
    try:
        from app.scheduler.task_manager import get_scheduler
        scheduler = get_scheduler()
        if scheduler.is_running:
            scheduler.reload_notified_job()
    except:
        pass  # No fallar si el scheduler no está corriendo
    
    # Devolver mensaje de éxito para HTMX
    return HTMLResponse(content='''
        <div class="bg-green-100 border border-green-400 text-green-700 px-4 py-3 rounded relative mb-4" role="alert">
            <strong class="font-bold">¡Configuración guardada!</strong>
            <span class="block sm:inline">Los cambios se han aplicado correctamente.</span>
        </div>
    ''')


@router.post("/settings/reset")
async def reset_settings_form(request: Request, db: Session = Depends(get_db)):
    """
    Restablecer configuración a valores por defecto.
    """
    settings = get_or_create_settings(db)
    
    # Eliminar y recrear
    db.delete(settings)
    db.commit()
    
    new_settings = Settings(id=1)
    db.add(new_settings)
    db.commit()
    
    # Devolver mensaje y recargar página
    return HTMLResponse(content='''
        <div class="bg-blue-100 border border-blue-400 text-blue-700 px-4 py-3 rounded relative mb-4" role="alert">
            <strong class="font-bold">¡Configuración restablecida!</strong>
            <span class="block sm:inline">Se han restaurado los valores por defecto.</span>
        </div>
        <script>
            setTimeout(() => window.location.reload(), 1500);
        </script>
    ''')
