"""
Helper para acceder a la configuración de la aplicación.

Proporciona funciones de ayuda para obtener y actualizar la configuración
desde cualquier parte de la aplicación.
"""

from sqlalchemy.orm import Session
from app.models import Settings
from typing import Optional, List


def get_settings(db: Session) -> Settings:
    """
    Obtiene la configuración actual.
    Si no existe, la crea con valores por defecto.
    
    Args:
        db: Sesión de base de datos
        
    Returns:
        Objeto Settings con la configuración
    """
    settings = db.query(Settings).filter(Settings.id == 1).first()
    
    if not settings:
        settings = Settings(id=1)
        db.add(settings)
        db.commit()
        db.refresh(settings)
    
    return settings


def get_vinted_domain(db: Session) -> str:
    """
    Obtiene el dominio de Vinted configurado.
    
    Args:
        db: Sesión de base de datos
        
    Returns:
        Dominio de Vinted (ej: "vinted.es")
    """
    settings = get_settings(db)
    return settings.vinted_domain


def get_vinted_url(db: Session, vinted_id: str) -> str:
    """
    Construye la URL completa de un producto en Vinted.
    
    Args:
        db: Sesión de base de datos
        vinted_id: ID del producto en Vinted
        
    Returns:
        URL completa del producto
    """
    domain = get_vinted_domain(db)
    return f"https://www.{domain}/items/{vinted_id}"


def get_proxies(db: Session) -> Optional[List[str]]:
    """
    Obtiene la lista de proxies configurados.
    
    Args:
        db: Sesión de base de datos
        
    Returns:
        Lista de proxies o None si no están activados
    """
    settings = get_settings(db)
    
    if not settings.proxies_enabled or not settings.proxy_list:
        return None
    
    # Parsear lista de proxies (uno por línea)
    proxies = [
        proxy.strip() 
        for proxy in settings.proxy_list.split('\n') 
        if proxy.strip()
    ]
    
    return proxies if proxies else None


def get_banned_words(db: Session) -> List[str]:
    """
    Obtiene la lista de palabras prohibidas globales.
    
    Args:
        db: Sesión de base de datos
        
    Returns:
        Lista de palabras prohibidas (en minúsculas)
    """
    settings = get_settings(db)
    
    if not settings.global_banned_words:
        return []
    
    words = [
        word.strip().lower() 
        for word in settings.global_banned_words.split('\n') 
        if word.strip()
    ]
    
    return words


def get_banned_sellers(db: Session) -> List[str]:
    """
    Obtiene la lista de vendedores bloqueados globalmente.
    
    Args:
        db: Sesión de base de datos
        
    Returns:
        Lista de IDs/nombres de vendedores bloqueados
    """
    settings = get_settings(db)
    
    if not settings.global_banned_sellers:
        return []
    
    sellers = [
        seller.strip() 
        for seller in settings.global_banned_sellers.split('\n') 
        if seller.strip()
    ]
    
    return sellers


def get_request_headers(db: Session) -> dict:
    """
    Obtiene los headers configurados para requests HTTP.
    
    Args:
        db: Sesión de base de datos
        
    Returns:
        Diccionario con headers
    """
    settings = get_settings(db)
    
    headers = {
        "User-Agent": settings.user_agent
    }
    
    # Añadir headers adicionales si están configurados
    if settings.default_headers:
        headers.update(settings.default_headers)
    
    return headers


def should_filter_product(
    db: Session,
    title: str,
    description: Optional[str],
    price: float,
    seller_id: Optional[str]
) -> bool:
    """
    Determina si un producto debe ser filtrado según la configuración global.
    
    Args:
        db: Sesión de base de datos
        title: Título del producto
        description: Descripción del producto
        price: Precio del producto
        seller_id: ID del vendedor
        
    Returns:
        True si el producto debe ser filtrado (rechazado), False si debe aceptarse
    """
    settings = get_settings(db)
    
    # Filtrar por precio mínimo
    if settings.global_min_price > 0 and price < settings.global_min_price:
        return True
    
    # Filtrar por palabras prohibidas
    banned_words = get_banned_words(db)
    if banned_words:
        text = f"{title} {description or ''}".lower()
        for word in banned_words:
            if word in text:
                return True
    
    # Filtrar por vendedores bloqueados
    if seller_id:
        banned_sellers = get_banned_sellers(db)
        if seller_id in banned_sellers:
            return True
    
    return False


def get_telegram_config(db: Session) -> Optional[dict]:
    """
    Obtiene la configuración de Telegram.
    
    Args:
        db: Sesión de base de datos
        
    Returns:
        Dict con bot_token y chat_id, o None si no está configurado
    """
    settings = get_settings(db)
    
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        return None
    
    return {
        "bot_token": settings.telegram_bot_token,
        "chat_id": settings.telegram_chat_id
    }


def get_discord_config(db: Session) -> Optional[dict]:
    """
    Obtiene la configuración de Discord.
    
    Args:
        db: Sesión de base de datos
        
    Returns:
        Dict con webhook_url y bot_token, o None si no está configurado
    """
    settings = get_settings(db)
    
    if not settings.discord_webhook_url:
        return None
    
    return {
        "webhook_url": settings.discord_webhook_url,
        "bot_token": settings.discord_bot_token
    }
