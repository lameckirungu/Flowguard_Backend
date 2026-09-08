from sqlalchemy import create_engine, text

from app.core.config import settings


def reset_database():
    engine = create_engine(str(settings.database_url), isolation_level="AUTOCOMMIT")
    
    with engine.connect() as conn:
        # Wipe everything
        conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE;"))
        conn.execute(text("DROP SCHEMA IF EXISTS master CASCADE;"))
        conn.execute(text("DROP SCHEMA IF EXISTS bronze CASCADE;"))
        conn.execute(text("DROP SCHEMA IF EXISTS silver CASCADE;"))
        conn.execute(text("DROP SCHEMA IF EXISTS gold CASCADE;"))
        
        # Recreate public specifically for PostgreSQL ENUMs and Extensions
        conn.execute(text("CREATE SCHEMA public;"))
        
        # Create the Medallion schemas for our application tables
        conn.execute(text("CREATE SCHEMA master;"))
        conn.execute(text("CREATE SCHEMA bronze;"))
        conn.execute(text("CREATE SCHEMA silver;"))
        conn.execute(text("CREATE SCHEMA gold;"))
        
    print("✅ Database wiped. Schemas (public, master, bronze, silver, gold) created.")

if __name__ == "__main__":
    reset_database()