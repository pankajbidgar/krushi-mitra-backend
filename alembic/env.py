import sys
from pathlib import Path
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool
from alembic import context

# तुझ्या प्रोजेक्टचा रूट पाथ (backend) sys.path मध्ये जोडा
sys.path.append(str(Path(__file__).parent.parent))

# आता तुझे मॉडेल्स आणि बेस इम्पोर्ट करा
from database import Base   # तुझ्या database.py मधील Base
from models import *        # सर्व मॉडेल्स इम्पोर्ट होतील (यामुळे metadata मध्ये सर्व टेबल्स रजिस्टर होतील)

# Alembic Config ऑब्जेक्ट
config = context.config

# लॉगिंग कॉन्फिगरेशन
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# महत्त्वाचे: target_metadata ला तुझ्या Base चे metadata द्या
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Offline mode मायग्रेशन (SQL स्क्रिप्ट जनरेट करण्यासाठी)"""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Online mode मायग्रेशन (थेट डेटाबेसवर लागू करण्यासाठी)"""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()