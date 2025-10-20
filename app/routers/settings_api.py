"""
Endpoints API para gestionar la configuración de la aplicación.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime

from app.database import get_db
from app.models import Settings
from app.schemas import SettingsResponse, SettingsUpdate, MessageResponse

router = APIRouter()


def get_or_create_settings(db: Session) -> Settings:
    """
    Obtiene la configuración o la crea si no existe.
    Solo debe haber un registro de configuración (id=1).
    """
    settings = db.query(Settings).filter(Settings.id == 1).first()
    
    if not settings:
        # Crear configuración por defecto
        settings = Settings(id=1)
        db.add(settings)
        db.commit()
        db.refresh(settings)
    
    return settings


@router.get("/settings", response_model=SettingsResponse)
async def get_settings(db: Session = Depends(get_db)):
    """
    Obtener la configuración actual de la aplicación.
    """
    settings = get_or_create_settings(db)
    return settings


@router.put("/settings", response_model=SettingsResponse)
async def update_settings(
    settings_data: SettingsUpdate,
    db: Session = Depends(get_db)
):
    """
    Actualizar la configuración de la aplicación.
    
    Solo actualiza los campos que se envían (los demás quedan igual).
    """
    settings = get_or_create_settings(db)
    
    # Actualizar solo los campos que se enviaron (exclude_unset=True)
    update_data = settings_data.model_dump(exclude_unset=True)
    
    for field, value in update_data.items():
        setattr(settings, field, value)
    
    # Actualizar timestamp
    # settings.updated_at = datetime.utcnow()
    setattr(settings, "updated_at", datetime.utcnow())
    
    db.commit()
    db.refresh(settings)
    
    return settings


@router.post("/settings/reset", response_model=MessageResponse)
async def reset_settings(db: Session = Depends(get_db)):
    """
    Restablecer la configuración a valores por defecto.
    """
    settings = get_or_create_settings(db)
    
    # Eliminar y recrear con valores por defecto
    db.delete(settings)
    db.commit()
    
    # Crear nueva configuración con valores por defecto
    new_settings = Settings(id=1)
    db.add(new_settings)
    db.commit()
    
    return MessageResponse(
        message="Configuración restablecida a valores por defecto",
        success=True
    )


@router.get("/settings/vinted-domains", response_model=list)
async def get_vinted_domains():
    """
    Obtener lista de dominios de Vinted disponibles.
    """
    return [
        {"value": "vinted.es", "label": "España (vinted.es)"},
        {"value": "vinted.fr", "label": "Francia (vinted.fr)"},
        {"value": "vinted.it", "label": "Italia (vinted.it)"},
        {"value": "vinted.com", "label": "Internacional (vinted.com)"},
        {"value": "vinted.de", "label": "Alemania (vinted.de)"},
        {"value": "vinted.at", "label": "Austria (vinted.at)"},
        {"value": "vinted.be", "label": "Bélgica (vinted.be)"},
        {"value": "vinted.nl", "label": "Países Bajos (vinted.nl)"},
        {"value": "vinted.pl", "label": "Polonia (vinted.pl)"},
        {"value": "vinted.cz", "label": "República Checa (vinted.cz)"},
        {"value": "vinted.lt", "label": "Lituania (vinted.lt)"},
        {"value": "vinted.lu", "label": "Luxemburgo (vinted.lu)"},
        {"value": "vinted.pt", "label": "Portugal (vinted.pt)"},
        {"value": "vinted.se", "label": "Suecia (vinted.se)"},
        {"value": "vinted.dk", "label": "Dinamarca (vinted.dk)"},
        {"value": "vinted.sk", "label": "Eslovaquia (vinted.sk)"},
        {"value": "vinted.ro", "label": "Rumania (vinted.ro)"},
    ]

# ============================================================================
# ENDPOINT PARA RECARGAR SCHEDULER
# ============================================================================

@router.post("/settings/reload-scheduler", response_model=MessageResponse)
async def reload_scheduler():
    """
    Recarga las tareas del scheduler después de cambiar configuración.
    
    Útil para aplicar cambios en auto_mark_notified_hours sin reiniciar.
    """
    try:
        from app.scheduler.task_manager import get_scheduler
        
        scheduler = get_scheduler()
        
        if not scheduler.is_running:
            return MessageResponse(
                message="Scheduler no está en ejecución",
                success=False
            )
        
        # Recargar tarea periódica de notificados
        scheduler.reload_notified_job()
        
        return MessageResponse(
            message="Scheduler recargado correctamente",
            success=True
        )
        
    except Exception as e:
        # logger.error(f"Error recargando scheduler: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error recargando scheduler: {str(e)}"
        )
