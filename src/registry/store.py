"""Registry storage implementations.

This module provides different storage backends for the tool registry:
- InMemoryRegistry: For local development and MVP
- ModalDictRegistry: For Modal deployment (persistent across restarts)
- NeonRegistry: For production with PostgreSQL (placeholder)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

from src.api.schemas import ToolRegistryEntry, ToolStatus
from src.infra.logging import get_logger

logger = get_logger("registry")


class RegistryBase(ABC):
    """Abstract base class for registry storage."""

    @abstractmethod
    def get(self, tool_id: str) -> Optional[ToolRegistryEntry]:
        """Get a tool by ID."""
        ...

    @abstractmethod
    def set(self, tool_id: str, entry: ToolRegistryEntry) -> None:
        """Store a tool."""
        ...

    @abstractmethod
    def delete(self, tool_id: str) -> bool:
        """Delete a tool. Returns True if deleted, False if not found."""
        ...

    @abstractmethod
    def list_all(self, org_id: Optional[str] = None) -> List[ToolRegistryEntry]:
        """List all tools, optionally filtered by org_id."""
        ...

    @abstractmethod
    def cleanup_expired(self) -> int:
        """Remove expired tools. Returns count of removed tools."""
        ...

    def _is_expired(self, entry: ToolRegistryEntry) -> bool:
        """Check if a tool has expired."""
        if not entry.expires_at:
            return False
        return datetime.now(timezone.utc) > entry.expires_at


class InMemoryRegistry(RegistryBase):
    """In-memory registry for local development.
    
    Also supports dict-like access for backward compatibility.
    """

    def __init__(self):
        self._store: Dict[str, ToolRegistryEntry] = {}

    def get(self, tool_id: str) -> Optional[ToolRegistryEntry]:
        entry = self._store.get(tool_id)
        if entry and self._is_expired(entry):
            entry.status = ToolStatus.EXPIRED
            self._store[tool_id] = entry
        return entry

    def set(self, tool_id: str, entry: ToolRegistryEntry) -> None:
        self._store[tool_id] = entry

    def delete(self, tool_id: str) -> bool:
        if tool_id in self._store:
            del self._store[tool_id]
            return True
        return False

    def list_all(self, org_id: Optional[str] = None) -> List[ToolRegistryEntry]:
        entries = []
        for entry in self._store.values():
            if org_id and entry.org_id != org_id:
                continue
            if self._is_expired(entry):
                entry.status = ToolStatus.EXPIRED
            entries.append(entry)
        return entries

    def cleanup_expired(self) -> int:
        """Remove expired tools."""
        now = datetime.now(timezone.utc)
        expired = [
            tool_id
            for tool_id, entry in self._store.items()
            if entry.expires_at and entry.expires_at < now
        ]
        for tool_id in expired:
            del self._store[tool_id]
        return len(expired)

    def clear(self) -> None:
        """Clear all entries (for testing)."""
        self._store.clear()

    # Dict-like access for backward compatibility
    def __getitem__(self, tool_id: str) -> ToolRegistryEntry:
        entry = self.get(tool_id)
        if entry is None:
            raise KeyError(tool_id)
        return entry

    def __setitem__(self, tool_id: str, entry: ToolRegistryEntry) -> None:
        self.set(tool_id, entry)

    def __delitem__(self, tool_id: str) -> None:
        if not self.delete(tool_id):
            raise KeyError(tool_id)

    def __contains__(self, tool_id: str) -> bool:
        return tool_id in self._store

    def values(self):
        return self._store.values()

    def items(self):
        return self._store.items()

    def keys(self):
        return self._store.keys()


class ModalDictRegistry(RegistryBase):
    """
    Registry backed by Modal Dict for persistent storage.

    Modal Dict provides:
    - Persistence across function restarts
    - Shared state between function instances
    - Automatic serialization
    
    Also supports dict-like access for backward compatibility.
    """

    def __init__(self, dict_name: str = "tool-foundry-registry"):
        self._dict_name = dict_name
        self._dict: Optional[Any] = None

    def _get_dict(self) -> Any:
        """Get or create the Modal Dict."""
        if self._dict is None:
            try:
                import modal
                self._dict = modal.Dict.from_name(
                    self._dict_name,
                    create_if_missing=True,
                )
                logger.info(f"Connected to Modal Dict: {self._dict_name}")
            except ImportError:
                raise RuntimeError("Modal is required for ModalDictRegistry")
            except Exception as e:
                logger.error(f"Failed to connect to Modal Dict: {e}")
                raise
        return self._dict

    def get(self, tool_id: str) -> Optional[ToolRegistryEntry]:
        """Get a tool by ID."""
        try:
            modal_dict = self._get_dict()
            data = modal_dict.get(tool_id)
            if data is None:
                return None

            entry = ToolRegistryEntry.model_validate_json(data)

            # Check expiration
            if self._is_expired(entry):
                entry.status = ToolStatus.EXPIRED
                # Update in dict
                modal_dict[tool_id] = entry.model_dump_json()

            return entry
        except Exception as e:
            logger.error(f"Failed to get tool {tool_id}: {e}")
            return None

    def set(self, tool_id: str, entry: ToolRegistryEntry) -> None:
        """Store a tool."""
        try:
            modal_dict = self._get_dict()
            modal_dict[tool_id] = entry.model_dump_json()
            logger.debug(f"Stored tool {tool_id}")
        except Exception as e:
            logger.error(f"Failed to set tool {tool_id}: {e}")
            raise

    def delete(self, tool_id: str) -> bool:
        """Delete a tool."""
        try:
            modal_dict = self._get_dict()
            if tool_id in modal_dict:
                del modal_dict[tool_id]
                logger.debug(f"Deleted tool {tool_id}")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to delete tool {tool_id}: {e}")
            return False

    def list_all(self, org_id: Optional[str] = None) -> List[ToolRegistryEntry]:
        """List all tools, optionally filtered by org_id."""
        try:
            modal_dict = self._get_dict()
            entries = []

            # Modal Dict supports iteration
            for tool_id in modal_dict.keys():
                try:
                    data = modal_dict.get(tool_id)
                    if data:
                        entry = ToolRegistryEntry.model_validate_json(data)

                        # Filter by org_id if specified
                        if org_id and entry.org_id != org_id:
                            continue

                        # Check expiration
                        if self._is_expired(entry):
                            entry.status = ToolStatus.EXPIRED

                        entries.append(entry)
                except Exception as e:
                    logger.warning(f"Failed to parse tool {tool_id}: {e}")
                    continue

            return entries
        except Exception as e:
            logger.error(f"Failed to list tools: {e}")
            return []

    def cleanup_expired(self) -> int:
        """Remove expired tools."""
        try:
            modal_dict = self._get_dict()
            now = datetime.now(timezone.utc)
            expired_count = 0

            for tool_id in list(modal_dict.keys()):
                try:
                    data = modal_dict.get(tool_id)
                    if data:
                        entry = ToolRegistryEntry.model_validate_json(data)
                        if entry.expires_at and entry.expires_at < now:
                            del modal_dict[tool_id]
                            expired_count += 1
                            logger.debug(f"Cleaned up expired tool {tool_id}")
                except Exception as e:
                    logger.warning(f"Failed to check expiration for {tool_id}: {e}")
                    continue

            if expired_count > 0:
                logger.info(f"Cleaned up {expired_count} expired tools")
            return expired_count
        except Exception as e:
            logger.error(f"Failed to cleanup expired tools: {e}")
            return 0

    # Dict-like access for backward compatibility
    def __getitem__(self, tool_id: str) -> ToolRegistryEntry:
        entry = self.get(tool_id)
        if entry is None:
            raise KeyError(tool_id)
        return entry

    def __setitem__(self, tool_id: str, entry: ToolRegistryEntry) -> None:
        self.set(tool_id, entry)

    def __delitem__(self, tool_id: str) -> None:
        if not self.delete(tool_id):
            raise KeyError(tool_id)

    def __contains__(self, tool_id: str) -> bool:
        return self.get(tool_id) is not None

    def values(self):
        return [e for e in self.list_all()]

    def items(self):
        return [(e.tool_id, e) for e in self.list_all()]

    def keys(self):
        return [e.tool_id for e in self.list_all()]
    
    def clear(self) -> None:
        """Clear all entries."""
        modal_dict = self._get_dict()
        for tool_id in list(modal_dict.keys()):
            del modal_dict[tool_id]


def create_registry(use_modal: bool = False) -> RegistryBase:
    """
    Create the appropriate registry based on configuration.

    Args:
        use_modal: If True, use Modal Dict registry.

    Returns:
        RegistryBase instance.
    """
    if use_modal:
        try:
            import modal  # noqa: F401
            logger.info("Using Modal Dict registry")
            return ModalDictRegistry()
        except ImportError:
            logger.warning("Modal not available, falling back to in-memory registry")

    logger.info("Using in-memory registry")
    return InMemoryRegistry()


# Singleton registry instance
_registry: Optional[RegistryBase] = None


def get_registry(use_modal: bool = False) -> RegistryBase:
    """Get the singleton registry instance."""
    global _registry
    if _registry is None:
        _registry = create_registry(use_modal=use_modal)
    return _registry
