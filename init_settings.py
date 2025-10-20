"""
Script de migración para crear la tabla de configuración.

Ejecuta este script para añadir la tabla 'settings' a tu base de datos existente.

Uso:
    python init_settings.py
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from config import settings as app_config
from app.database import Base
from app.models import Settings

def init_settings_table():
    """
    Crea la tabla de configuración si no existe.
    """
    print("🔧 Inicializando tabla de configuración...")
    
    # Conectar a la base de datos
    engine = create_engine(
        app_config.DATABASE_URL,
        connect_args={"check_same_thread": False} if "sqlite" in app_config.DATABASE_URL else {}
    )
    
    # Crear solo la tabla Settings si no existe
    Base.metadata.create_all(bind=engine, tables=[Settings.__table__])
    
    print("✅ Tabla 'settings' creada correctamente")
    
    # Crear sesión
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    try:
        # Verificar si ya existe configuración
        existing_settings = db.query(Settings).filter(Settings.id == 1).first()
        
        if existing_settings:
            print("ℹ️  Ya existe una configuración en la base de datos")
        else:
            # Crear configuración por defecto
            default_settings = Settings(id=1)
            db.add(default_settings)
            db.commit()
            print("✅ Configuración por defecto creada")
            
            # Mostrar configuración creada
            print("\n📋 Configuración inicial:")
            print(f"  - Dominio Vinted: {default_settings.vinted_domain}")
            print(f"  - Tema: {default_settings.theme}")
            print(f"  - Idioma: {default_settings.language}")
            print(f"  - Moneda: {default_settings.currency}")
            print(f"  - Productos máx por búsqueda: {default_settings.max_products_per_search}")
            print(f"  - Eliminar productos después de: {default_settings.auto_delete_products_days} días")
            
    except Exception as e:
        print(f"❌ Error al crear configuración: {e}")
        db.rollback()
    finally:
        db.close()
    
    print("\n🎉 Migración completada")


if __name__ == "__main__":
    init_settings_table()
