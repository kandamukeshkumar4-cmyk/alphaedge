from app.db.session import async_engine_settings


def test_async_engine_settings_converts_neon_sslmode_for_asyncpg():
    url = (
        "postgresql+asyncpg://neondb_owner:secret@example.neon.tech/neondb"
        "?sslmode=require&channel_binding=require"
    )

    engine_url, kwargs = async_engine_settings(url)

    assert engine_url == "postgresql+asyncpg://neondb_owner:secret@example.neon.tech/neondb"
    assert kwargs == {"connect_args": {"ssl": True}}


def test_async_engine_settings_converts_asyncpg_ssl_query_to_connect_args():
    url = "postgresql+asyncpg://neondb_owner:secret@example.neon.tech/neondb?ssl=true"

    engine_url, kwargs = async_engine_settings(url)

    assert engine_url == "postgresql+asyncpg://neondb_owner:secret@example.neon.tech/neondb"
    assert kwargs == {"connect_args": {"ssl": True}}
