"""
Configuración de la base de datos usando SQLAlchemy.

SQLAlchemy es un ORM (Object-Relational Mapping) que nos permite:
- Trabajar con la BD usando objetos Python en lugar de SQL directo
- Cambiar de BD (SQLite a PostgreSQL) sin cambiar código
- Tener migraciones y versionado de esquema
"""

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from config import settings

# 1. ENGINE: Conexión a la base de datos
# connect_args solo es necesario para SQLite (permite múltiples threads)
engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {},
    echo=settings.DEBUG  # Si DEBUG=True, imprime todas las queries SQL (útil para aprender)
)

# 2. SESSION: Forma de interactuar con la BD
# - autocommit=False: Las transacciones deben confirmarse manualmente
# - autoflush=False: No guarda automáticamente antes de cada query
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 3. BASE: Clase base para todos los modelos
# Todos nuestros modelos heredarán de esta clase
Base = declarative_base()


def get_db():
    """
    Dependency que proporciona una sesión de BD.
    
    Uso en FastAPI:
        @app.get("/items")
        def read_items(db: Session = Depends(get_db)):
            items = db.query(Item).all()
            return items
    
    El 'finally' asegura que la conexión se cierre siempre,
    incluso si hay un error.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    Crea todas las tablas en la base de datos.
    Se ejecuta al iniciar la aplicación.
    """
    # Importamos los modelos aquí para evitar importaciones circulares
    from app import models  # noqa: F401
    
    Base.metadata.create_all(bind=engine)
    print("✅ Base de datos inicializada correctamente")
