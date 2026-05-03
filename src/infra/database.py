"""Database client for Neon PostgreSQL.

Provides async connection pool and query helpers for the Foundry API.
Uses Neon's serverless HTTP driver so we don't need compiled PostgreSQL
drivers in the Modal container.
"""

from __future__ import annotations

import os
import json
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse, urlunparse

from src.infra.logging import get_logger

logger = get_logger("database")

import httpx


class NeonDB:
    """Lightweight Neon database client using the serverless HTTP API.
    
    Uses Neon's SQL-over-HTTP endpoint (/sql) which works without
    compiled PostgreSQL drivers.
    """
    
    def __init__(self, connection_string: Optional[str] = None):
        self._connection_string = connection_string or os.environ.get("DATABASE_URL", "")
        self._client: Optional[httpx.AsyncClient] = None
        self._http_host: Optional[str] = None
        self._http_connection_string: Optional[str] = None
        
        if self._connection_string:
            self._setup_http_endpoint()
    
    def _setup_http_endpoint(self):
        """Derive the HTTP endpoint from the connection string.
        
        Neon's /sql endpoint requires the non-pooler hostname.
        Pooler hostnames contain '-pooler' which must be stripped.
        """
        parsed = urlparse(self._connection_string)
        host = parsed.hostname or ""
        
        # Strip -pooler suffix for HTTP endpoint
        # e.g., ep-xxx-pooler.region.aws.neon.tech → ep-xxx.region.aws.neon.tech
        http_host = host.replace("-pooler", "")
        self._http_host = http_host
        
        # Build a non-pooler connection string for the Neon-Connection-String header
        # Replace the hostname in the connection string
        self._http_connection_string = self._connection_string.replace(host, http_host)
        
        # Also remove channel_binding parameter if present (not supported over HTTP)
        self._http_connection_string = self._http_connection_string.replace("&channel_binding=require", "")
        self._http_connection_string = self._http_connection_string.replace("?channel_binding=require&", "?")
        self._http_connection_string = self._http_connection_string.replace("?channel_binding=require", "")
        
        logger.info(f"Neon HTTP endpoint: {http_host}")
    
    @property
    def is_configured(self) -> bool:
        return bool(self._connection_string)
    
    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client
    
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
        
        client = await self._get_client()
        api_url = f"https://{self._http_host}/sql"
        
        payload = {
            "query": query,
            "params": params or [],
        }
        
        try:
            response = await client.post(
                api_url,
                json=payload,
                headers={
                    "Neon-Connection-String": self._http_connection_string,
                    "Content-Type": "application/json",
                },
            )
            response.raise_for_status()
            
            data = response.json()
            
            # Neon HTTP API returns:
            # { rows: [{col: val, ...}, ...], fields: [...], rowAsArray: false }
            # Rows are already dicts when rowAsArray is false (default)
            if "rows" in data:
                if data.get("rowAsArray", False):
                    # Array mode: zip field names with row arrays
                    fields = [f["name"] for f in data.get("fields", [])]
                    return [dict(zip(fields, row)) for row in data["rows"]]
                else:
                    # Object mode (default): rows are already dicts
                    return data["rows"]
            
            return []
            
        except httpx.HTTPStatusError as e:
            logger.error(f"Database query failed (HTTP {e.response.status_code}): {e.response.text}")
            raise
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
