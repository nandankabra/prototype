from alembic import context
from app.core.database import Base, engine
import app.models  # register ORM tables

with engine.connect() as connection:
    context.configure(connection=connection, target_metadata=Base.metadata)
    with context.begin_transaction():
        context.run_migrations()
