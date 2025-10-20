"""
Schemas de Pydantic para validación de datos.

Los schemas definen:
- Qué datos aceptamos del usuario (request)
- Qué datos devolvemos (response)
- Validaciones automáticas (tipos, rangos, etc.)

⭐ VERSIÓN MEJORADA CON:
- Schemas para SchedulerLog
- Schemas para estadísticas detalladas
- Schemas para dashboard del scheduler
"""

from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional, List, Dict, Any
from datetime import datetime


# ============================================================================
# SCHEMAS PARA BÚSQUEDAS (SEARCH)
# ============================================================================

class SearchBase(BaseModel):
    """Campos base compartidos entre crear y actualizar búsqueda."""
    name: str = Field(..., min_length=1, max_length=200, description="Nombre descriptivo de la búsqueda")
    query: Optional[str] = Field(None, max_length=500, description="Texto de búsqueda en Vinted")
    
    # Filtros de Vinted (todos opcionales)
    category_ids: Optional[List[int]] = Field(None, description="IDs de categorías de Vinted")
    brand_ids: Optional[List[int]] = Field(None, description="IDs de marcas")
    size_ids: Optional[List[int]] = Field(None, description="IDs de tallas")
    color_ids: Optional[List[int]] = Field(None, description="IDs de colores")
    material_ids: Optional[List[int]] = Field(None, description="IDs de materiales")
    platform_ids: Optional[List[int]] = Field(None, description="IDs de plataformas de videojuegos")
    status_ids: Optional[List[int]] = Field(None, description="IDs de estados")
    
    # Rango de precios
    price_from: Optional[float] = Field(None, ge=0, description="Precio mínimo en euros")
    price_to: Optional[float] = Field(None, ge=0, description="Precio máximo en euros")
    
    # Orden de resultados
    order: str = Field("newest_first", description="Orden de los resultados")
    
    # Filtros personalizados
    allowed_countries: Optional[List[str]] = Field(None, description="Códigos de países permitidos")
    banned_words: Optional[List[str]] = Field(None, description="Palabras prohibidas")
    banned_seller_ids: Optional[List[str]] = Field(None, description="IDs de vendedores bloqueados")
    
    # Configuración
    interval_minutes: int = Field(5, ge=1, le=1440, description="Intervalo de ejecución en minutos")
    is_active: bool = Field(True, description="Si la búsqueda está activa")
    
    vinted_query_string: Optional[str] = Field(None, description="Query string original de Vinted")
    
    @field_validator('price_to')
    def validate_price_range(cls, v, info):
        if v is not None and info.data.get('price_from') is not None:
            if v < info.data['price_from']:
                raise ValueError('El precio máximo debe ser mayor que el mínimo')
        return v
    
    @field_validator('allowed_countries')
    def validate_country_codes(cls, v):
        if v:
            for country in v:
                if not (len(country) == 2 and country.isupper()):
                    raise ValueError(f'Código de país inválido: {country}')
        return v
    
    @field_validator('order')
    def validate_order(cls, v):
        valid_orders = ['newest_first', 'price_low_to_high', 'price_high_to_low', 'relevance']
        if v not in valid_orders:
            raise ValueError(f'Orden inválido: {v}')
        return v


class SearchCreate(SearchBase):
    """Schema para CREAR una nueva búsqueda."""
    vinted_url: Optional[str] = Field(None, description="URL de Vinted para extraer parámetros")
    
    @model_validator(mode='after')
    def parse_vinted_url_if_provided(self):
        if self.vinted_url:
            from app.utils.url_parser import parse_vinted_url
            try:
                parsed_params = parse_vinted_url(self.vinted_url)
                if 'video_game_platform_ids' in parsed_params:
                    parsed_params['platform_ids'] = parsed_params.pop('video_game_platform_ids')
                for key, value in parsed_params.items():
                    setattr(self, key, value)
            except ValueError as e:
                raise ValueError(f"Error parseando URL de Vinted: {e}")
        
        if not self.query and not (self.price_from or self.price_to):
            raise ValueError("Debe proporcionar al menos un término de búsqueda o rango de precio")
        return self


class SearchUpdate(BaseModel):
    """Schema para ACTUALIZAR una búsqueda existente."""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    query: Optional[str] = Field(None, max_length=500)
    category_ids: Optional[List[int]] = None
    brand_ids: Optional[List[int]] = None
    size_ids: Optional[List[int]] = None
    color_ids: Optional[List[int]] = None
    material_ids: Optional[List[int]] = None
    status_ids: Optional[List[int]] = None
    price_from: Optional[float] = Field(None, ge=0)
    price_to: Optional[float] = Field(None, ge=0)
    order: Optional[str] = None
    allowed_countries: Optional[List[str]] = None
    banned_words: Optional[List[str]] = None
    banned_seller_ids: Optional[List[str]] = None
    interval_minutes: Optional[int] = Field(None, ge=1, le=1440)
    is_active: Optional[bool] = None
    vinted_query_string: Optional[str] = None
    
    @field_validator('price_from', 'price_to', 'interval_minutes', mode='before')
    def empty_string_to_none(cls, v):
        if v == "" or v is None:
            return None
        return v
    
    @field_validator('query', mode='before')
    def empty_query_to_none(cls, v):
        if v == "":
            return None
        return v
    
    @field_validator('order')
    def validate_order(cls, v):
        if v is not None:
            valid_orders = ['newest_first', 'price_low_to_high', 'price_high_to_low', 'relevance']
            if v not in valid_orders:
                raise ValueError(f'Orden inválido: {v}')
        return v


class SearchResponse(SearchBase):
    """Schema para DEVOLVER una búsqueda (response)."""
    id: int
    created_at: datetime
    updated_at: Optional[datetime]
    last_run_at: Optional[datetime]
    last_success_at: Optional[datetime]
    products_count: int = 0
    
    class Config:
        from_attributes = True


# ============================================================================
# SCHEMAS PARA PRODUCTOS (PRODUCT)
# ============================================================================

class ProductBase(BaseModel):
    """Campos base de un producto."""
    vinted_id: str
    title: str = Field(..., max_length=500)
    description: Optional[str] = None
    price: float = Field(..., ge=0)
    currency: str = Field("EUR", max_length=10)
    brand: Optional[str] = Field(None, max_length=200)
    size: Optional[str] = Field(None, max_length=50)
    condition: Optional[str] = Field(None, max_length=100)
    url: str
    image_url: Optional[str] = None
    seller_vinted_id: Optional[str] = None
    seller_name: Optional[str] = None
    seller_country: Optional[str] = None


class ProductCreate(ProductBase):
    """Schema para crear un producto."""
    pass


class ProductResponse(ProductBase):
    """Schema para devolver un producto."""
    id: int
    search_id: int
    seller_id: Optional[int]
    is_available: bool
    is_notified: bool
    is_favorite: bool
    found_at: datetime
    notified_at: Optional[datetime]
    
    class Config:
        from_attributes = True


# ============================================================================
# SCHEMAS PARA VENDEDORES (SELLER)
# ============================================================================

class SellerBase(BaseModel):
    """Campos base de un vendedor."""
    vinted_id: str
    login: str
    profile_url: Optional[str] = None
    country_code: Optional[str] = None
    country_title: Optional[str] = None
    city: Optional[str] = None
    item_count: int = 0
    total_items_count: int = 0
    followers_count: int = 0
    following_count: int = 0
    positive_feedback_count: int = 0
    negative_feedback_count: int = 0
    neutral_feedback_count: int = 0
    feedback_count: int = 0
    feedback_reputation: float = 0.0
    email_verified: bool = False
    facebook_verified: bool = False
    google_verified: bool = False
    is_business: bool = False
    is_banned: bool = False
    last_logged_on: Optional[datetime] = None
    avg_response_time: Optional[int] = None
    photo_url: Optional[str] = None
    about: Optional[str] = None


class SellerCreate(SellerBase):
    """Schema para crear un vendedor."""
    pass


class SellerUpdate(BaseModel):
    """Schema para actualizar un vendedor."""
    login: Optional[str] = None
    profile_url: Optional[str] = None
    country_code: Optional[str] = None
    country_title: Optional[str] = None
    city: Optional[str] = None
    item_count: Optional[int] = None
    total_items_count: Optional[int] = None
    followers_count: Optional[int] = None
    following_count: Optional[int] = None
    positive_feedback_count: Optional[int] = None
    negative_feedback_count: Optional[int] = None
    neutral_feedback_count: Optional[int] = None
    feedback_count: Optional[int] = None
    feedback_reputation: Optional[float] = None
    email_verified: Optional[bool] = None
    facebook_verified: Optional[bool] = None
    google_verified: Optional[bool] = None
    is_business: Optional[bool] = None
    is_banned: Optional[bool] = None
    ban_date: Optional[datetime] = None
    last_logged_on: Optional[datetime] = None
    avg_response_time: Optional[int] = None
    photo_url: Optional[str] = None
    about: Optional[str] = None


class SellerResponse(SellerBase):
    """Schema para devolver un vendedor."""
    id: int
    ban_date: Optional[datetime]
    first_seen_at: datetime
    last_updated_at: datetime
    
    class Config:
        from_attributes = True


# ============================================================================
# ⭐ NUEVOS SCHEMAS PARA SCHEDULER
# ============================================================================

class SchedulerLogBase(BaseModel):
    """Campos base de un log del scheduler."""
    job_id: str
    job_name: Optional[str] = None
    job_type: str = "search"
    search_id: Optional[int] = None


class SchedulerLogResponse(SchedulerLogBase):
    """Schema para devolver un log del scheduler."""
    id: int
    started_at: datetime
    finished_at: Optional[datetime]
    status: str
    products_found: int = 0
    products_new: int = 0
    products_filtered: int = 0
    products_notified: int = 0
    error_message: Optional[str]
    error_count: int = 0
    duration_ms: Optional[int]
    scraping_log_id: Optional[int]
    
    class Config:
        from_attributes = True


class SchedulerStatusResponse(BaseModel):
    """Estado actual del scheduler."""
    running: bool
    jobs_count: int
    active_searches: int
    next_executions: List[Dict[str, Any]]


class SchedulerJobInfo(BaseModel):
    """Información de un job del scheduler."""
    id: str
    name: str
    search_id: Optional[int]
    type: str
    next_run_time: Optional[str]
    trigger: str
    is_running: bool = False


# ============================================================================
# SCHEMAS PARA ESTADÍSTICAS
# ============================================================================

class StatsResponse(BaseModel):
    """Estadísticas generales de la aplicación."""
    total_searches: int
    active_searches: int
    total_products: int
    new_products: int
    products_today: int


class DetailedStatsResponse(BaseModel):
    """⭐ NUEVO: Estadísticas detalladas."""
    searches: Dict[str, int]
    products: Dict[str, int]
    top_searches: List[Dict[str, Any]]
    avg_price: float
    products_by_day: Optional[List[Dict[str, Any]]] = None
    success_rate: Optional[float] = None


class SchedulerStatsResponse(BaseModel):
    """⭐ NUEVO: Estadísticas del scheduler."""
    total_executions: int
    successful_executions: int
    failed_executions: int
    success_rate: float
    avg_duration_ms: float
    total_products_found: int
    total_products_new: int
    last_24h_executions: int
    errors_by_search: List[Dict[str, Any]]


# ============================================================================
# SCHEMAS PARA NOTIFICACIONES
# ============================================================================

class NotificationBase(BaseModel):
    """Campos base de una notificación."""
    product_id: int
    channel: str
    status: str = "pending"
    error_message: Optional[str] = None


class NotificationCreate(NotificationBase):
    """Schema para crear una notificación."""
    pass


class NotificationUpdate(BaseModel):
    """Schema para actualizar una notificación."""
    status: Optional[str] = Field(None, pattern="^(pending|sent|failed)$")
    error_message: Optional[str] = None


class NotificationResponse(NotificationBase):
    """Schema para devolver una notificación."""
    id: int
    sent_at: datetime
    
    class Config:
        from_attributes = True


# ============================================================================
# SCHEMAS PARA CONFIGURACIÓN (SETTINGS)
# ============================================================================

class SettingsBase(BaseModel):
    """Campos base de configuración."""
    # Notificaciones
    push_notifications_enabled: bool = False
    webhook_url: Optional[str] = None
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    discord_webhook_url: Optional[str] = None
    discord_bot_token: Optional[str] = None
    
    # Scraping
    user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    default_headers: Optional[Dict[str, str]] = None
    max_products_per_search: int = Field(100, ge=1, le=1000)
    proxies_enabled: bool = False
    proxy_list: Optional[str] = None
    proxy_rotation: bool = True
    
    # Filtros globales
    global_banned_words: Optional[str] = None
    global_min_price: float = Field(0.0, ge=0.0)
    global_banned_sellers: Optional[str] = None
    
    # Gestión de datos
    auto_delete_products_days: int = Field(30, ge=0)
    auto_mark_notified_hours: int = Field(24, ge=0)
    max_products_in_db: int = Field(10000, ge=0)
    
    # ⭐ NUEVO: Scheduler
    scheduler_error_notifications_enabled: bool = True
    scheduler_error_threshold: int = Field(3, ge=1, le=10)
    
    # Preferencias
    theme: str = Field("light", pattern="^(light|dark)$")
    language: str = Field("es", pattern="^(es|en|fr|it|pt)$")
    currency: str = Field("EUR", pattern="^(EUR|USD|GBP)$")
    vinted_domain: str = "vinted.es"


class SettingsUpdate(BaseModel):
    """Schema para actualizar configuración."""
    push_notifications_enabled: Optional[bool] = None
    webhook_url: Optional[str] = None
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    discord_webhook_url: Optional[str] = None
    discord_bot_token: Optional[str] = None
    user_agent: Optional[str] = None
    default_headers: Optional[Dict[str, str]] = None
    max_products_per_search: Optional[int] = Field(None, ge=1, le=1000)
    proxies_enabled: Optional[bool] = None
    proxy_list: Optional[str] = None
    proxy_rotation: Optional[bool] = None
    global_banned_words: Optional[str] = None
    global_min_price: Optional[float] = Field(None, ge=0.0)
    global_banned_sellers: Optional[str] = None
    auto_delete_products_days: Optional[int] = Field(None, ge=0)
    auto_mark_notified_hours: Optional[int] = Field(None, ge=0)
    max_products_in_db: Optional[int] = Field(None, ge=0)
    scheduler_error_notifications_enabled: Optional[bool] = None
    scheduler_error_threshold: Optional[int] = Field(None, ge=1, le=10)
    theme: Optional[str] = Field(None, pattern="^(light|dark)$")
    language: Optional[str] = Field(None, pattern="^(es|en|fr|it|pt)$")
    currency: Optional[str] = Field(None, pattern="^(EUR|USD|GBP)$")
    vinted_domain: Optional[str] = None


class SettingsResponse(SettingsBase):
    """Schema para devolver configuración."""
    id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


# ============================================================================
# SCHEMAS PARA RESPUESTAS GENÉRICAS
# ============================================================================

class MessageResponse(BaseModel):
    """Respuesta genérica con mensaje."""
    message: str
    success: bool = True


class ErrorResponse(BaseModel):
    """Respuesta de error."""
    detail: str
    error: bool = True