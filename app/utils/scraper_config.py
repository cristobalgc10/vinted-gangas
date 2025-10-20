"""
Scraper Configuration Manager

Gestiona la configuración del scraper desde Settings:
- User-Agents rotativos
- Headers adicionales
- Proxies rotativos
- Límites de productos
"""

import random
from typing import Optional, List, Dict
from sqlalchemy.orm import Session

from app.models import Settings
from app.database import SessionLocal


class ScraperConfig:
    """
    Gestor de configuración del scraper.
    Lee Settings y proporciona valores para el VintedRequester.
    """
    
    def __init__(self, db: Optional[Session] = None):
        """
        Inicializa el gestor de configuración.
        
        Args:
            db: Sesión de BD (opcional, se crea una si no se pasa)
        """
        self.db = db or SessionLocal()
        self._own_db = db is None
        
        # Cache de configuración
        self._settings: Optional[Settings] = None
        self._user_agents: List[str] = []
        self._proxies: List[str] = []
        
        # Índices para rotación
        self._user_agent_index = 0
        self._proxy_index = 0
        
        # Cargar configuración inicial
        self._load_config()
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        if self._own_db:
            self.db.close()
    
    def _load_config(self):
        """Carga la configuración desde Settings."""
        self._settings = self.db.query(Settings).filter(Settings.id == 1).first()
        
        if not self._settings:
            # Crear configuración por defecto si no existe
            self._settings = Settings(id=1)
            self.db.add(self._settings)
            self.db.commit()
            self.db.refresh(self._settings)
        
        # Parsear User-Agents
        self._parse_user_agents()
        
        # Parsear Proxies
        self._parse_proxies()
    
    def _parse_user_agents(self):
        """Parsea la lista de User-Agents desde user_agent_list."""
        ua_list = getattr(self._settings, 'user_agent_list', None)
        
        if ua_list:
            # Separar por líneas y limpiar
            self._user_agents = [
                ua.strip() 
                for ua in ua_list.split('\n') 
                if ua.strip()
            ]
        
        # Fallback al user_agent antiguo si no hay lista
        if not self._user_agents:
            old_ua = getattr(self._settings, 'user_agent', None)
            if old_ua:
                self._user_agents = [old_ua]
        
        # Fallback a User-Agent por defecto
        if not self._user_agents:
            self._user_agents = [
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ]
    
    def _parse_proxies(self):
        """Parsea la lista de proxies desde proxy_list."""
        if not getattr(self._settings, 'proxies_enabled', False):
            self._proxies = []
            return
        
        proxy_list = getattr(self._settings, 'proxy_list', None)
        
        if proxy_list:
            # Separar por líneas y limpiar
            self._proxies = [
                proxy.strip() 
                for proxy in proxy_list.split('\n') 
                if proxy.strip()
            ]
        else:
            self._proxies = []
    
    def reload(self):
        """Recarga la configuración desde la base de datos."""
        self.db.expire_all()
        self._load_config()
    
    def get_user_agent(self) -> str:
        """
        Obtiene un User-Agent según configuración.
        
        Returns:
            str: User-Agent a usar
        """
        if not self._user_agents:
            return "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        
        # Verificar si rotación está activada
        rotation = getattr(self._settings, 'user_agent_rotation', True)
        
        if not rotation:
            # Sin rotación, usar siempre el primero
            return self._user_agents[0]
        
        # Con rotación
        if len(self._user_agents) == 1:
            return self._user_agents[0]
        
        # Rotar secuencialmente
        user_agent = self._user_agents[self._user_agent_index]
        self._user_agent_index = (self._user_agent_index + 1) % len(self._user_agents)
        
        return user_agent
    
    def get_random_user_agent(self) -> str:
        """
        Obtiene un User-Agent aleatorio (no secuencial).
        
        Returns:
            str: User-Agent aleatorio
        """
        if not self._user_agents:
            return "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        
        return random.choice(self._user_agents)
    
    def get_headers(self) -> Dict[str, str]:
        """
        Obtiene headers completos para requests.
        Incluye User-Agent + headers adicionales de configuración.
        
        Returns:
            dict: Headers completos
        """
        # Headers base
        headers = {
            "User-Agent": self.get_user_agent(),
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
            "X-Requested-With": "XMLHttpRequest"
        }
        
        # Añadir headers adicionales de configuración
        additional_headers = getattr(self._settings, 'default_headers', None)
        
        if additional_headers and isinstance(additional_headers, dict):
            # Merge headers (los adicionales tienen prioridad)
            headers.update(additional_headers)
        
        return headers
    
    def get_proxy(self) -> Optional[Dict[str, str]]:
        """
        Obtiene un proxy según configuración.
        
        Returns:
            dict: {'http': 'proxy_url', 'https': 'proxy_url'} o None si no hay proxies
        """
        if not getattr(self._settings, 'proxies_enabled', False):
            return None
        
        if not self._proxies:
            return None
        
        # Verificar si rotación está activada
        rotation = getattr(self._settings, 'proxy_rotation', True)
        
        if not rotation:
            # Sin rotación, usar siempre el primero
            proxy = self._proxies[0]
        else:
            # Con rotación secuencial
            proxy = self._proxies[self._proxy_index]
            self._proxy_index = (self._proxy_index + 1) % len(self._proxies)
        
        # Formato para requests
        return {
            'http': proxy,
            'https': proxy
        }
    
    def get_max_products(self) -> int:
        """
        Obtiene el límite máximo de productos por búsqueda.
        
        Returns:
            int: Número máximo de productos
        """
        return getattr(self._settings, 'max_products_per_search', 100)
    
    def get_vinted_domain(self) -> str:
        """
        Obtiene el dominio de Vinted configurado.
        
        Returns:
            str: Dominio (ej: 'vinted.es')
        """
        return getattr(self._settings, 'vinted_domain', 'vinted.es')
    
    def get_stats(self) -> Dict:
        """
        Obtiene estadísticas de la configuración actual.
        
        Returns:
            dict: Estadísticas de configuración
        """
        return {
            'user_agents_count': len(self._user_agents),
            'user_agent_rotation': getattr(self._settings, 'user_agent_rotation', True),
            'proxies_enabled': getattr(self._settings, 'proxies_enabled', False),
            'proxies_count': len(self._proxies),
            'proxy_rotation': getattr(self._settings, 'proxy_rotation', True),
            'max_products': self.get_max_products(),
            'vinted_domain': self.get_vinted_domain(),
            'has_custom_headers': bool(getattr(self._settings, 'default_headers', None))
        }
    
    @property
    def settings(self) -> Settings:
        """Acceso directo a Settings."""
        return self._settings


# ============================================================================
# FUNCIONES HELPER
# ============================================================================

def get_scraper_config(db: Optional[Session] = None) -> ScraperConfig:
    """
    Obtiene una instancia de ScraperConfig.
    
    Args:
        db: Sesión de BD (opcional)
    
    Returns:
        ScraperConfig instance
    """
    return ScraperConfig(db=db)


def test_config():
    """Función de testing para verificar configuración."""
    print("=" * 60)
    print("🔧 TEST DE CONFIGURACIÓN DEL SCRAPER")
    print("=" * 60)
    print()
    
    with ScraperConfig() as config:
        stats = config.get_stats()
        
        print("📊 ESTADÍSTICAS:")
        print(f"   • User-Agents configurados: {stats['user_agents_count']}")
        print(f"   • Rotación de User-Agents: {'✅' if stats['user_agent_rotation'] else '❌'}")
        print(f"   • Proxies habilitados: {'✅' if stats['proxies_enabled'] else '❌'}")
        print(f"   • Proxies configurados: {stats['proxies_count']}")
        print(f"   • Rotación de proxies: {'✅' if stats['proxy_rotation'] else '❌'}")
        print(f"   • Máximo productos: {stats['max_products']}")
        print(f"   • Dominio Vinted: {stats['vinted_domain']}")
        print(f"   • Headers personalizados: {'✅' if stats['has_custom_headers'] else '❌'}")
        print()
        
        print("🔤 USER-AGENTS:")
        for i in range(min(3, stats['user_agents_count'])):
            ua = config.get_user_agent()
            print(f"   {i+1}. {ua[:70]}...")
        print()
        
        print("🌐 HEADERS:")
        headers = config.get_headers()
        for key, value in list(headers.items())[:5]:
            print(f"   • {key}: {value[:60]}...")
        print()
        
        if stats['proxies_enabled'] and stats['proxies_count'] > 0:
            print("🔗 PROXIES:")
            for i in range(min(3, stats['proxies_count'])):
                proxy = config.get_proxy()
                if proxy:
                    print(f"   {i+1}. {proxy.get('http', 'N/A')}")
        
        print()
        print("=" * 60)
        print("✅ CONFIGURACIÓN VÁLIDA")
        print("=" * 60)


if __name__ == "__main__":
    test_config()
