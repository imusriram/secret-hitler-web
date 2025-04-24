# backend/app/core/db.py
import os
from supabase import create_async_client, AsyncClient
from supabase.lib.client_options import ClientOptions
from dotenv import load_dotenv

# Load environment variables from .env file
# Adjust path if .env is elsewhere relative to execution
load_dotenv(dotenv_path="../../.env")

supabase_url: str = os.environ.get("SUPABASE_URL")
# Use Service Role Key for backend
supabase_key: str = os.environ.get("SUPABASE_SERVICE_KEY")

if not supabase_url or not supabase_key:
    raise ValueError(
        "Supabase URL and Key must be set in environment variables.")

# Consider adding options if needed, e.g., schema, timeout
# options: ClientOptions = ClientOptions(schema="public", ...)
# supabase_client: AsyncClient = create_client(supabase_url, supabase_key, options=options)

# Simpler initialization for now


print("Supabase client initialized.")


async def get_supabase_client() -> AsyncClient:
    """Dependency function to get the Supabase client."""
    supabase_client: AsyncClient = await create_async_client(supabase_url, supabase_key)
    return supabase_client
