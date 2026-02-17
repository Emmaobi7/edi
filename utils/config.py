import os

class Settings:
    # Use DATABASE_URL from .env if available, otherwise build from components
    SQLALCHEMY_DATABASE_URI: str = os.getenv('DATABASE_URL')

    if not SQLALCHEMY_DATABASE_URI:
        DB_USER: str = os.getenv('POSTGRES_USER', 'postgres')
        DB_PASSWORD: str = os.getenv('POSTGRES_PASSWORD', 'postgres')
        DB_HOST: str = os.getenv('POSTGRES_HOST', 'localhost')
        DB_PORT: str = os.getenv('POSTGRES_PORT', '5432')
        DB_NAME: str = os.getenv('POSTGRES_DB', 'govcon')
        DB_SCHEMA: str = 'mercury'
        SQLALCHEMY_DATABASE_URI: str = (
            f"postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
        )
        # For Alembic (sync driver)
        SQLALCHEMY_SYNC_DATABASE_URI: str = (
            f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
        )

    APP_NAME: str = os.getenv('APP_NAME', 'Mercury-Python')

settings = Settings() 