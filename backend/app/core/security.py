# backend/app/core/security.py
import os
from typing import Optional, Dict, Any
from jose import jwt, JWTError # type: ignore
from dotenv import load_dotenv

# Load environment variables
load_dotenv(dotenv_path=".env")  # Adjust path if needed

SUPABASE_JWT_SECRET: str = os.environ.get("SUPABASE_JWT_SECRET")
ALGORITHM = "HS256"  # Supabase uses HS256 for JWT signing

if not SUPABASE_JWT_SECRET:
    raise ValueError(
        "SUPABASE_JWT_SECRET must be set in environment variables.")


async def verify_supabase_jwt(token: str) -> Optional[Dict[str, Any]]:
    """
    Verifies a JWT token issued by Supabase.

    Args:
        token: The JWT token string.

    Returns:
        The decoded payload if the token is valid, otherwise None.
    """
    try:
        # Decode the token. It will automatically verify the signature
        # and expiration based on the secret and algorithm.
        # Supabase tokens have "authenticated" as their audience
        payload = jwt.decode(
            token,
            SUPABASE_JWT_SECRET,
            algorithms=[ALGORITHM],
            audience="authenticated"  # Add the expected audience
        )
        # You could add more checks here if needed (e.g., required claims)
        if 'sub' not in payload:  # 'sub' usually contains the user ID
            print("Token missing 'sub' claim.")
            return None

        return payload

    except JWTError as e:
        # Token is invalid (expired, wrong signature, malformed, etc.)
        print(f"JWT Error: {e}")
        return None
    except Exception as e:
        # Catch any other unexpected errors during decoding
        print(f"An unexpected error occurred during JWT verification: {e}")
        return None
