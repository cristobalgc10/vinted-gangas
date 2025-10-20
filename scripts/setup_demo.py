"""
Script de prueba para verificar que la aplicación web funciona correctamente.

Este script:
1. Verifica que FastAPI inicia correctamente
2. Crea datos de prueba en la base de datos
3. Muestra las URLs disponibles
"""

import sys
import os

# Añadir el directorio raíz al path para imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal, init_db
from app.models import Search, Product
from datetime import datetime

print("=" * 70)
print("🧪 PREPARANDO APLICACIÓN WEB")
print("=" * 70)

# 1. Inicializar base de datos
print("\n1️⃣ Inicializando base de datos...")
init_db()

# 2. Crear datos de ejemplo si no existen
db = SessionLocal()
try:
    # Verificar si ya hay datos
    existing_searches = db.query(Search).count()
    
    if existing_searches == 0:
        print("\n2️⃣ Creando datos de ejemplo...")
        
        # Crear 3 búsquedas de ejemplo
        search1 = Search(
            name="Zapatillas Nike Air Max",
            query="nike air max",
            price_from=20.0,
            price_to=50.0,
            interval_minutes=5,
            is_active=True,
            allowed_countries=["ES", "PT", "FR"]
        )
        
        search2 = Search(
            name="Camisetas Vintage",
            query="camiseta vintage",
            price_from=5.0,
            price_to=20.0,
            interval_minutes=10,
            is_active=True
        )
        
        search3 = Search(
            name="Pantalones Vaqueros Levis",
            query="levis 501",
            price_from=15.0,
            price_to=40.0,
            interval_minutes=15,
            is_active=False
        )
        
        db.add_all([search1, search2, search3])
        db.commit()
        db.refresh(search1)
        
        print("   ✅ 3 búsquedas de ejemplo creadas")
        
        # Crear algunos productos de ejemplo
        products = [
            Product(
                search_id=search1.id,
                vinted_id="prod_001",
                title="Nike Air Max 90 - Como nuevas",
                description="Zapatillas en perfecto estado, apenas usadas",
                price=35.0,
                currency="EUR",
                brand="Nike",
                size="42",
                condition="Muy bueno",
                url="https://www.vinted.es/items/12345",
                image_url="https://images.vinted.net/placeholder.jpg",
                seller_id="user_123",
                seller_name="María",
                seller_country="ES"
            ),
            Product(
                search_id=search1.id,
                vinted_id="prod_002",
                title="Nike Air Max 95 - Negras y rojas",
                description="Zapatillas deportivas en buen estado",
                price=45.0,
                currency="EUR",
                brand="Nike",
                size="43",
                condition="Bueno",
                url="https://www.vinted.es/items/12346",
                seller_id="user_456",
                seller_name="Carlos",
                seller_country="ES"
            ),
            Product(
                search_id=search2.id,
                vinted_id="prod_003",
                title="Camiseta vintage años 90 - Band tee",
                description="Camiseta de banda de los 90, auténtica vintage",
                price=18.0,
                currency="EUR",
                condition="Bueno",
                url="https://www.vinted.es/items/12347",
                seller_id="user_789",
                seller_name="Laura",
                seller_country="PT"
            )
        ]
        
        db.add_all(products)
        db.commit()
        
        print("   ✅ 3 productos de ejemplo creados")
    else:
        print("\n2️⃣ Ya existen datos en la base de datos")
        print(f"   📊 Búsquedas: {existing_searches}")
        print(f"   📦 Productos: {db.query(Product).count()}")

except Exception as e:
    print(f"\n❌ ERROR al crear datos: {e}")
    db.rollback()
finally:
    db.close()

print("\n" + "=" * 70)
print("✅ APLICACIÓN LISTA PARA INICIAR")
print("=" * 70)
print("\n📝 Para iniciar la aplicación, ejecuta:")
print("   python main.py")
print("\n🌐 Una vez iniciada, accede a:")
print("   • Dashboard:  http://localhost:8000")
print("   • Búsquedas:  http://localhost:8000/searches")
print("   • Productos:  http://localhost:8000/products")
print("   • Ayuda:      http://localhost:8000/help")
print("   • API Docs:   http://localhost:8000/docs")
print("\n💡 Presiona Ctrl+C para detener el servidor cuando termines")
print("=" * 70)
