"""
Script de testing para configuración del scraper.

Verifica que todo funcione correctamente:
- User-Agents rotativos
- Headers personalizados
- Proxies rotativos
- Límites de productos

Uso:
    python scripts/test_scraper_config.py
"""

import sys
import os

# Añadir el directorio raíz al path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.utils.scraper_config import ScraperConfig
from app.scraper.vinted_client import VintedRequester


def print_header(title: str):
    """Imprime un encabezado bonito."""
    print()
    print("=" * 70)
    print(f"  {title}")
    print("=" * 70)
    print()


def test_config():
    """Test de ScraperConfig."""
    print_header("🔧 TEST: Configuración del Scraper")
    
    with ScraperConfig() as config:
        stats = config.get_stats()
        
        print("📊 ESTADÍSTICAS GENERALES:")
        print(f"   • User-Agents: {stats['user_agents_count']}")
        print(f"   • Rotación UA: {'✅ Activada' if stats['user_agent_rotation'] else '❌ Desactivada'}")
        print(f"   • Proxies: {'✅ Habilitados' if stats['proxies_enabled'] else '❌ Deshabilitados'}")
        print(f"   • Proxies configurados: {stats['proxies_count']}")
        print(f"   • Rotación proxies: {'✅ Activada' if stats['proxy_rotation'] else '❌ Desactivada'}")
        print(f"   • Max productos: {stats['max_products']}")
        print(f"   • Dominio Vinted: {stats['vinted_domain']}")
        print(f"   • Headers custom: {'✅ Sí' if stats['has_custom_headers'] else '❌ No'}")
        print()
        
        # Test User-Agents
        if stats['user_agents_count'] > 0:
            print("🔤 USER-AGENTS CONFIGURADOS:")
            
            if stats['user_agent_rotation']:
                print(f"   Modo: Rotación secuencial ({stats['user_agents_count']} disponibles)")
                print()
                print("   Simulando 5 peticiones:")
                for i in range(min(5, stats['user_agents_count'])):
                    ua = config.get_user_agent()
                    print(f"   [{i+1}] {ua[:65]}...")
            else:
                print(f"   Modo: User-Agent fijo")
                ua = config.get_user_agent()
                print(f"   → {ua[:65]}...")
            print()
        
        # Test Headers
        print("📋 HEADERS COMPLETOS:")
        headers = config.get_headers()
        for key, value in headers.items():
            if key == 'User-Agent':
                print(f"   • {key}: {value[:60]}...")
            else:
                print(f"   • {key}: {value}")
        print()
        
        # Test Proxies
        if stats['proxies_enabled'] and stats['proxies_count'] > 0:
            print("🔗 PROXIES CONFIGURADOS:")
            
            if stats['proxy_rotation']:
                print(f"   Modo: Rotación secuencial ({stats['proxies_count']} disponibles)")
                print()
                print("   Simulando 3 peticiones:")
                for i in range(min(3, stats['proxies_count'])):
                    proxy = config.get_proxy()
                    if proxy:
                        print(f"   [{i+1}] {proxy.get('http', 'N/A')}")
            else:
                print(f"   Modo: Proxy fijo")
                proxy = config.get_proxy()
                if proxy:
                    print(f"   → {proxy.get('http', 'N/A')}")
            print()


def test_requester():
    """Test de VintedRequester con configuración."""
    print_header("🌐 TEST: VintedRequester con Configuración")
    
    with ScraperConfig() as config:
        print("Creando VintedRequester con configuración...")
        requester = VintedRequester(config=config, debug=False)
        
        stats = config.get_stats()
        
        print()
        print("✅ VintedRequester inicializado correctamente")
        print()
        print(f"   • Base URL: {requester.VINTED_BASE_URL}")
        print(f"   • Max retries: {requester.MAX_RETRIES}")
        print(f"   • User-Agents: {stats['user_agents_count']}")
        print(f"   • Proxies: {stats['proxies_count']} ({'enabled' if stats['proxies_enabled'] else 'disabled'})")
        print()
        
        # Test headers del requester
        print("📋 Headers activos en session:")
        for key, value in list(requester.session.headers.items())[:5]:
            if key == 'User-Agent':
                print(f"   • {key}: {value[:60]}...")
            else:
                print(f"   • {key}: {value}")
        print()
        
        requester.close()


def test_rotation():
    """Test de rotación de User-Agents y proxies."""
    print_header("🔄 TEST: Rotación de User-Agents y Proxies")
    
    with ScraperConfig() as config:
        stats = config.get_stats()
        
        if stats['user_agents_count'] > 1 and stats['user_agent_rotation']:
            print(f"🔤 Rotación de User-Agents ({stats['user_agents_count']} disponibles):")
            print()
            
            uas = []
            for i in range(stats['user_agents_count'] + 2):  # +2 para ver que vuelve al inicio
                ua = config.get_user_agent()
                uas.append(ua)
                print(f"   [{i+1}] {ua[:65]}...")
            
            # Verificar que rotó correctamente
            print()
            if len(set(uas[:stats['user_agents_count']])) == stats['user_agents_count']:
                print("   ✅ Rotación correcta: Se usaron todos los User-Agents")
            else:
                print("   ⚠️  Advertencia: Algunos User-Agents se repitieron")
            
            if uas[0] == uas[stats['user_agents_count']]:
                print("   ✅ Ciclo correcto: Volvió al primer User-Agent")
            else:
                print("   ⚠️  Advertencia: No volvió al primer User-Agent")
            print()
        else:
            print("⏭️  Rotación de User-Agents desactivada o solo 1 disponible")
            print()
        
        if stats['proxies_enabled'] and stats['proxies_count'] > 1 and stats['proxy_rotation']:
            print(f"🔗 Rotación de Proxies ({stats['proxies_count']} disponibles):")
            print()
            
            proxies = []
            for i in range(stats['proxies_count'] + 2):
                proxy = config.get_proxy()
                if proxy:
                    proxy_url = proxy.get('http', 'N/A')
                    proxies.append(proxy_url)
                    print(f"   [{i+1}] {proxy_url}")
            
            # Verificar rotación
            print()
            if len(set(proxies[:stats['proxies_count']])) == stats['proxies_count']:
                print("   ✅ Rotación correcta: Se usaron todos los proxies")
            else:
                print("   ⚠️  Advertencia: Algunos proxies se repitieron")
            
            if proxies[0] == proxies[stats['proxies_count']]:
                print("   ✅ Ciclo correcto: Volvió al primer proxy")
            else:
                print("   ⚠️  Advertencia: No volvió al primer proxy")
            print()
        else:
            print("⏭️  Proxies desactivados, sin configurar, o rotación desactivada")
            print()


def main():
    """Ejecuta todos los tests."""
    print()
    print("*" * 70)
    print("*" + " " * 68 + "*")
    print("*" + "  🧪 TEST DE CONFIGURACIÓN DEL SCRAPER".center(68) + "*")
    print("*" + " " * 68 + "*")
    print("*" * 70)
    
    try:
        # Test 1: Configuración
        test_config()
        
        # Test 2: VintedRequester
        test_requester()
        
        # Test 3: Rotación
        test_rotation()
        
        # Resumen final
        print_header("✅ TESTS COMPLETADOS")
        print("Todos los tests se ejecutaron correctamente.")
        print()
        print("🎯 Próximos pasos:")
        print("   1. Verifica los User-Agents en /settings")
        print("   2. Configura proxies si es necesario")
        print("   3. Ejecuta una búsqueda de prueba")
        print()
        
    except Exception as e:
        print()
        print_header("❌ ERROR EN TESTS")
        print(f"Error: {e}")
        print()
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
