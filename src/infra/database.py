"""Database client for Neon PostgreSQL.

Provides async connection pool and query helpers for the Foundry API.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

from src.infra.logging import get_logger

logger = get_logger("database")

# We use httpx to call Neon's serverless driver endpoint
# This avoids needing psycopg2/asyncpg binary deps in Modal
import httpx
import json


class NeonDB:
    """Lightweight Neon database client using the serverless HTTP API.
    
    Supports two connection modes:
    1. Neon REST API URL (e.g., https://ep-xxx.apirest...neon.tech/neondb/rest/v1)
    2. PostgreSQL connection string (postgresql://user:pass@host/db)
    
    Uses HTTP so we don't need compiled PostgreSQL drivers in Modal.
    """
    
    def __init__(
        self,
        connection_string: Optional[str] = None,
        api_url: Optional[str] = None,
    ):
        self._connection_string = connection_string or os.environ.get("DATABASE_URL", "")
        self._api_url = api_url or os.environ.get(
            "NEON_API_URL",
            "https://ep-purple-band-ail6lb3c.apirest.c-4.us-east-1.aws.neon.tech/neondb/rest/v1"
        )
        self._client: Optional[httpx.AsyncClient] = None
    
    @property
    def is_configured(self) -> bool:
        return bool(self._connection_string)
    
    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client
    
    def _parse_connection_string(self) -> Dict[str, str]:
        """Parse postgresql://user:pass@host/db into components."""
        from urllib.parse import urlparse
        parsed = urlparse(self._connection_string)
        return {
            "host": parsed.hostname or "",
            "port": str(parsed.port or 5432),
            "user": parsed.username or "",
            "password": parsed.password or "",
            "database": parsed.path.lstrip("/") if parsed.path else "",
            "sslmode": "require",
        }
    
    async def execute(
        self,
        query: str,
        params: Optional[List[Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Execute a SQL query via Neon serverless HTTP API.
        
        Args:
            query: SQL query with $1, $2, ... placeholders.
            params: Query parameters.
            
        Returns:
            List of row dicts.
        """
        if not self.is_configured:
            logger.warning("Database not configured, skipping query")
            return []
        
        conn = self._parse_connection_string()
        client = await self._get_client()
        
        # Use Neon serverless SQL-over-HTTP
        # The proxy endpoint is at the same host as the connection
        api_url = f"https://{conn['host']}/sql"
        
        payload = {
            "query": query,
            "params": params or [],
        }
        
        try:
            response = await client.post(
                api_url,
                json=payload,
                headers={
                    "Neon-Connection-String": self._connection_string,
                    "Content-Type": "application/json",
                },
            )
            response.raise_for_status()
            
            data = response.json()
            
            # Neon returns { rows: [...], fields: [...] }
            if "rows" in data:
                fields = [f["name"] for f in data.get("fields", [])]
                return [dict(zip(fields, row)) for row in data["rows"]]
            
            return []
            
        except httpx.HTTPError as e:
            logger.error(f"Database query failed: {e}")
            raise
    
    async def execute_one(
        self,
        query: str,
        params: Optional[List[Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Execute a query and return the first row."""
        rows = await self.execute(query, params)
        return rows[0] if rows else None
    
    async def close(self):
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None


# Singleton
_db: Optional[NeonDB] = None


def get_db() -> NeonDB:
    """Get the database client singleton."""
    global _db
    if _db is None:
        _db = NeonDB()
    return _db
