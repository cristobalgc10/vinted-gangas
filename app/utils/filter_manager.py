"""
Filter Manager - Sistema de filtros globales

Aplica filtros configurados en Settings:
- Palabras prohibidas en título/descripción
- Precio mínimo global
- Vendedores bloqueados
- Filtros personalizados de cada búsqueda
"""

from typing import List, Optional
from sqlalchemy.orm import Session

from app.models import Settings, Search
from app.schemas import ProductCreate
from app.database import SessionLocal


class FilterManager:
    """
    Gestor de filtros globales y personalizados.
    Lee configuración desde Settings y aplica filtros a productos.
    """
    
    def __init__(self, db: Optional[Session] = None):
        """
        Inicializa el gestor de filtros.
        
        Args:
            db: Sesión de BD (opcional, se crea una si no se pasa)
        """
        self.db = db or SessionLocal()
        self._own_db = db is None
        
        # Cache de configuración
        self._settings: Optional[Settings] = None
        self._global_banned_words: List[str] = []
        self._global_banned_sellers: List[str] = []
        self._global_min_price: float = 0.0
        
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
        """Carga la configuración de filtros desde Settings."""
        self._settings = self.db.query(Settings).filter(Settings.id == 1).first()
        
        if not self._settings:
            # Si no hay settings, no hay filtros
            return
        
        # Parsear palabras prohibidas globales
        self._parse_global_banned_words()
        
        # Parsear vendedores bloqueados globales
        self._parse_global_banned_sellers()
        
        # Obtener precio mínimo global
        self._global_min_price = getattr(self._settings, 'global_min_price', 0.0)
    
    def _parse_global_banned_words(self):
        """Parsea la lista de palabras prohibidas globales."""
        banned_words_str = getattr(self._settings, 'global_banned_words', None)
        
        if banned_words_str:
            # Separar por líneas y limpiar
            self._global_banned_words = [
                word.strip().lower() 
                for word in banned_words_str.split('\n') 
                if word.strip()
            ]
        else:
            self._global_banned_words = []
    
    def _parse_global_banned_sellers(self):
        """Parsea la lista de vendedores bloqueados globales."""
        banned_sellers_str = getattr(self._settings, 'global_banned_sellers', None)
        
        if banned_sellers_str:
            # Separar por líneas y limpiar
            self._global_banned_sellers = [
                seller.strip().lower() 
                for seller in banned_sellers_str.split('\n') 
                if seller.strip()
            ]
        else:
            self._global_banned_sellers = []
    
    def reload(self):
        """Recarga la configuración desde la base de datos."""
        self.db.expire_all()
        self._load_config()
    
    def filter_product(self, product: ProductCreate, search: Optional[Search] = None) -> tuple[bool, Optional[str]]:
        """
        Aplica todos los filtros a un producto.
        
        Args:
            product: Producto a filtrar
            search: Búsqueda asociada (para filtros personalizados)
        
        Returns:
            tuple: (pasa_filtros: bool, razón_rechazo: Optional[str])
                   Si pasa_filtros=False, razón_rechazo contiene el motivo
        """
        # Filtro 1: Precio mínimo global
        if self._global_min_price > 0 and product.price < self._global_min_price:
            return False, f"Precio {product.price}€ < mínimo global {self._global_min_price}€"
        
        # Filtro 2: Palabras prohibidas globales
        if self._global_banned_words:
            text_to_check = f"{product.title} {product.description or ''}".lower()
            
            for banned_word in self._global_banned_words:
                if banned_word in text_to_check:
                    return False, f"Palabra prohibida: '{banned_word}'"
        
        # Filtro 3: Vendedores bloqueados globales
        if self._global_banned_sellers and product.seller_name:
            seller_name_lower = product.seller_name.lower()
            seller_id_lower = product.seller_vinted_id.lower() if product.seller_vinted_id else ""
            
            for banned_seller in self._global_banned_sellers:
                if banned_seller in seller_name_lower or banned_seller == seller_id_lower:
                    return False, f"Vendedor bloqueado: '{product.seller_name}'"
        
        # Filtros personalizados de la búsqueda (si se pasa)
        if search:
            # Filtro 4: Palabras prohibidas de la búsqueda
            search_banned_words = getattr(search, 'banned_words', None)
            if search_banned_words:
                banned_words_list = [
                    word.strip().lower() 
                    for word in (search_banned_words if isinstance(search_banned_words, list) else search_banned_words.split('\n'))
                    if word.strip()
                ] if isinstance(search_banned_words, str) else search_banned_words
                
                text_to_check = f"{product.title} {product.description or ''}".lower()
                
                for banned_word in banned_words_list:
                    if banned_word in text_to_check:
                        return False, f"Palabra prohibida (búsqueda): '{banned_word}'"
            
            # Filtro 5: Vendedores bloqueados de la búsqueda
            search_banned_sellers = getattr(search, 'banned_seller_ids', None)
            if search_banned_sellers and product.seller_vinted_id:
                banned_sellers_list = search_banned_sellers if isinstance(search_banned_sellers, list) else []
                
                if product.seller_vinted_id in banned_sellers_list:
                    return False, f"Vendedor bloqueado (búsqueda): '{product.seller_name}'"
            
            # Filtro 6: Países permitidos
            allowed_countries = getattr(search, 'allowed_countries', None)
            if allowed_countries and product.seller_country:
                countries_list = allowed_countries if isinstance(allowed_countries, list) else []
                
                if countries_list and product.seller_country not in countries_list:
                    return False, f"País no permitido: '{product.seller_country}'"
        
        # Producto pasa todos los filtros
        return True, None
    
    def filter_products(self, products: List[ProductCreate], search: Optional[Search] = None) -> tuple[List[ProductCreate], dict]:
        """
        Filtra una lista de productos.
        
        Args:
            products: Lista de productos a filtrar
            search: Búsqueda asociada (opcional)
        
        Returns:
            tuple: (productos_filtrados: List[ProductCreate], estadísticas: dict)
        """
        filtered = []
        rejected = []
        rejection_reasons = {}
        
        for product in products:
            passes, reason = self.filter_product(product, search)
            
            if passes:
                filtered.append(product)
            else:
                rejected.append(product)
                # Contar razones de rechazo
                rejection_reasons[reason] = rejection_reasons.get(reason, 0) + 1
        
        stats = {
            'total': len(products),
            'accepted': len(filtered),
            'rejected': len(rejected),
            'rejection_reasons': rejection_reasons
        }
        
        return filtered, stats
    
    def get_stats(self) -> dict:
        """
        Obtiene estadísticas de filtros configurados.
        
        Returns:
            dict: Estadísticas de filtros activos
        """
        return {
            'global_banned_words_count': len(self._global_banned_words),
            'global_banned_sellers_count': len(self._global_banned_sellers),
            'global_min_price': self._global_min_price,
            'filters_active': (
                len(self._global_banned_words) > 0 or 
                len(self._global_banned_sellers) > 0 or 
                self._global_min_price > 0
            )
        }
    
    @property
    def settings(self) -> Settings:
        """Acceso directo a Settings."""
        return self._settings


# ============================================================================
# FUNCIONES HELPER
# ============================================================================

def get_filter_manager(db: Optional[Session] = None) -> FilterManager:
    """
    Obtiene una instancia de FilterManager.
    
    Args:
        db: Sesión de BD (opcional)
    
    Returns:
        FilterManager instance
    """
    return FilterManager(db=db)


def test_filters():
    """Función de testing para verificar filtros."""
    print("=" * 60)
    print("🚫 TEST DE FILTROS GLOBALES")
    print("=" * 60)
    print()
    
    with FilterManager() as fm:
        stats = fm.get_stats()
        
        print("📊 ESTADÍSTICAS:")
        print(f"   • Palabras prohibidas: {stats['global_banned_words_count']}")
        print(f"   • Vendedores bloqueados: {stats['global_banned_sellers_count']}")
        print(f"   • Precio mínimo: {stats['global_min_price']}€")
        print(f"   • Filtros activos: {'✅ Sí' if stats['filters_active'] else '❌ No'}")
        print()
        
        if stats['global_banned_words_count'] > 0:
            print("🚫 PALABRAS PROHIBIDAS:")
            for word in fm._global_banned_words[:10]:  # Mostrar max 10
                print(f"   • {word}")
            if len(fm._global_banned_words) > 10:
                print(f"   ... y {len(fm._global_banned_words) - 10} más")
            print()
        
        if stats['global_banned_sellers_count'] > 0:
            print("👤 VENDEDORES BLOQUEADOS:")
            for seller in fm._global_banned_sellers[:10]:
                print(f"   • {seller}")
            if len(fm._global_banned_sellers) > 10:
                print(f"   ... y {len(fm._global_banned_sellers) - 10} más")
            print()
        
        # Test con producto de ejemplo
        from app.schemas import ProductCreate
        
        print("🧪 TEST CON PRODUCTO DE EJEMPLO:")
        test_product = ProductCreate(
            search_id=1,
            vinted_id="12345",
            title="Nike Air Max en muy buen estado",
            description="Zapatillas Nike en perfecto estado",
            price=25.0,
            currency="EUR",
            brand="Nike",
            size="42",
            condition="Muy bueno",
            url="https://vinted.es/items/12345",
            image_url="https://example.com/image.jpg",
            seller_vinted_id="999",
            seller_name="vendedor_test",
            seller_country="ES"
        )
        
        passes, reason = fm.filter_product(test_product)
        
        if passes:
            print("   ✅ Producto PASA los filtros")
        else:
            print(f"   ❌ Producto RECHAZADO: {reason}")
        print()
        
        # Test con producto que debería ser rechazado
        if stats['global_banned_words_count'] > 0:
            print("🧪 TEST CON PRODUCTO CON PALABRA PROHIBIDA:")
            banned_word = fm._global_banned_words[0]
            test_product2 = ProductCreate(
                search_id=1,
                vinted_id="12346",
                title=f"Producto con {banned_word}",
                description="Descripción",
                price=25.0,
                currency="EUR",
                url="https://vinted.es/items/12346",
                seller_vinted_id="999",
                seller_name="vendedor",
                seller_country="ES"
            )
            
            passes, reason = fm.filter_product(test_product2)
            
            if passes:
                print("   ⚠️  ERROR: Producto debería ser rechazado")
            else:
                print(f"   ✅ Producto RECHAZADO correctamente: {reason}")
            print()
        
        print("=" * 60)
        print("✅ TEST COMPLETADO")
        print("=" * 60)


if __name__ == "__main__":
    test_filters()
