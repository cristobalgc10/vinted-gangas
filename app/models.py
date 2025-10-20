"""
Modelos de base de datos usando SQLAlchemy ORM.

Cada clase representa una tabla en la base de datos.
Los campos de clase se convierten en columnas de la tabla.

⭐ VERSIÓN OPTIMIZADA CON:
- SchedulerLog para historial del scheduler
- Índices optimizados para mejores consultas
- Campos adicionales en ScrapingLog para métricas
- Nuevos campos en Settings para notificaciones de errores
"""

from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, JSON, Text, Index
from sqlalchemy.orm import relationship
from datetime import datetime

from app.database import Base


class Search(Base):
    """
    Modelo para almacenar configuraciones de búsquedas.
    
    Cada registro representa una búsqueda que se ejecutará periódicamente.
    Ejemplo: "Zapatillas Nike talla 42 entre 20-50€ cada 5 minutos"
    """
    __tablename__ = "searches"
    
    # Campos básicos
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    
    # --- PARÁMETROS DE BÚSQUEDA DE VINTED ---
    query = Column(String(500))
    category_ids = Column(JSON)
    brand_ids = Column(JSON)
    size_ids = Column(JSON)
    color_ids = Column(JSON)
    material_ids = Column(JSON)
    platform_ids = Column(JSON)
    status_ids = Column(JSON)
    
    # Rango de precios
    price_from = Column(Float, nullable=True)
    price_to = Column(Float, nullable=True)
    
    # Orden de resultados
    order = Column(String(50), default="newest_first")
    
    # --- FILTROS PERSONALIZADOS ---
    allowed_countries = Column(JSON)
    banned_words = Column(JSON)
    banned_seller_ids = Column(JSON)
    
    # --- CONFIGURACIÓN DE EJECUCIÓN ---
    interval_minutes = Column(Integer, default=5, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    
    # --- TIMESTAMPS ---
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_run_at = Column(DateTime, nullable=True)
    last_success_at = Column(DateTime, nullable=True)
    
    # --- QUERY STRING ORIGINAL DE VINTED ---
    vinted_query_string = Column(Text, nullable=True)
    
    # --- RELACIONES CON OTRAS TABLAS ---
    products = relationship("Product", back_populates="search", cascade="all, delete-orphan")
    scraping_logs = relationship("ScrapingLog", back_populates="search", cascade="all, delete-orphan")
    scheduler_logs = relationship("SchedulerLog", back_populates="search", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Search(id={self.id}, name='{self.name}', active={self.is_active})>"


class Product(Base):
    """
    Modelo para almacenar productos encontrados en Vinted.
    
    Cada registro es un producto que cumplió los criterios de una búsqueda.
    """
    __tablename__ = "products"
    
    # Identificación
    id = Column(Integer, primary_key=True, index=True)
    search_id = Column(Integer, ForeignKey("searches.id"), nullable=False, index=True)
    
    # --- DATOS DEL PRODUCTO DE VINTED ---
    vinted_id = Column(String(100), unique=True, nullable=False, index=True)
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    price = Column(Float, nullable=False)
    currency = Column(String(10), default="EUR")
    brand = Column(String(200), nullable=True)
    size = Column(String(50), nullable=True)
    condition = Column(String(100), nullable=True)
    url = Column(String(1000), nullable=False)
    image_url = Column(String(1000), nullable=True)
    
    # --- RELACIÓN CON VENDEDOR ---
    seller_id = Column(Integer, ForeignKey("sellers.id"), nullable=True, index=True)
    seller_vinted_id = Column(String(100), nullable=True, index=True)
    seller_name = Column(String(200), nullable=True)
    seller_country = Column(String(10), nullable=True)
    
    # --- CONTROL Y ESTADO ---
    is_available = Column(Boolean, default=True, nullable=False)
    is_notified = Column(Boolean, default=False, nullable=False)
    is_favorite = Column(Boolean, default=False, nullable=False)
    found_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    notified_at = Column(DateTime, nullable=True)
    
    # --- RELACIONES ---
    search = relationship("Search", back_populates="products")
    seller = relationship("Seller", back_populates="products")
    notifications = relationship("Notification", back_populates="product", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Product(id={self.id}, vinted_id='{self.vinted_id}', title='{self.title[:30]}...')>"


class Seller(Base):
    """
    Modelo para almacenar información de vendedores de Vinted.
    
    Cada registro representa un vendedor único.
    Se actualiza cuando se scrapean sus productos.
    """
    __tablename__ = "sellers"
    
    # Identificación
    id = Column(Integer, primary_key=True, index=True)
    vinted_id = Column(String(100), unique=True, nullable=False, index=True)
    login = Column(String(200), nullable=False)
    
    # --- DATOS BÁSICOS ---
    profile_url = Column(String(1000), nullable=True)
    country_code = Column(String(10), nullable=True)
    country_title = Column(String(100), nullable=True)
    city = Column(String(200), nullable=True)
    
    # --- ESTADÍSTICAS DE ACTIVIDAD ---
    item_count = Column(Integer, default=0)
    total_items_count = Column(Integer, default=0)
    followers_count = Column(Integer, default=0)
    following_count = Column(Integer, default=0)
    
    # --- FEEDBACK/REPUTACIÓN ---
    positive_feedback_count = Column(Integer, default=0)
    negative_feedback_count = Column(Integer, default=0)
    neutral_feedback_count = Column(Integer, default=0)
    feedback_count = Column(Integer, default=0)
    feedback_reputation = Column(Float, default=0.0)
    
    # --- VERIFICACIONES ---
    email_verified = Column(Boolean, default=False)
    facebook_verified = Column(Boolean, default=False)
    google_verified = Column(Boolean, default=False)
    is_business = Column(Boolean, default=False)
    
    # --- ESTADO DE CUENTA ---
    is_banned = Column(Boolean, default=False)
    ban_date = Column(DateTime, nullable=True)
    last_logged_on = Column(DateTime, nullable=True)
    
    # --- OTROS DATOS ---
    avg_response_time = Column(Integer, nullable=True)
    photo_url = Column(String(1000), nullable=True)
    about = Column(Text, nullable=True)
    
    # --- TIMESTAMPS ---
    first_seen_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # --- RELACIONES ---
    products = relationship("Product", back_populates="seller")
    
    def __repr__(self):
        return f"<Seller(id={self.id}, vinted_id='{self.vinted_id}', login='{self.login}')>"


class Notification(Base):
    """
    Modelo para registrar notificaciones enviadas.
    
    Cada registro es un envío de notificación (Telegram, Discord, etc.)
    """
    __tablename__ = "notifications"
    
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    channel = Column(String(50), nullable=False)
    status = Column(String(20), default="pending", nullable=False)
    error_message = Column(Text, nullable=True)
    sent_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # --- RELACIONES ---
    product = relationship("Product", back_populates="notifications")
    
    def __repr__(self):
        return f"<Notification(id={self.id}, channel='{self.channel}', status='{self.status}')>"


class ScrapingLog(Base):
    """
    Modelo para registrar ejecuciones del scraper (logs).
    
    Útil para debugging y estadísticas.
    
    ⭐ MEJORADO: Ahora incluye métricas adicionales (filtros, notificaciones, vendedores)
    """
    __tablename__ = "scraping_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    search_id = Column(Integer, ForeignKey("searches.id"), nullable=False, index=True)
    
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    finished_at = Column(DateTime, nullable=True)
    
    status = Column(String(20), default="running")
    # Estados: "running", "success", "failed"
    
    products_found = Column(Integer, default=0)
    # Cuántos productos nuevos se encontraron
    
    error_message = Column(Text, nullable=True)
    
    # ⭐ NUEVOS CAMPOS PARA MÉTRICAS DETALLADAS
    products_filtered = Column(Integer, default=0)  # Rechazados por filtros
    products_notified = Column(Integer, default=0)  # Notificaciones enviadas
    sellers_new = Column(Integer, default=0)        # Vendedores nuevos scrapeados
    sellers_updated = Column(Integer, default=0)    # Vendedores actualizados
    duration_ms = Column(Integer, nullable=True)    # Duración total en milisegundos
    
    # --- RELACIONES ---
    search = relationship("Search", back_populates="scraping_logs")
    
    def __repr__(self):
        return f"<ScrapingLog(id={self.id}, search_id={self.search_id}, status='{self.status}')>"


class SchedulerLog(Base):
    """
    ⭐ NUEVO MODELO: Registra ejecuciones del scheduler.
    
    Cada registro representa una ejecución de un job del scheduler:
    - Jobs de búsqueda (scraping automático)
    - Jobs de mantenimiento (limpieza diaria, marcar notificados)
    
    Útil para:
    - Monitorear el scheduler en tiempo real
    - Detectar errores recurrentes
    - Generar estadísticas y métricas
    - Dashboard del scheduler
    """
    __tablename__ = "scheduler_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Referencia a la búsqueda (null si es job de mantenimiento)
    search_id = Column(Integer, ForeignKey("searches.id"), nullable=True, index=True)
    
    # Información del job
    job_id = Column(String(100), nullable=False, index=True)
    # Ejemplo: "search_1", "data_cleanup_daily", "data_mark_notified_periodic"
    
    job_name = Column(String(200), nullable=True)
    # Nombre legible del job
    
    job_type = Column(String(50), default="search")
    # Tipos: "search", "cleanup", "maintenance"
    
    # Timestamps
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    finished_at = Column(DateTime, nullable=True)
    
    # Estado de la ejecución
    status = Column(String(20), default="running", index=True)
    # Estados: "running", "success", "error", "timeout"
    
    # Métricas (solo para jobs de tipo "search")
    products_found = Column(Integer, default=0)      # Total encontrados en Vinted
    products_new = Column(Integer, default=0)        # Nuevos guardados en BD
    products_filtered = Column(Integer, default=0)   # Rechazados por filtros
    products_notified = Column(Integer, default=0)   # Notificaciones enviadas
    
    # Tracking de errores
    error_message = Column(Text, nullable=True)
    error_count = Column(Integer, default=0)
    # Contador de errores consecutivos para esta búsqueda
    # Se reinicia a 0 cuando tiene éxito
    
    # Duración de la ejecución
    duration_ms = Column(Integer, nullable=True)
    
    # Relación opcional con ScrapingLog
    scraping_log_id = Column(Integer, ForeignKey("scraping_logs.id"), nullable=True)
    
    # --- RELACIONES ---
    search = relationship("Search", back_populates="scheduler_logs")
    
    def __repr__(self):
        return f"<SchedulerLog(id={self.id}, job_id='{self.job_id}', status='{self.status}')>"


class Settings(Base):
    """
    Modelo para almacenar la configuración global de la aplicación.
    
    Solo habrá un registro en esta tabla (singleton).
    Siempre tendrá id=1.
    """
    __tablename__ = "settings"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # ========================================================================
    # NOTIFICACIONES E INTEGRACIONES
    # ========================================================================
    
    push_notifications_enabled = Column(Boolean, default=False, nullable=False)
    webhook_url = Column(String(1000), nullable=True)
    telegram_bot_token = Column(String(500), nullable=True)
    telegram_chat_id = Column(String(100), nullable=True)
    discord_webhook_url = Column(String(1000), nullable=True)
    discord_bot_token = Column(String(500), nullable=True)
    
    # ========================================================================
    # SCRAPING
    # ========================================================================
    
    user_agent = Column(
        String(500), 
        default="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        nullable=False
    )
    
    user_agent_list = Column(Text, nullable=True)
    user_agent_rotation = Column(Boolean, default=True, nullable=False)
    default_headers = Column(JSON, nullable=True)
    max_products_per_search = Column(Integer, default=100, nullable=False)
    proxies_enabled = Column(Boolean, default=False, nullable=False)
    proxy_list = Column(Text, nullable=True)
    proxy_rotation = Column(Boolean, default=True, nullable=False)
    
    # ========================================================================
    # FILTROS GLOBALES
    # ========================================================================
    
    global_banned_words = Column(Text, nullable=True)
    global_min_price = Column(Float, default=0.0, nullable=False)
    global_banned_sellers = Column(Text, nullable=True)
    
    # ========================================================================
    # GESTIÓN DE DATOS
    # ========================================================================
    
    auto_delete_products_days = Column(Integer, default=30, nullable=False)
    auto_mark_notified_hours = Column(Integer, default=24, nullable=False)
    max_products_in_db = Column(Integer, default=10000, nullable=False)
    
    # ⭐ NUEVO: Notificaciones de errores del scheduler
    scheduler_error_notifications_enabled = Column(Boolean, default=True, nullable=False)
    scheduler_error_threshold = Column(Integer, default=3, nullable=False)
    # Enviar notificación si una búsqueda falla N veces consecutivas
    
    # ========================================================================
    # PREFERENCIAS DE INTERFAZ
    # ========================================================================
    
    theme = Column(String(20), default="light", nullable=False)
    language = Column(String(10), default="es", nullable=False)
    currency = Column(String(10), default="EUR", nullable=False)
    vinted_domain = Column(String(100), default="vinted.es", nullable=False)
    
    # ========================================================================
    # TIMESTAMPS
    # ========================================================================
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    def __repr__(self):
        return f"<Settings(id={self.id})>"