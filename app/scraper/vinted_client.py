"""
Cliente HTTP para Vinted con configuración dinámica desde Settings.

Mejoras:
- User-Agents rotativos desde configuración
- Headers personalizados
- Proxies rotativos
- Integración con ScraperConfig
"""

import json
import requests
import sys
import os
from requests.exceptions import HTTPError
from datetime import datetime
from typing import Optional

# Añadir el directorio raíz al path para imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.schemas import ProductCreate, SellerCreate
from app.utils.scraper_config import ScraperConfig


class VintedRequester:
    """
    Cliente HTTP para Vinted con configuración dinámica.
    Lee configuración desde Settings (User-Agents, proxies, headers).
    """
    
    def __init__(self, config: Optional[ScraperConfig] = None, debug=False):
        """
        Inicializa el requester.
        
        Args:
            config: Configuración del scraper (opcional, se crea una si no se pasa)
            debug: Activar modo debug
        """
        self.config = config or ScraperConfig()
        self.debug = debug
        
        # Obtener dominio desde configuración
        vinted_domain = self.config.get_vinted_domain()
        self.VINTED_BASE_URL = f"https://www.{vinted_domain}/"
        
        self.MAX_RETRIES = 3
        self.session = requests.Session()
        
        # Configurar headers iniciales
        self._update_headers()
        
        if self.debug:
            stats = self.config.get_stats()
            print(f"[CONFIG] User-Agents: {stats['user_agents_count']}")
            print(f"[CONFIG] Proxies: {stats['proxies_count']} ({'enabled' if stats['proxies_enabled'] else 'disabled'})")
            print(f"[CONFIG] Max productos: {stats['max_products']}")
    
    def _update_headers(self):
        """Actualiza headers con configuración actual."""
        headers = self.config.get_headers()
        
        # Añadir Referer basado en el dominio
        headers['Referer'] = self.VINTED_BASE_URL
        
        self.session.headers.update(headers)
        
        if self.debug:
            print(f"[HEADERS] User-Agent: {headers.get('User-Agent', 'N/A')[:60]}...")
    
    def _configure_proxy(self):
        """Configura proxy según configuración."""
        proxy = self.config.get_proxy()
        
        if proxy:
            self.session.proxies.update(proxy)
            if self.debug:
                print(f"[PROXY] Usando: {proxy.get('http', 'N/A')}")
        else:
            self.session.proxies.clear()
    
    def _refresh_cookies(self):
        """Obtiene cookies frescas haciendo un request HEAD a la base URL."""
        self.session.cookies.clear_session_cookies()
        try:
            self.session.head(self.VINTED_BASE_URL, timeout=10)
            if self.debug:
                print("[COOKIES] Refreshed!")
        except Exception as e:
            if self.debug:
                print(f"[COOKIES] Error refreshing: {e}")
    
    def get(self, url, params=None):
        """
        GET request con retry logic y rotación de User-Agent.
        
        Args:
            url: URL a solicitar
            params: Parámetros query string
        
        Returns:
            Response object
        """
        self._configure_proxy()
        tried = 0
        
        while tried < self.MAX_RETRIES:
            tried += 1
            
            try:
                if self.debug:
                    # Mostrar la URL completa que se va a enviar
                    from urllib.parse import urlencode
                    full_url = url
                    if params:
                        # Soporta listas (arrays) correctamente
                        def _encode(params):
                            items = []
                            for k, v in params.items():
                                if isinstance(v, list):
                                    for item in v:
                                        items.append((k, item))
                                else:
                                    items.append((k, v))
                            return urlencode(items, doseq=True)
                        query = _encode(params)
                        full_url = f"{url}?{query}"
                    print(f"[DEBUG] URL solicitada: {full_url}")
                    print(f"[DEBUG] Intento {tried}/{self.MAX_RETRIES}")
                
                response = self.session.get(url, params=params, timeout=10)
                
                if response.status_code in (401, 403, 404) and tried < self.MAX_RETRIES:
                    if self.debug:
                        print(f"[ERROR] {response.status_code}, retrying...")
                    
                    # Rotar User-Agent en cada reintento
                    self._update_headers()
                    self._refresh_cookies()
                    
                elif response.status_code == 200:
                    return response
                    
                elif tried == self.MAX_RETRIES:
                    return response  # Devuelve el último response
                    
            except Exception as e:
                if self.debug:
                    print(f"[ERROR] Request error: {e}")
                
                if tried < self.MAX_RETRIES:
                    # Rotar User-Agent y proxy
                    self._update_headers()
                    self._configure_proxy()
                elif tried == self.MAX_RETRIES:
                    raise HTTPError(f"Failed after {self.MAX_RETRIES} attempts: {e}")
        
        raise HTTPError(f"Failed to get valid response after {self.MAX_RETRIES} attempts")
    
    def scrape_catalog(self, query_string=None, search_text="", price_from=None, price_to=None, 
                      order="newest_first", page=1, per_page=None, **extra_filters):
        """
        Scrapea el catálogo de Vinted con soporte para todos los filtros.
        
        Args:
            query_string: Query string original de Vinted (opcional)
            search_text: Texto de búsqueda
            price_from: Precio mínimo
            price_to: Precio máximo
            order: Orden de resultados
            page: Página
            per_page: Productos por página (usa límite de config si no se especifica)
            **extra_filters: Filtros adicionales
        
        Returns:
            list: Lista de ProductCreate objects
        """
        url = f"{self.VINTED_BASE_URL}api/v2/catalog/items"
        
        # Usar límite de configuración si no se especifica per_page
        if per_page is None:
            per_page = min(self.config.get_max_products(), 96)  # Vinted max = 96
        
        if query_string:
            # Adaptar la query string al formato esperado por la API
            from urllib.parse import parse_qsl
            queries = parse_qsl(query_string)
            params = {}
            
            # Mapeo de arrays con corchetes a nombres esperados por la API
            array_map = {
                "catalog[]": "catalog_ids",
                "video_game_platform_ids[]": "video_game_platform_ids",
                "color_ids[]": "color_ids",
                "brand_ids[]": "brand_ids",
                "size_ids[]": "size_ids",
                "material_ids[]": "material_ids",
                "status_ids[]": "status_ids",
                "country_ids[]": "country_ids",
                "city_ids[]": "city_ids",
                "disposal[]": "is_for_swap",
            }
            
            # Agrupar valores (arrays como string separados por comas)
            for k_api, k_param in array_map.items():
                values = [v for (k, v) in queries if k == k_api]
                if values:
                    params[k_param] = ",".join(values)
            
            # Otros parámetros simples
            for k, v in queries:
                if k not in array_map:
                    params[k] = v
            
            # page y per_page siempre presentes
            params["page"] = page
            params["per_page"] = per_page
            
            if self.debug:
                print(f"[DEBUG] Query string adaptada con {len(params)} parámetros")
            
            response = self.get(url, params=params)
        else:
            # Parámetros base
            params = {
                "page": page,
                "per_page": per_page
            }
            
            if search_text:
                params["search_text"] = search_text
            if price_from is not None:
                params["price_from"] = price_from
            if price_to is not None:
                params["price_to"] = price_to
            if order:
                params["order"] = order
            
            # Arrays como string separados por comas
            for key, value in extra_filters.items():
                if isinstance(value, list):
                    params[key] = ",".join(str(x) for x in value)
                else:
                    params[key] = value
            
            response = self.get(url, params=params)
        
        if response.status_code == 200:
            data = response.json()
            items = data.get("items", [])
            
            if self.debug:
                print(f"[SUCCESS] {len(items)} productos encontrados")
            
            products = []
            
            for item in items:
                try:
                    product = ProductCreate(
                        search_id=1,  # Placeholder, ajusta según búsqueda
                        vinted_id=str(item.get("id")),
                        title=item.get("title", ""),
                        description=item.get("description", ""),
                        price=float(item.get("price", {}).get("amount", 0)),
                        currency=item.get("price", {}).get("currency_code", "EUR"),
                        brand=item.get("brand_title", ""),
                        size=item.get("size_title", ""),
                        condition=item.get("status", ""),
                        url=item.get("url", ""),
                        image_url=item.get("photo", {}).get("url", "") if item.get("photo") else "",
                        seller_vinted_id=str(item.get("user", {}).get("id", "")) if item.get("user") else "",
                        seller_name=item.get("user", {}).get("login", "") if item.get("user") else "",
                        seller_country=item.get("user", {}).get("country_title", "") if item.get("user") else ""
                    )
                    products.append(product)
                    
                except Exception as e:
                    if self.debug:
                        print(f"[ERROR] Mapeando item: {e}")
            
            return products
        else:
            if self.debug:
                print(f"[ERROR] {response.status_code} - {response.text[:200]}")
            return []
    
    def get_seller_info(self, seller_id: str):
        """
        Obtiene información completa de un vendedor por su ID.
        
        Args:
            seller_id: ID del vendedor en Vinted
            
        Returns:
            SellerCreate object o None si falla
        """
        url = f"{self.VINTED_BASE_URL}api/v2/users/{seller_id}"
        
        response = self.get(url)
        
        if response.status_code == 200:
            data = response.json()
            user = data.get("user", {})
            
            if not user:
                if self.debug:
                    print(f"[ERROR] No se encontró info del vendedor {seller_id}")
                return None
            
            try:
                # Parsear verificaciones
                verification = user.get("verification", {})
                email_verified = verification.get("email", {}).get("valid", False)
                facebook_verified = verification.get("facebook", {}).get("valid", False)
                google_verified = verification.get("google", {}).get("valid", False)
                
                # Parsear última actividad
                last_logged_on = None
                if user.get("last_loged_on_ts"):
                    try:
                        from dateutil import parser
                        last_logged_on = parser.parse(user.get("last_loged_on_ts"))
                    except:
                        last_logged_on = None
                
                # Parsear foto
                photo_url = None
                if user.get("photo"):
                    photo_url = user.get("photo", {}).get("url", "")
                
                # Crear objeto SellerCreate
                seller = SellerCreate(
                    vinted_id=str(user.get("id")),
                    login=user.get("login", ""),
                    profile_url=user.get("profile_url", ""),
                    country_code=user.get("country_code", ""),
                    country_title=user.get("country_title", ""),
                    city=user.get("city", ""),
                    item_count=user.get("item_count", 0),
                    total_items_count=user.get("total_items_count", 0),
                    followers_count=user.get("followers_count", 0),
                    following_count=user.get("following_count", 0),
                    positive_feedback_count=user.get("positive_feedback_count", 0),
                    negative_feedback_count=user.get("negative_feedback_count", 0),
                    neutral_feedback_count=user.get("neutral_feedback_count", 0),
                    feedback_count=user.get("feedback_count", 0),
                    feedback_reputation=user.get("feedback_reputation", 0.0),
                    email_verified=email_verified,
                    facebook_verified=facebook_verified,
                    google_verified=google_verified,
                    is_business=user.get("business", False),
                    is_banned=user.get("is_account_banned", False),
                    last_logged_on=last_logged_on,
                    avg_response_time=user.get("avg_response_time"),
                    photo_url=photo_url,
                    about=user.get("about", "")
                )
                
                if self.debug:
                    print(f"[SUCCESS] Vendedor {seller.login} obtenido")
                
                return seller
                
            except Exception as e:
                if self.debug:
                    print(f"[ERROR] Mapeando vendedor: {e}")
                return None
        else:
            if self.debug:
                print(f"[ERROR] {response.status_code} obteniendo vendedor {seller_id}")
            return None
    
    def close(self):
        """Cierra la sesión."""
        self.session.close()


# ============================================================================
# INSTANCIA SINGLETON (LEGACY - para compatibilidad)
# ============================================================================

# Esta instancia se mantiene para compatibilidad con código antiguo
# pero ahora usa la configuración dinámica
requester = VintedRequester(debug=False)
