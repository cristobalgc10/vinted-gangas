"""
Configuración centralizada de la aplicación.
Este archivo gestiona todas las variables de configuración usando Pydantic.
"""

from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """
    Clase que define todas las configuraciones de la aplicación.
    Pydantic automáticamente carga valores desde variables de entorno
    o usa los valores por defecto definidos aquí.
    """
    
    # Configuración de la aplicación
    APP_NAME: str = "Vinted Scraper"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = True
    
    # Base de datos
    DATABASE_URL: str = "sqlite:///./vinted_scraper.db"
    # Nota: SQLite es simple para empezar, pero podríamos cambiar a:
    # PostgreSQL: "postgresql://user:password@localhost/dbname"
    
    # Telegram Bot
    TELEGRAM_BOT_TOKEN: Optional[str] = None
    TELEGRAM_CHAT_ID: Optional[str] = None
    # Para obtener estos valores:
    # 1. Habla con @BotFather en Telegram para crear un bot
    # 2. Usa @userinfobot para obtener tu chat_id
    
    # Scraping
    REQUEST_TIMEOUT: int = 30  # segundos
    USER_AGENT: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    MAX_RETRIES: int = 3
    RETRY_DELAY: int = 5  # segundos entre reintentos
    
    # Scheduler
    SCHEDULER_TIMEZONE: str = "Europe/Madrid"
    
    class Config:
        """
        Configuración de Pydantic.
        env_file: permite cargar variables desde un archivo .env
        """
        env_file = ".env"
        env_file_encoding = "utf-8"


# Instancia global de configuración
settings = Settings()
