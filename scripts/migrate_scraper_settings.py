"""
Migración: Actualizar campos de scraping en Settings - VERSIÓN CORREGIDA

Cambios:
1. user_agent (String) → user_agent_list (Text) - Soporte para múltiples User-Agents
2. Añadir user_agent_rotation (Boolean) - Rotar entre User-Agents
3. Convertir user_agent existente a user_agent_list (primera línea)

NOTA: Esta versión NO usa el modelo Settings para evitar conflictos.
Trabaja directamente con SQL.

Ejecutar:
    python scripts/migrate_scraper_settings.py
"""

import sys
import os

# Añadir el directorio raíz al path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.database import engine


def migrate():
    """Ejecuta la migración de campos de scraping."""
    
    print("=" * 60)
    print("🔄 MIGRACIÓN: Actualizar campos de scraping")
    print("=" * 60)
    print()
    
    try:
        # 1. Verificar si ya se ejecutó la migración
        print("📋 Verificando estado de la base de datos...")
        
        with engine.connect() as conn:
            # Verificar si existe la columna user_agent_list
            result = conn.execute(text(
                "SELECT COUNT(*) FROM pragma_table_info('settings') WHERE name='user_agent_list'"
            )).scalar()
            
            if result > 0:
                print("✅ La migración ya fue ejecutada anteriormente")
                print()
                return
        
        print("⚠️  La migración no se ha ejecutado, procediendo...")
        print()
        
        # 2. Obtener user_agent actual (sin usar modelo Settings)
        print("📥 Obteniendo configuración actual...")
        
        with engine.connect() as conn:
            # Verificar si existe configuración
            result = conn.execute(text(
                "SELECT COUNT(*) FROM settings WHERE id = 1"
            )).scalar()
            
            if result == 0:
                print("⚠️  No existe configuración, creando valores por defecto...")
                # Crear configuración por defecto
                conn.execute(text("""
                    INSERT INTO settings (
                        id, 
                        user_agent,
                        push_notifications_enabled,
                        proxies_enabled,
                        proxy_rotation,
                        global_min_price,
                        auto_delete_products_days,
                        auto_mark_notified_hours,
                        max_products_in_db,
                        max_products_per_search,
                        theme,
                        language,
                        currency,
                        vinted_domain
                    ) VALUES (
                        1,
                        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                        0,
                        0,
                        1,
                        0.0,
                        30,
                        24,
                        10000,
                        100,
                        'light',
                        'es',
                        'EUR',
                        'vinted.es'
                    )
                """))
                conn.commit()
                current_user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            else:
                # Obtener user_agent actual
                current_user_agent = conn.execute(text(
                    "SELECT user_agent FROM settings WHERE id = 1"
                )).scalar()
        
        print(f"   User-Agent actual: {current_user_agent[:60] if current_user_agent else 'N/A'}...")
        print()
        
        # 3. Ejecutar ALTER TABLE
        print("🔧 Modificando estructura de la base de datos...")
        
        with engine.connect() as conn:
            # Añadir nueva columna user_agent_list
            print("   • Añadiendo columna user_agent_list...")
            conn.execute(text(
                "ALTER TABLE settings ADD COLUMN user_agent_list TEXT"
            ))
            
            # Añadir columna user_agent_rotation
            print("   • Añadiendo columna user_agent_rotation...")
            conn.execute(text(
                "ALTER TABLE settings ADD COLUMN user_agent_rotation INTEGER DEFAULT 1 NOT NULL"
            ))
            
            conn.commit()
        
        print("   ✅ Estructura actualizada")
        print()
        
        # 4. Migrar datos
        print("📤 Migrando datos...")
        
        # Convertir user_agent actual a user_agent_list (primera línea)
        # Añadir algunos User-Agents por defecto
        default_user_agents = [
            current_user_agent if current_user_agent else "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15"
        ]
        
        user_agent_list_str = "\n".join(default_user_agents)
        
        with engine.connect() as conn:
            conn.execute(
                text("UPDATE settings SET user_agent_list = :list, user_agent_rotation = 1 WHERE id = 1"),
                {"list": user_agent_list_str}
            )
            conn.commit()
        
        print(f"   ✅ Migrados {len(default_user_agents)} User-Agents")
        print()
        
        # 5. Verificar migración
        print("🔍 Verificando migración...")
        
        with engine.connect() as conn:
            result = conn.execute(text(
                "SELECT user_agent_list, user_agent_rotation FROM settings WHERE id = 1"
            )).first()
            
            if result:
                ua_list, ua_rotation = result
                if ua_list:
                    ua_count = len([ua for ua in ua_list.split('\n') if ua.strip()])
                    print(f"   ✅ user_agent_list: {ua_count} User-Agents configurados")
                    print(f"   ✅ user_agent_rotation: {'Activada' if ua_rotation else 'Desactivada'}")
                else:
                    print("   ❌ Error: user_agent_list está vacío")
                    return
            else:
                print("   ❌ Error: No se pudo verificar la migración")
                return
        
        print()
        print("=" * 60)
        print("✅ MIGRACIÓN COMPLETADA EXITOSAMENTE")
        print("=" * 60)
        print()
        print("📝 NOTA:")
        print("   El campo 'user_agent' antiguo se mantiene para compatibilidad.")
        print("   Ahora usa 'user_agent_list' y 'user_agent_rotation'.")
        print()
        print("🎯 Próximos pasos:")
        print("   1. Reinicia la aplicación: python main.py")
        print("   2. Verifica en /settings que aparecen los nuevos campos")
        print("   3. Ejecuta test: python scripts/test_scraper_config.py")
        print()
        
    except Exception as e:
        print()
        print("=" * 60)
        print("❌ ERROR EN MIGRACIÓN")
        print("=" * 60)
        print(f"Error: {e}")
        print()
        import traceback
        traceback.print_exc()
        print()
        print("💡 SOLUCIÓN:")
        print("   Si ya modificaste models.py, revierte los cambios temporalmente:")
        print("   1. Comenta las líneas de user_agent_list y user_agent_rotation")
        print("   2. Ejecuta este script de nuevo")
        print("   3. Descomenta las líneas")
        print()
        sys.exit(1)


if __name__ == "__main__":
    migrate()
