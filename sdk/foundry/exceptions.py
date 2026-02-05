"""Foundry SDK exceptions."""


class FoundryError(Exception):
    """Base exception for Foundry SDK."""
    pass


class ToolCreationError(FoundryError):
    """Raised when tool creation fails."""
    
    def __init__(self, message: str, request_id: str = None):
        super().__init__(message)
        self.request_id = request_id


class ToolInvocationError(FoundryError):
    """Raised when tool invocation fails."""
    
    def __init__(self, message: str, tool_id: str = None, execution_time_ms: int = None):
        super().__init__(message)
        self.tool_id = tool_id
        self.execution_time_ms = execution_time_ms


class ToolNotReadyError(FoundryError):
    """Raised when trying to invoke a tool that isn't ready."""
    pass


class ChainError(FoundryError):
    """Raised when tool chaining fails."""
    
    def __init__(self, message: str, step: int = None, tool_id: str = None):
        super().__init__(message)
        self.step = step
        self.tool_id = tool_id
