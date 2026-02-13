"""FastAPI routes for Tool Foundry API.

Organized with versioned routers and proper separation of concerns.
"""

from __future__ import annotations

import secrets
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks, APIRouter, Depends, Header, Security, Request
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.security import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware

from src.api.schemas import (
    BuildStatusResponse,
    CreateCapabilityRequest,
    CreateCapabilityResponse,
    CreateToolRequest,
    CreateToolResponse,
    DeprecateToolRequest,
    HealthResponse,
    InvokeRequest,
    InvokeResponse,
    RebuildToolRequest,
    RebuildToolResponse,
    SearchRequest,
    SearchResponse,
    SearchResult,
    ToolManifest,
    ToolRegistryEntry,
    ToolStatus,
)
from src.builder.validator import validate_restricted_python
from src.infra.config import get_settings
from src.infra.logging import get_logger, setup_logging
from src.infra.secrets import get_anthropic_api_key, has_llm_provider
from src.api.auth import AuthContext, validate_api_key, require_auth, track_usage, check_usage_limit

# Setup logging on import
setup_logging()
logger = get_logger("api")

# =============================================================================
# Registry Setup
# =============================================================================

from src.registry.store import RegistryBase, InMemoryRegistry, ModalDictRegistry

_registry_instance: Optional[RegistryBase] = None


def get_registry() -> RegistryBase:
    """Get the registry instance, initializing if needed."""
    global _registry_instance
    if _registry_instance is not None:
        return _registry_instance

    try:
        import os

        if os.environ.get("MODAL_ENVIRONMENT"):
            _registry_instance = ModalDictRegistry("tool-foundry-registry")
            logger.info("Using Modal Dict registry for persistence")
            return _registry_instance
    except Exception as e:
        logger.warning(f"Could not initialize Modal Dict: {e}")

    _registry_instance = InMemoryRegistry()
    logger.info("Using in-memory registry")
    return _registry_instance


# =============================================================================
# API Key Authentication (DB-backed via src.api.auth)
# =============================================================================
# Auth is handled by validate_api_key (optional) and require_auth (mandatory)
# imported from src.api.auth. These look up hashed keys in Postgres.


# In-memory build requests tracking
_build_requests: Dict[str, Dict] = {}


def get_base_url() -> str:
    """Get the base URL for the deployed service.
    
    Priority:
    1. MODAL_SERVE_URL (set during local `modal serve`)
    2. FOUNDRY_API_BASE_URL (explicit override)
    3. Auto-detect from Modal environment
    4. Fallback to localhost for development
    """
    import os

    # 1. Modal local serve URL (set during `modal serve`)
    modal_url = os.environ.get("MODAL_SERVE_URL")
    if modal_url:
        return modal_url.rstrip("/")

    # 2. Explicit override from settings/env
    settings = get_settings()
    if settings.api_base_url:
        return settings.api_base_url.rstrip("/")

    # 3. Check for explicit base URL env var
    explicit_url = os.environ.get("FOUNDRY_API_BASE_URL")
    if explicit_url:
        return explicit_url.rstrip("/")

    # 4. Auto-detect if running in Modal (check for Modal-specific env vars)
    if os.environ.get("MODAL_ENVIRONMENT") or os.environ.get("MODAL_TASK_ID"):
        # We're in Modal - use the known deployment URL pattern
        # This can be overridden via FOUNDRY_API_BASE_URL if the workspace changes
        return "https://camfleety--toolfoundry-serve.modal.run"

    # 5. Development fallback
    return "http://localhost:8000"


# =============================================================================
# Landing Page
# =============================================================================

def get_landing_page() -> str:
    """Return the landing page HTML."""
    base_url = get_base_url()
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Foundry - AI Agents Building Tools for Themselves</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        :root {{ --pink: #e91e8c; --magenta: #c026d3; --orange: #f97316; --yellow: #fbbf24; --dark: #0a0a0a; --light: #fafafa; }}
        body {{ font-family: 'Space Grotesk', -apple-system, sans-serif; background: var(--dark); color: var(--dark); overflow-x: hidden; }}
        
        nav {{ position: fixed; top: 0; left: 0; right: 0; z-index: 100; padding: 20px 40px; display: flex; justify-content: space-between; align-items: center; background: transparent; transition: background 0.3s ease; }}
        nav.scrolled {{ background: rgba(10, 10, 10, 0.95); backdrop-filter: blur(10px); }}
        .logo {{ font-size: 1.75rem; font-weight: 700; color: var(--dark); text-decoration: none; letter-spacing: -0.5px; font-style: italic; }}
        nav.scrolled .logo {{ color: var(--light); }}
        .nav-links {{ display: flex; gap: 32px; align-items: center; }}
        .nav-links a {{ color: var(--dark); text-decoration: none; font-size: 0.875rem; font-weight: 500; letter-spacing: 0.5px; text-transform: uppercase; transition: opacity 0.2s; }}
        nav.scrolled .nav-links a {{ color: var(--light); }}
        .nav-links a:hover {{ opacity: 0.7; }}
        .nav-cta {{ background: var(--dark) !important; color: var(--light) !important; padding: 10px 20px; border-radius: 6px; }}
        nav.scrolled .nav-cta {{ background: var(--light) !important; color: var(--dark) !important; }}
        
        .hero {{ min-height: 100vh; display: flex; flex-direction: column; justify-content: center; align-items: center; text-align: center; position: relative; padding: 120px 20px 80px; background: linear-gradient(180deg, #f472b6 0%, #fb923c 30%, #fbbf24 50%, #fb923c 70%, #f472b6 100%); overflow: hidden; }}
        .hero::before {{ content: ''; position: absolute; top: 50%; left: 50%; width: 200%; height: 200%; transform: translate(-50%, -50%); background: repeating-conic-gradient(from 0deg, transparent 0deg 4deg, rgba(255,255,255,0.03) 4deg 8deg); pointer-events: none; }}
        .hero::after {{ content: ''; position: absolute; top: 0; left: 0; right: 0; bottom: 0; background: linear-gradient(0deg, transparent 0%, rgba(236, 72, 153, 0.3) 5%, transparent 10%, transparent 20%, rgba(236, 72, 153, 0.2) 25%, transparent 30%, transparent 70%, rgba(236, 72, 153, 0.2) 75%, transparent 80%, transparent 90%, rgba(236, 72, 153, 0.3) 95%, transparent 100%); pointer-events: none; }}
        .hero-content {{ position: relative; z-index: 10; max-width: 1000px; }}
        .hero h1 {{ font-size: clamp(2.5rem, 6vw, 4.5rem); font-weight: 700; line-height: 1.15; margin-bottom: 24px; letter-spacing: -2px; }}
        .hero h1 .static {{ display: block; }}
        .hero h1 .rotating-wrapper {{ display: inline-block; position: relative; }}
        .hero h1 .rotating-text {{ display: inline-block; color: var(--dark); background: rgba(255,255,255,0.2); padding: 4px 16px; border-radius: 8px; animation: fadeInOut 3s ease-in-out infinite; min-width: 280px; }}
        @keyframes fadeInOut {{
            0%, 100% {{ opacity: 0; transform: translateY(10px); }}
            10%, 90% {{ opacity: 1; transform: translateY(0); }}
        }}
        .hero p {{ font-size: 1.25rem; max-width: 600px; margin: 0 auto 40px; opacity: 0.9; }}
        .cta-buttons {{ display: flex; gap: 16px; justify-content: center; flex-wrap: wrap; }}
        .btn {{ padding: 16px 32px; font-size: 0.875rem; font-weight: 600; text-transform: uppercase; letter-spacing: 1px; text-decoration: none; border-radius: 6px; transition: all 0.2s ease; font-family: inherit; cursor: pointer; border: none; }}
        .btn-primary {{ background: #dc2626; color: white; }}
        .btn-primary:hover {{ background: #b91c1c; transform: translateY(-2px); }}
        .btn-secondary {{ background: transparent; color: var(--dark); border: 2px solid var(--dark); }}
        .btn-secondary:hover {{ background: var(--dark); color: var(--light); }}
        
        .trust {{ padding: 60px 40px; text-align: center; background: linear-gradient(180deg, #f472b6 0%, var(--dark) 100%); }}
        .trust-label {{ font-size: 0.75rem; letter-spacing: 2px; text-transform: uppercase; margin-bottom: 32px; opacity: 0.8; }}
        .trust-logos {{ display: flex; justify-content: center; align-items: center; gap: 48px; flex-wrap: wrap; max-width: 800px; margin: 0 auto; }}
        .trust-logo {{ font-size: 1.25rem; font-weight: 600; opacity: 0.7; }}
        
        .features {{ background: var(--dark); color: var(--light); padding: 120px 40px; }}
        .features-header {{ text-align: center; max-width: 700px; margin: 0 auto 80px; }}
        .features-header h2 {{ font-size: clamp(2rem, 5vw, 3rem); margin-bottom: 20px; letter-spacing: -1px; }}
        .features-header p {{ font-size: 1.125rem; opacity: 0.7; line-height: 1.7; }}
        .features-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 40px; max-width: 1200px; margin: 0 auto; }}
        .feature-card {{ background: linear-gradient(135deg, rgba(255,255,255,0.05) 0%, rgba(255,255,255,0.02) 100%); border: 1px solid rgba(255,255,255,0.1); border-radius: 16px; padding: 40px; transition: all 0.3s ease; }}
        .feature-card:hover {{ transform: translateY(-4px); border-color: rgba(255,255,255,0.2); }}
        .feature-icon {{ width: 48px; height: 48px; background: linear-gradient(135deg, var(--pink) 0%, var(--orange) 100%); border-radius: 12px; display: flex; align-items: center; justify-content: center; margin-bottom: 24px; font-size: 1.5rem; }}
        .feature-card h3 {{ font-size: 1.25rem; margin-bottom: 12px; }}
        .feature-card p {{ opacity: 0.7; line-height: 1.6; }}
        
        .demo {{ background: var(--dark); color: var(--light); padding: 80px 40px 120px; }}
        .demo-container {{ max-width: 1000px; margin: 0 auto; }}
        .demo h2 {{ text-align: center; font-size: clamp(2rem, 5vw, 3rem); margin-bottom: 48px; letter-spacing: -1px; }}
        .code-block {{ background: #1a1a1a; border: 1px solid rgba(255,255,255,0.1); border-radius: 16px; overflow: hidden; }}
        .code-header {{ background: rgba(255,255,255,0.05); padding: 16px 24px; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid rgba(255,255,255,0.1); }}
        .code-dots {{ display: flex; gap: 8px; }}
        .code-dot {{ width: 12px; height: 12px; border-radius: 50%; }}
        .code-dot.red {{ background: #ff5f57; }}
        .code-dot.yellow {{ background: #febc2e; }}
        .code-dot.green {{ background: #28c840; }}
        .code-title {{ font-family: monospace; font-size: 0.875rem; opacity: 0.7; }}
        .code-content {{ padding: 24px; font-family: monospace; font-size: 0.875rem; line-height: 1.8; overflow-x: auto; white-space: pre; }}
        .comment {{ color: #6b7280; }}
        .string {{ color: #4ade80; }}
        .property {{ color: #fbbf24; }}
        
        .cta-section {{ background: linear-gradient(135deg, var(--magenta) 0%, var(--orange) 100%); padding: 120px 40px; text-align: center; }}
        .cta-section h2 {{ font-size: clamp(2rem, 5vw, 3.5rem); margin-bottom: 20px; letter-spacing: -1px; }}
        .cta-section p {{ font-size: 1.25rem; max-width: 600px; margin: 0 auto 40px; opacity: 0.9; }}
        
        footer {{ background: var(--dark); color: var(--light); padding: 60px 40px; text-align: center; }}
        .footer-links {{ display: flex; justify-content: center; gap: 32px; margin-bottom: 24px; flex-wrap: wrap; }}
        .footer-links a {{ color: var(--light); text-decoration: none; opacity: 0.7; transition: opacity 0.2s; }}
        .footer-links a:hover {{ opacity: 1; }}
        .footer-copy {{ opacity: 0.5; font-size: 0.875rem; }}
        
        @media (max-width: 768px) {{
            nav {{ padding: 16px 20px; }}
            .nav-links {{ display: none; }}
            .hero {{ padding: 100px 20px 60px; }}
            .hero h1 .rotating-text {{ min-width: 200px; font-size: 0.9em; }}
            .features, .demo, .cta-section {{ padding: 80px 20px; }}
        }}
    </style>
</head>
<body>
    <nav id="navbar">
        <a href="/" class="logo">Foundry</a>
        <div class="nav-links">
            <a href="#features">Features</a>
            <a href="#demo">Demo</a>
            <a href="{base_url}/docs">API Docs</a>
            <a href="{base_url}/docs" class="nav-cta">Try It Free</a>
        </div>
    </nav>

    <section class="hero">
        <div class="hero-content">
            <h1>
                <span class="static">AI Agents Building Tools</span>
                <span class="static">for <span class="rotating-wrapper"><span class="rotating-text" id="rotating-text">themselves</span></span></span>
            </h1>
            <p>Dynamic tool creation at runtime. Describe what you need, get production-ready code in seconds.</p>
            <div class="cta-buttons">
                <a href="{base_url}/docs" class="btn btn-primary">Try It Free</a>
                <a href="#demo" class="btn btn-secondary">See Demo</a>
            </div>
        </div>
    </section>

    <section class="trust">
        <p class="trust-label">Powering AI agents across industries</p>
        <div class="trust-logos">
            <div class="trust-logo">🏥 Healthcare</div>
            <div class="trust-logo">🎨 Creative</div>
            <div class="trust-logo">💰 Finance</div>
            <div class="trust-logo">🔬 Research</div>
        </div>
    </section>

    <section class="features" id="features">
        <div class="features-header">
            <h2>Tools that build themselves</h2>
            <p>Foundry gives your AI agents the power to create custom tools on demand. No pre-built integrations needed—just describe the capability and it exists.</p>
        </div>
        <div class="features-grid">
            <div class="feature-card">
                <div class="feature-icon">🤖</div>
                <h3>AI-Powered Generation</h3>
                <p>Describe what you need in plain English. GPT-5.2 generates production-ready Python tools automatically.</p>
            </div>
            <div class="feature-card">
                <div class="feature-icon">⚡</div>
                <h3>Instant Deployment</h3>
                <p>Tools are deployed and ready to invoke in under 2 seconds. No build steps, no containers to manage.</p>
            </div>
            <div class="feature-card">
                <div class="feature-icon">🔒</div>
                <h3>Secure Sandboxing</h3>
                <p>Every tool runs in an isolated sandbox with no network, filesystem, or system access. Safe by design.</p>
            </div>
            <div class="feature-card">
                <div class="feature-icon">📊</div>
                <h3>Rich Output Types</h3>
                <p>Return numbers, text, tables, or even images. Typed responses make parsing deterministic.</p>
            </div>
            <div class="feature-card">
                <div class="feature-icon">🌐</div>
                <h3>Web Search Built-in</h3>
                <p>Tools can search the web via Exa API. Give your agents access to real-time information.</p>
            </div>
            <div class="feature-card">
                <div class="feature-icon">💰</div>
                <h3>Pay Per Use</h3>
                <p>Only pay for compute time. No idle servers, no minimum fees. Scale from zero to millions.</p>
            </div>
        </div>
    </section>

    <section class="demo" id="demo">
        <div class="demo-container">
            <h2>One API call. Infinite possibilities.</h2>
            <div class="code-block">
                <div class="code-header">
                    <div class="code-dots">
                        <div class="code-dot red"></div>
                        <div class="code-dot yellow"></div>
                        <div class="code-dot green"></div>
                    </div>
                    <span class="code-title">terminal</span>
                </div>
                <pre class="code-content"><span class="comment"># Your agent needs a new capability? Just ask.</span>
curl -X POST {base_url}/v1/construct \\
  -H <span class="string">"Content-Type: application/json"</span> \\
  -d <span class="string">'{{"capability_description": "Analyze patient vitals and flag anomalies"}}'</span>

<span class="comment"># Tool is ready in ~2 seconds</span>
{{ <span class="property">"tool_id"</span>: <span class="string">"tool-abc123"</span>, <span class="property">"status"</span>: <span class="string">"ready"</span> }}

<span class="comment"># Invoke it with real data</span>
curl -X POST {base_url}/v1/tools/tool-abc123/invoke \\
  -d <span class="string">'{{"input": {{"heart_rate": 142, "bp": "180/95", "temp": 101.2}}}}'</span>

<span class="comment"># Intelligent results</span>
{{
  <span class="property">"success"</span>: true,
  <span class="property">"result"</span>: {{
    <span class="property">"anomalies"</span>: [<span class="string">"elevated heart rate"</span>, <span class="string">"high blood pressure"</span>, <span class="string">"fever"</span>],
    <span class="property">"risk_level"</span>: <span class="string">"high"</span>,
    <span class="property">"recommendation"</span>: <span class="string">"immediate attention required"</span>
  }}
}}</pre>
            </div>
        </div>
    </section>

    <section class="cta-section">
        <h2>Let your agents build what they need</h2>
        <p>No credit card required. Start creating tools in minutes.</p>
        <a href="{base_url}/docs" class="btn btn-primary">Get Started Free</a>
    </section>

    <footer>
        <div class="footer-links">
            <a href="{base_url}/docs">Documentation</a>
            <a href="{base_url}/docs">API Reference</a>
            <a href="{base_url}/health">Status</a>
        </div>
        <p class="footer-copy">© 2026 Foundry. Built on Modal.</p>
    </footer>

    <script>
        const navbar = document.getElementById('navbar');
        window.addEventListener('scroll', () => {{
            navbar.classList.toggle('scrolled', window.scrollY > 50);
        }});
        document.querySelectorAll('a[href^="#"]').forEach(anchor => {{
            anchor.addEventListener('click', function (e) {{
                e.preventDefault();
                document.querySelector(this.getAttribute('href'))?.scrollIntoView({{ behavior: 'smooth' }});
            }});
        }});
        
        // Rotating text animation
        const words = ['themselves', 'healthcare', 'creatives', 'finance', 'researchers', 'developers', 'startups', 'enterprise'];
        let currentIndex = 0;
        const rotatingText = document.getElementById('rotating-text');
        
        setInterval(() => {{
            currentIndex = (currentIndex + 1) % words.length;
            rotatingText.style.animation = 'none';
            rotatingText.offsetHeight; // Trigger reflow
            rotatingText.textContent = words[currentIndex];
            rotatingText.style.animation = 'fadeInOut 3s ease-in-out';
        }}, 3000);
    </script>
</body>
</html>'''


# =============================================================================
# Swagger/OpenAPI Configuration
# =============================================================================

def _get_api_config() -> dict:
    """Get API configuration from environment variables."""
    import os
    return {
        "title": os.environ.get("FOUNDRY_API_TITLE", "Tool Foundry API"),
        "description": os.environ.get("FOUNDRY_API_DESCRIPTION", ""),
        "version": os.environ.get("FOUNDRY_API_VERSION", "1.0.0"),
        "contact_name": os.environ.get("FOUNDRY_CONTACT_NAME", ""),
        "contact_email": os.environ.get("FOUNDRY_CONTACT_EMAIL", ""),
        "contact_url": os.environ.get("FOUNDRY_CONTACT_URL", ""),
        "logo_url": os.environ.get("FOUNDRY_LOGO_URL", ""),
        "terms_of_service": os.environ.get("FOUNDRY_TERMS_URL", ""),
    }


def _build_description(config: dict) -> str:
    """Build the API description with optional custom content."""
    custom_desc = config.get("description", "")
    
    base_description = """
## Dynamic Tool Creation & Execution Service

Tool Foundry enables AI agents to dynamically create, manage, and execute tools at runtime.

### Key Features
- **🤖 Agent-Driven Creation**: Describe a capability in natural language, get a working tool
- **📝 Direct Creation**: Provide Python code directly for full control  
- **🔒 Secure Execution**: Sandboxed execution with validated code
- **💾 Persistent Registry**: Tools survive deployments

### Quick Start

**1. Create a tool** (choose one method):

```bash
# Agent-driven (from description)
POST /v1/construct
{"capability_description": "Calculate compound interest", "org_id": "my-org", "conversation_id": "conv-1"}

# Direct (with code)
POST /v1/tools  
{"name": "add", "implementation": "def main(a, b): return a + b", ...}
```

**2. Invoke the tool:**
```bash
POST /v1/tools/{tool_id}/invoke
{"input": {"principal": 1000, "rate": 0.05, "years": 10}}
```

### Security
- Code validation via AST analysis
- Sandboxed execution (no filesystem, network, or subprocess access)
- Module allowlist enforcement
- 30s timeout, 256MB memory limit per invocation
"""
    
    if custom_desc:
        return f"{custom_desc}\n\n---\n\n{base_description}"
    return base_description


# Build OpenAPI config
_api_config = _get_api_config()

# Contact info (if provided)
_contact_info = None
if _api_config["contact_name"] or _api_config["contact_email"]:
    _contact_info = {}
    if _api_config["contact_name"]:
        _contact_info["name"] = _api_config["contact_name"]
    if _api_config["contact_email"]:
        _contact_info["email"] = _api_config["contact_email"]
    if _api_config["contact_url"]:
        _contact_info["url"] = _api_config["contact_url"]

# =============================================================================
# FastAPI App with Metadata
# =============================================================================

web_app = FastAPI(
    title=_api_config["title"],
    description=_build_description(_api_config),
    version=_api_config["version"],
    docs_url=None,  # Disable default, we'll add custom styled docs
    redoc_url=None,  # Disable default, we'll add custom styled redoc
    terms_of_service=_api_config["terms_of_service"] or None,
    contact=_contact_info,
    license_info={
        "name": "Proprietary",
    },
    openapi_tags=[
        {
            "name": "health",
            "description": "Health checks and service status",
        },
        {
            "name": "construct",
            "description": "🤖 Agent-driven tool construction from natural language descriptions",
        },
        {
            "name": "tools",
            "description": "🔧 Tool management: create, list, get, update, delete",
        },
        {
            "name": "execution",
            "description": "⚡ Tool invocation and execution",
        },
    ],
)


# =============================================================================
# CORS & Security Middleware
# =============================================================================

import os as _os

_allowed_origins = [
    origin.strip()
    for origin in _os.environ.get(
        "FOUNDRY_CORS_ORIGINS",
        # Default: allow localhost dev + Vercel + custom domain
        "http://localhost:3000,http://localhost:3001,"
        "https://foundry.ai,https://www.foundry.ai,"
        "https://*.vercel.app,"
        "https://camfleety--toolfoundry-serve.modal.run",
    ).split(",")
    if origin.strip()
]

web_app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=[
        "X-RateLimit-Limit",
        "X-RateLimit-Remaining",
        "X-RateLimit-Reset",
        "Retry-After",
    ],
)


@web_app.middleware("http")
async def security_headers(request: Request, call_next):
    """Add security headers to every response."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


# =============================================================================
# Custom Swagger UI with Branding
# =============================================================================

from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
from fastapi.responses import HTMLResponse


@web_app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    """Custom styled Swagger UI documentation."""
    logo_url = _api_config.get("logo_url", "")
    title = _api_config.get("title", "Tool Foundry API")
    
    # Clean, minimal custom CSS - keep default Swagger styling
    custom_css = """
    /* Branded header bar */
    .foundry-header {
        background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%);
        padding: 16px 24px;
        display: flex;
        align-items: center;
        gap: 16px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.15);
    }
    
    .foundry-header img {
        height: 36px;
        border-radius: 6px;
    }
    
    .foundry-header h1 {
        color: white;
        font-size: 1.25rem;
        font-weight: 600;
        margin: 0;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    }
    
    /* Hide default Swagger topbar since we have our own */
    .swagger-ui .topbar {
        display: none;
    }
    
    /* Subtle improvements to default theme */
    .swagger-ui .info .title {
        color: #1e293b;
    }
    
    .swagger-ui .opblock {
        border-radius: 8px;
        margin: 8px 0;
    }
    
    .swagger-ui .btn {
        border-radius: 6px;
    }
    
    .swagger-ui .opblock-tag {
        font-weight: 600;
    }
    """
    
    swagger_html = get_swagger_ui_html(
        openapi_url="/openapi.json",
        title=f"{title} - Documentation",
        swagger_css_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css",
        swagger_js_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js",
        swagger_favicon_url=logo_url if logo_url else "https://fastapi.tiangolo.com/img/favicon.png",
        swagger_ui_parameters={
            "deepLinking": True,
            "displayRequestDuration": True,
            "filter": True,
            "defaultModelsExpandDepth": 2,
            "docExpansion": "list",
            "persistAuthorization": True,
        },
    )
    
    # Build the header HTML
    logo_html = f'<img src="{logo_url}" alt="Logo">' if logo_url else ""
    header_html = f'<body><div class="foundry-header">{logo_html}<h1>{title}</h1></div>'
    
    html_content = swagger_html.body.decode()
    html_content = html_content.replace("</head>", f"<style>{custom_css}</style></head>")
    html_content = html_content.replace("<body>", header_html)
    
    return HTMLResponse(content=html_content)


@web_app.get("/redoc", include_in_schema=False)
async def custom_redoc_html():
    """Custom styled ReDoc documentation."""
    title = _api_config.get("title", "Tool Foundry API")
    logo_url = _api_config.get("logo_url", "")
    
    return get_redoc_html(
        openapi_url="/openapi.json",
        title=f"{title} - Documentation",
        redoc_favicon_url=logo_url if logo_url else "https://fastapi.tiangolo.com/img/favicon.png",
)


# =============================================================================
# Routers
# =============================================================================

# Health router (no version prefix, no auth required)
health_router = APIRouter(tags=["health"])

# V1 API routers — auth validated per-handler via Depends(validate_api_key)
# so we can track usage with the auth context
construct_router = APIRouter(prefix="/v1/construct", tags=["construct"])
tools_router = APIRouter(prefix="/v1/tools", tags=["tools"])
execution_router = APIRouter(prefix="/v1/tools", tags=["execution"])
builds_router = APIRouter(prefix="/v1/builds", tags=["construct"])
search_router = APIRouter(prefix="/v1/search", tags=["search"])


# =============================================================================
# Health Endpoints
# =============================================================================


@health_router.get("/", include_in_schema=False, response_class=HTMLResponse)
async def root():
    """Landing page for Tool Foundry."""
    return get_landing_page()


@health_router.get("/api", include_in_schema=False)
async def api_info():
    """API root - info endpoint."""
    return {
        "service": "Tool Foundry",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
        "api": "/v1",
    }


@health_router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Check service health and feature availability."""
    settings = get_settings()
    return HealthResponse(
        status="healthy",
        service="tool-foundry",
        version="1.0.0",
        features={
            "agent_enabled": bool(get_anthropic_api_key()),
            "sandbox_enabled": settings.enable_sandbox_execution,
            "async_builds": settings.enable_async_builds,
            "event_emission": settings.enable_event_emission,
        },
    )


@health_router.get("/v1", include_in_schema=False)
async def v1_info():
    """V1 API information."""
    return {
        "version": "v1",
        "endpoints": {
            "capabilities": "/v1/construct",
            "tools": "/v1/tools",
            "builds": "/v1/builds",
            "search": "/v1/search",
        },
    }


# =============================================================================
# Capabilities Endpoints (Agent-Driven Creation)
# =============================================================================


def get_builder_agent():
    """Get or create the builder agent."""
    from src.agent import get_builder_agent as _get_agent

    return _get_agent()


async def _build_capability_async(
    request_id: str,
    request: CreateCapabilityRequest = None,
    description: str = None,
    org_id: str = None,
    conversation_id: str = None,
    ttl_hours: int = 24,
) -> None:
    """Background task to build a capability."""
    try:
        agent = get_builder_agent()

        # Use request object or individual params
        if request:
            desc = request.capability_description
            ctx = request.context
            o_id = request.org_id
            c_id = request.conversation_id
            ttl = request.ttl_hours
        else:
            desc = description
            ctx = None
            o_id = org_id
            c_id = conversation_id
            ttl = ttl_hours

        result = await agent.build_from_description(
            capability_description=desc,
            context=ctx,
            org_id=o_id,
            conversation_id=c_id,
        )

        if not result.success:
            _build_requests[request_id]["status"] = "failed"
            _build_requests[request_id]["error"] = result.error
            return

        # Create tool entry
        tool_id = f"tool-{uuid.uuid4().hex[:12]}"
        expires_at = datetime.now(timezone.utc) + timedelta(hours=ttl)

        entry = ToolRegistryEntry(
            tool_id=tool_id,
            org_id=o_id,
            conversation_id=c_id,
            name=result.tool_name,
            description=result.tool_description,
            status=ToolStatus.READY,
            input_schema=result.input_schema,
            implementation=result.implementation,
            created_at=datetime.now(timezone.utc),
            expires_at=expires_at,
        )

        get_registry()[tool_id] = entry

        _build_requests[request_id]["status"] = "ready"
        _build_requests[request_id]["tool_id"] = tool_id

        logger.info(f"Async build complete: {request_id} -> {tool_id}")

    except Exception as e:
        logger.error(f"Async build failed: {request_id}: {e}")
        _build_requests[request_id]["status"] = "failed"
        _build_requests[request_id]["error"] = str(e)


@construct_router.post(
    "",
    response_model=CreateCapabilityResponse,
    summary="Create tool from description",
    description="Use AI to generate a tool from a natural language capability description.",
)
async def create_capability(
    request: CreateCapabilityRequest,
    background_tasks: BackgroundTasks,
    auth: Optional[AuthContext] = Depends(validate_api_key),
) -> CreateCapabilityResponse:
    """Create a tool from a capability description using the AI agent."""
    request_id = f"req-{uuid.uuid4().hex[:12]}"
    base_url = get_base_url()

    # Check usage limit if authenticated
    if auth:
        await check_usage_limit(auth, "tool_build")

    if not has_llm_provider():
        return CreateCapabilityResponse(
            request_id=request_id,
            status="failed",
            message="Agent not available: No LLM provider configured (set OPENAI_API_KEY or ANTHROPIC_API_KEY)",
        )

    settings = get_settings()
    # Use org_id from auth context if available, fall back to request
    org_id = (auth.org_id if auth else None) or request.org_id

    # Async build
    if request.async_build and settings.enable_async_builds:
        _build_requests[request_id] = {
            "status": "building",
            "tool_id": None,
            "error": None,
            "created_at": datetime.now(timezone.utc),
        }

        background_tasks.add_task(_build_capability_async, request_id, request)

        logger.info(f"Queued async build: {request_id}")
        return CreateCapabilityResponse(
            request_id=request_id,
            status="building",
            message="Build started. Poll /v1/builds/{request_id} for status.",
        )

    # Synchronous build
    start_time = time.time()
    try:
        agent = get_builder_agent()
        result = await agent.build_from_description(
            capability_description=request.capability_description,
            context=request.context,
            org_id=org_id,
            conversation_id=request.conversation_id,
        )

        elapsed_ms = int((time.time() - start_time) * 1000)

        if not result.success:
            # Track failed build
            if auth:
                background_tasks.add_task(
                    track_usage, auth, "tool_build", tool_id=None,
                    request_id=request_id, endpoint="/v1/construct",
                    status_code=200, execution_time_ms=elapsed_ms,
                    error=result.error,
                )
            return CreateCapabilityResponse(
                request_id=request_id,
                status="failed",
                message=f"Build failed: {result.error}",
            )

        tool_id = f"tool-{uuid.uuid4().hex[:12]}"
        expires_at = datetime.now(timezone.utc) + timedelta(hours=request.ttl_hours)

        entry = ToolRegistryEntry(
            tool_id=tool_id,
            org_id=org_id,
            conversation_id=request.conversation_id,
            name=result.tool_name,
            description=result.tool_description,
            status=ToolStatus.READY,
            input_schema=result.input_schema,
            implementation=result.implementation,
            created_at=datetime.now(timezone.utc),
            expires_at=expires_at,
        )

        get_registry()[tool_id] = entry
        logger.info(f"Created tool from capability: {tool_id}")

        # Track successful build
        if auth:
            background_tasks.add_task(
                track_usage, auth, "tool_build", tool_id=tool_id,
                request_id=request_id, endpoint="/v1/construct",
                status_code=200, execution_time_ms=elapsed_ms,
            )

        return CreateCapabilityResponse(
            request_id=request_id,
            tool_id=tool_id,
            status="ready",
            message="Tool created successfully",
            manifest_url=f"{base_url}/v1/tools/{tool_id}",
            invoke_url=f"{base_url}/v1/tools/{tool_id}/invoke",
        )

    except Exception as e:
        elapsed_ms = int((time.time() - start_time) * 1000)
        logger.error(f"Capability creation failed: {e}")
        if auth:
            background_tasks.add_task(
                track_usage, auth, "tool_build", tool_id=None,
                request_id=request_id, endpoint="/v1/construct",
                status_code=500, execution_time_ms=elapsed_ms,
                error=str(e),
            )
        return CreateCapabilityResponse(
            request_id=request_id,
            status="failed",
            message=f"Build failed: {str(e)}",
        )


# =============================================================================
# Build Status Endpoints
# =============================================================================


@builds_router.get(
    "/{request_id}",
    response_model=BuildStatusResponse,
    summary="Check build status",
    description="Check the status of an async build request.",
)
async def get_build_status(request_id: str) -> BuildStatusResponse:
    """Check the status of an async build request."""
    if request_id not in _build_requests:
        raise HTTPException(status_code=404, detail=f"Build request {request_id} not found")

    build = _build_requests[request_id]
    return BuildStatusResponse(
        request_id=request_id,
        tool_id=build.get("tool_id"),
        status=build["status"],
        error=build.get("error"),
        created_at=build.get("created_at"),
    )


# =============================================================================
# Tools Management Endpoints
# =============================================================================


@tools_router.post(
    "",
    response_model=CreateToolResponse,
    summary="Create tool with code",
    description="Create a tool by providing Python implementation directly.",
)
async def create_tool(
    request: CreateToolRequest,
    background_tasks: BackgroundTasks,
    auth: Optional[AuthContext] = Depends(validate_api_key),
) -> CreateToolResponse:
    """Create a tool by providing Python implementation directly."""
    tool_id = f"tool-{uuid.uuid4().hex[:12]}"
    base_url = get_base_url()
    org_id = (auth.org_id if auth else None) or request.org_id

    # Validate the implementation
    try:
        validate_restricted_python(request.implementation)
    except Exception as e:
        return CreateToolResponse(
            tool_id=tool_id,
            status=ToolStatus.FAILED,
            manifest_url=f"{base_url}/v1/tools/{tool_id}",
            invoke_url=f"{base_url}/v1/tools/{tool_id}/invoke",
            message=f"Validation failed: {str(e)}",
        )

    # Create registry entry
    expires_at = datetime.now(timezone.utc) + timedelta(hours=request.ttl_hours)
    entry = ToolRegistryEntry(
        tool_id=tool_id,
        org_id=org_id,
        conversation_id=request.conversation_id,
        name=request.name,
        description=request.description,
        status=ToolStatus.READY,
        input_schema=request.input_schema,
        implementation=request.implementation,
        created_at=datetime.now(timezone.utc),
        expires_at=expires_at,
    )

    get_registry()[tool_id] = entry
    logger.info(f"Created tool {tool_id}: {request.name}")

    # Track usage
    if auth:
        background_tasks.add_task(
            track_usage, auth, "tool_build", tool_id=tool_id,
            endpoint="/v1/tools", status_code=200,
        )

    return CreateToolResponse(
        tool_id=tool_id,
        status=ToolStatus.READY,
        manifest_url=f"{base_url}/v1/tools/{tool_id}",
        invoke_url=f"{base_url}/v1/tools/{tool_id}/invoke",
        message="Tool created successfully",
    )


@tools_router.get(
    "",
    summary="List tools",
    description="List all tools, optionally filtered by organization.",
)
async def list_tools(
    org_id: Optional[str] = None,
    auth: Optional[AuthContext] = Depends(validate_api_key),
) -> Dict[str, List[ToolManifest]]:
    """List all tools, optionally filtered by org_id."""
    base_url = get_base_url()
    tools = []
    # Use org from auth if available and no explicit filter
    filter_org = org_id or (auth.org_id if auth else None)

    for entry in get_registry().values():
        if filter_org and entry.org_id != filter_org:
            continue

        if entry.expires_at and datetime.now(timezone.utc) > entry.expires_at:
            entry.status = ToolStatus.EXPIRED
            get_registry()[entry.tool_id] = entry

        tools.append(
            ToolManifest(
                tool_id=entry.tool_id,
                name=entry.name,
                description=entry.description,
                status=entry.status,
                input_schema=entry.input_schema,
                output_schema=entry.output_schema,
                invoke_url=f"{base_url}/v1/tools/{entry.tool_id}/invoke",
                created_at=entry.created_at,
                expires_at=entry.expires_at,
            )
        )
    return {"tools": tools}


@tools_router.get(
    "/{tool_id}",
    response_model=ToolManifest,
    summary="Get tool manifest",
    description="Get the manifest/schema for a specific tool.",
)
async def get_tool(tool_id: str) -> ToolManifest:
    """Get the manifest for a specific tool."""
    entry = get_registry().get(tool_id)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Tool {tool_id} not found")

    base_url = get_base_url()
    return ToolManifest(
        tool_id=entry.tool_id,
        name=entry.name,
        description=entry.description,
        status=entry.status,
        input_schema=entry.input_schema,
        output_schema=entry.output_schema,
        invoke_url=f"{base_url}/v1/tools/{entry.tool_id}/invoke",
        created_at=entry.created_at,
        expires_at=entry.expires_at,
    )


@tools_router.delete(
    "/{tool_id}",
    summary="Delete tool",
    description="Permanently delete a tool from the registry.",
)
async def delete_tool(tool_id: str) -> Dict[str, str]:
    """Delete a tool from the registry."""
    if tool_id not in get_registry():
        raise HTTPException(status_code=404, detail=f"Tool {tool_id} not found")

    del get_registry()[tool_id]
    logger.info(f"Deleted tool {tool_id}")
    return {"status": "deleted", "tool_id": tool_id}


@tools_router.post(
    "/{tool_id}/deprecate",
    summary="Deprecate tool",
    description="Mark a tool as deprecated (soft delete).",
)
async def deprecate_tool(tool_id: str, request: DeprecateToolRequest) -> Dict[str, Any]:
    """Deprecate a tool (soft delete)."""
    entry = get_registry().get(tool_id)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Tool {tool_id} not found")

    entry.status = ToolStatus.DEPRECATED
    if request.reason:
        entry.error_message = f"Deprecated: {request.reason}"

    get_registry()[tool_id] = entry
    logger.info(f"Deprecated tool {tool_id}: {request.reason or 'No reason given'}")

    response: Dict[str, Any] = {
        "status": "deprecated",
        "tool_id": tool_id,
        "message": request.reason or "Tool deprecated",
    }
    if request.replacement_tool_id:
        response["replacement_tool_id"] = request.replacement_tool_id

    return response


@tools_router.post(
    "/{tool_id}/rebuild",
    response_model=RebuildToolResponse,
    summary="Rebuild tool",
    description="Rebuild a tool with new instructions or fix a broken tool.",
)
async def rebuild_tool(
    tool_id: str,
    request: RebuildToolRequest,
    background_tasks: BackgroundTasks,
) -> RebuildToolResponse:
    """Rebuild a tool with new instructions or fix a broken tool."""
    entry = get_registry().get(tool_id)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Tool {tool_id} not found")

    if request.capability_description:
        description = request.capability_description
    elif request.fix_instructions:
        description = f"Fix the following tool: {entry.description}. Issues to fix: {request.fix_instructions}. Previous implementation had status: {entry.status}"
        if entry.error_message:
            description += f". Error was: {entry.error_message}"
    else:
        raise HTTPException(
            status_code=400,
            detail="Must provide either capability_description or fix_instructions",
        )

    base_url = get_base_url()

    # Mark old tool as deprecated
    entry.status = ToolStatus.DEPRECATED
    get_registry()[tool_id] = entry

    if request.async_build:
        request_id = f"rebuild-{secrets.token_hex(6)}"
        _build_requests[request_id] = {
            "status": "building",
            "tool_id": None,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "previous_tool_id": tool_id,
        }

        background_tasks.add_task(
            _build_capability_async,
            request_id=request_id,
            description=description,
            org_id=entry.org_id,
            conversation_id=entry.conversation_id,
            ttl_hours=24,
        )

        logger.info(f"Started rebuild for tool {tool_id}, request {request_id}")
        return RebuildToolResponse(
            tool_id=tool_id,
            previous_version=tool_id,
            status="rebuilding",
            message=f"Rebuild started. Check status at /v1/builds/{request_id}",
        )
    else:
        try:
            from src.agent import get_builder_agent

            agent = get_builder_agent()
            result = await agent.build_from_description(description)

            if not result.success:
                raise HTTPException(
                    status_code=500,
                    detail=f"Rebuild failed: {result.error or 'Unknown error'}",
                )

            new_tool_id = f"tool-{secrets.token_hex(6)}"
            new_entry = ToolRegistryEntry(
                tool_id=new_tool_id,
                org_id=entry.org_id,
                conversation_id=entry.conversation_id,
                name=result.tool_name or "rebuilt_tool",
                description=result.tool_description or description[:100],
                status=ToolStatus.READY,
                input_schema=result.input_schema or {"type": "object"},
                implementation=result.implementation,
                created_at=datetime.now(timezone.utc),
                expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
            )
            get_registry()[new_tool_id] = new_entry

            logger.info(f"Rebuilt tool {tool_id} as {new_tool_id}")
            return RebuildToolResponse(
                tool_id=new_tool_id,
                previous_version=tool_id,
                status="ready",
                message="Tool rebuilt successfully",
                manifest_url=f"{base_url}/v1/tools/{new_tool_id}",
                invoke_url=f"{base_url}/v1/tools/{new_tool_id}/invoke",
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Rebuild failed for {tool_id}: {e}")
            raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Execution Endpoints
# =============================================================================


@execution_router.post(
    "/{tool_id}/invoke",
    response_model=InvokeResponse,
    summary="Invoke tool",
    description="Execute a tool with the provided input. Any secrets configured for this tool via PUT /v1/tools/{tool_id}/secrets are automatically injected as environment variables.",
)
async def invoke_tool(
    tool_id: str,
    request: InvokeRequest,
    background_tasks: BackgroundTasks,
    auth: Optional[AuthContext] = Depends(validate_api_key),
) -> InvokeResponse:
    """Execute a tool with the provided input."""
    from src.api.schemas import ResultType, TypedResult

    entry = get_registry().get(tool_id)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Tool {tool_id} not found")

    if entry.status == ToolStatus.EXPIRED:
        raise HTTPException(status_code=410, detail=f"Tool {tool_id} has expired")

    if entry.status == ToolStatus.DEPRECATED:
        raise HTTPException(status_code=410, detail=f"Tool {tool_id} is deprecated")

    if entry.status != ToolStatus.READY:
        raise HTTPException(
            status_code=400,
            detail=f"Tool {tool_id} is not ready (status: {entry.status})",
        )

    # Check usage limit if authenticated
    if auth:
        await check_usage_limit(auth, "tool_invoke")

    logger.info(f"Invoking tool {tool_id}")

    # Fetch user-configured secrets for this tool
    extra_env = {}
    try:
        from src.api.secrets import get_tool_secrets_decrypted
        org_id = (auth.org_id if auth else None) or getattr(entry, "org_id", None) or "default"
        extra_env = await get_tool_secrets_decrypted(tool_id, org_id)
        if extra_env:
            logger.info(f"Injecting {len(extra_env)} secret(s) for tool {tool_id}")
    except Exception as e:
        logger.warning(f"Failed to fetch secrets for tool {tool_id}: {e}")

    try:
        from src.builder.sandbox import get_executor

        executor = get_executor()
        exec_result = executor.execute(
            implementation=entry.implementation,
            input_data=request.input,
            timeout_seconds=30,
            extra_env=extra_env if extra_env else None,
        )

        if not exec_result.success:
            logger.warning(f"Tool {tool_id} execution failed: {exec_result.error}")
            if auth:
                background_tasks.add_task(
                    track_usage, auth, "tool_invoke", tool_id=tool_id,
                    endpoint=f"/v1/tools/{tool_id}/invoke", status_code=200,
                    execution_time_ms=exec_result.execution_time_ms,
                    error=exec_result.error,
                )
            return InvokeResponse(
                success=False,
                result_type=None,
                result=TypedResult(),
                raw_result=None,
                error=exec_result.error,
                execution_time_ms=exec_result.execution_time_ms,
            )

        # Classify and wrap the result in typed envelope
        raw = exec_result.result
        result_type, typed_result = _classify_result(raw)

        # Track successful invocation
        if auth:
            background_tasks.add_task(
                track_usage, auth, "tool_invoke", tool_id=tool_id,
                endpoint=f"/v1/tools/{tool_id}/invoke", status_code=200,
                execution_time_ms=exec_result.execution_time_ms,
            )

        return InvokeResponse(
            success=True,
            result_type=result_type,
            result=typed_result,
            raw_result=raw,
            error=None,
            execution_time_ms=exec_result.execution_time_ms,
        )

    except Exception as e:
        logger.error(f"Tool {tool_id} invocation error: {e}")
        if auth:
            background_tasks.add_task(
                track_usage, auth, "tool_invoke", tool_id=tool_id,
                endpoint=f"/v1/tools/{tool_id}/invoke", status_code=500,
                error=str(e),
            )
        return InvokeResponse(
            success=False,
            result_type=None,
            result=TypedResult(),
            raw_result=None,
            error=str(e),
            execution_time_ms=0,
        )


def _classify_result(raw: Any) -> tuple:
    """Classify raw result into typed envelope."""
    from src.api.schemas import ResultType, TypedResult

    # Check for base64 image (string starting with image markers or long base64)
    if isinstance(raw, str):
        # Check if it looks like base64 image data
        if (
            raw.startswith("iVBOR")  # PNG
            or raw.startswith("/9j/")  # JPEG
            or raw.startswith("R0lGOD")  # GIF
            or (len(raw) > 1000 and raw.replace("+", "").replace("/", "").replace("=", "").isalnum())
        ):
            return ResultType.IMAGE, TypedResult(image_base64=raw)
        # Regular text
        return ResultType.TEXT, TypedResult(text=raw)

    # Check for number
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        return ResultType.NUMBER, TypedResult(number=float(raw))

    # Check for table (list of dicts)
    if isinstance(raw, list) and len(raw) > 0 and isinstance(raw[0], dict):
        return ResultType.TABLE, TypedResult(table=raw)

    # Check for dict with image_base64 key (common pattern)
    if isinstance(raw, dict):
        if "image_base64" in raw or "image" in raw:
            img = raw.get("image_base64") or raw.get("image")
            if isinstance(img, str):
                return ResultType.IMAGE, TypedResult(image_base64=img)
        # Regular object
        return ResultType.OBJECT, TypedResult(object=raw)

    # Fallback - convert to object
    return ResultType.OBJECT, TypedResult(object={"value": raw})


# Legacy endpoint for backward compatibility
@execution_router.post(
    "/{tool_id}:invoke",
    response_model=InvokeResponse,
    include_in_schema=False,  # Hide from docs, keep for compatibility
)
async def invoke_tool_legacy(
    tool_id: str,
    request: InvokeRequest,
    background_tasks: BackgroundTasks,
    auth: Optional[AuthContext] = Depends(validate_api_key),
) -> InvokeResponse:
    """Legacy invoke endpoint (use /invoke instead)."""
    return await invoke_tool(tool_id, request, background_tasks, auth)


# Legacy manifest endpoint
@tools_router.get(
    "/{tool_id}/manifest",
    response_model=ToolManifest,
    include_in_schema=False,
)
async def get_manifest_legacy(tool_id: str) -> ToolManifest:
    """Legacy manifest endpoint (use GET /v1/tools/{id} instead)."""
    return await get_tool(tool_id)


# =============================================================================
# Search Endpoints
# =============================================================================

QUERY_EXPANSION_PROMPT = """You are a search query expansion assistant. Given a user's question, generate {num_queries} distinct search queries that together would help comprehensively answer the question.

Rules:
1. Each query should approach the topic from a different angle
2. Include queries for: definitions, how-to, requirements, examples, alternatives
3. Keep each query concise (under 80 characters)
4. Make queries specific and searchable
5. Output ONLY a JSON array of strings, nothing else

Example for "how do I register to vote":
["voter registration requirements by state", "online voter registration process steps", "voter registration deadlines 2026", "documents needed to register to vote", "check voter registration status online"]

Example for "best way to learn python":
["Python beginner tutorial roadmap", "Python learning resources for beginners", "Python programming exercises practice", "Python projects for beginners portfolio", "Python certification courses online"]
"""


async def generate_search_queries(query: str, num_queries: int) -> list[str]:
    """Use GPT-4o-mini to generate multiple related search queries."""
    import os
    import httpx
    import json

    openai_api_key = os.environ.get("OPENAI_API_KEY")
    if not openai_api_key:
        logger.warning("OpenAI API key not configured, using original query only")
        return [query]

    try:
        prompt = QUERY_EXPANSION_PROMPT.format(num_queries=num_queries)
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {openai_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "gpt-4o-mini",
                    "messages": [
                        {"role": "system", "content": prompt},
                        {"role": "user", "content": query},
                    ],
                    "max_tokens": 500,
                    "temperature": 0.7,
                },
            )
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"].strip()
            
            # Parse JSON array from response
            queries = json.loads(content)
            if isinstance(queries, list) and len(queries) > 0:
                logger.info(f"Generated {len(queries)} queries from: '{query}'")
                return queries[:num_queries]
            
    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse query expansion response: {e}")
    except Exception as e:
        logger.warning(f"Query expansion failed: {e}")
    
    # Fallback to original query
    return [query]


async def search_brave(query: str, num_results: int = 10) -> list[dict]:
    """Search using Brave Search API (free tier: 2000 queries/month)."""
    import os
    import httpx
    
    results = []
    brave_api_key = os.environ.get("BRAVE_API_KEY")
    
    if not brave_api_key:
        logger.warning("Brave API key not configured, falling back to DuckDuckGo")
        return await search_duckduckgo_fallback(query, num_results)
    
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                "https://api.search.brave.com/res/v1/web/search",
                headers={
                    "Accept": "application/json",
                    "X-Subscription-Token": brave_api_key,
                },
                params={
                    "q": query,
                    "count": num_results,
                    "safesearch": "moderate",
                },
            )
            response.raise_for_status()
            data = response.json()
        
        web_results = data.get("web", {}).get("results", [])
        for i, item in enumerate(web_results):
            results.append({
                "url": item.get("url", ""),
                "title": item.get("title", ""),
                "text": item.get("description", ""),
                "score": 1.0 - (i * 0.03),
            })
        
        logger.info(f"Brave Search returned {len(results)} results for: '{query}'")
        
    except Exception as e:
        logger.warning(f"Brave Search failed for '{query}': {e}")
        # Fallback to DuckDuckGo
        return await search_duckduckgo_fallback(query, num_results)
    
    return results


async def search_duckduckgo_fallback(query: str, num_results: int = 10) -> list[dict]:
    """Fallback search using DuckDuckGo library.
    
    NOTE: DuckDuckGo and Google scraping often fail from cloud IPs.
    If all providers fail, we return an empty list with a log warning
    instead of silently returning nothing.
    """
    import asyncio
    
    results = []
    
    try:
        def _search():
            from duckduckgo_search import DDGS
            with DDGS() as ddgs:
                return list(ddgs.text(query, max_results=num_results))
        
        loop = asyncio.get_event_loop()
        ddg_results = await loop.run_in_executor(None, _search)
        
        for i, item in enumerate(ddg_results):
            results.append({
                "url": item.get("href", ""),
                "title": item.get("title", ""),
                "text": item.get("body", ""),
                "score": 1.0 - (i * 0.03),
            })
        
        logger.info(f"DuckDuckGo returned {len(results)} results for: '{query}'")
        
    except Exception as e:
        logger.warning(f"DuckDuckGo search failed for '{query}': {e}")
        # Try Google scraping as last resort
        results = await scrape_google(query, num_results)
    
    if not results:
        logger.warning(
            f"All search providers returned 0 results for '{query}'. "
            "This may be caused by search engines blocking cloud IPs. "
            "Configure a valid BRAVE_API_KEY for reliable results."
        )
    
    return results


async def scrape_google(query: str, num_results: int = 10) -> list[dict]:
    """Scrape Google search results using BeautifulSoup."""
    import httpx
    from urllib.parse import quote_plus, urlparse, parse_qs
    
    results = []
    
    try:
        from bs4 import BeautifulSoup
        
        search_url = f"https://www.google.com/search?q={quote_plus(query)}&num={num_results}"
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate",
            "DNT": "1",
        }
        
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            response = await client.get(search_url, headers=headers)
            response.raise_for_status()
            html = response.text
        
        soup = BeautifulSoup(html, "lxml")
        
        # Find search result divs
        for i, div in enumerate(soup.select("div.g")[:num_results]):
            try:
                # Find the link
                link = div.select_one("a[href]")
                if not link:
                    continue
                    
                url = link.get("href", "")
                
                # Skip Google internal links
                if not url or url.startswith("/") or "google.com" in url:
                    continue
                
                # Find title
                title_elem = div.select_one("h3")
                title = title_elem.get_text(strip=True) if title_elem else ""
                
                # Find snippet
                snippet_elem = div.select_one("div[data-sncf], div.VwiC3b, span.aCOpRe")
                snippet = snippet_elem.get_text(strip=True) if snippet_elem else ""
                
                if url and title:
                    results.append({
                        "url": url,
                        "title": title,
                        "text": snippet,
                        "score": 1.0 - (i * 0.03),
                    })
                    
            except Exception as e:
                logger.debug(f"Error parsing Google result: {e}")
                continue
        
        logger.info(f"Google scraper returned {len(results)} results for: '{query}'")
        
    except Exception as e:
        logger.warning(f"Google scraping failed for '{query}': {e}")
    
    return results


async def fetch_page_content(url: str, max_chars: int = 2000) -> str | None:
    """Fetch and extract text content from a URL using BeautifulSoup."""
    import httpx

    try:
        from bs4 import BeautifulSoup
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }
        
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            html = response.text
        
        # Parse with BeautifulSoup
        soup = BeautifulSoup(html, "lxml")
        
        # Remove unwanted elements
        for tag in soup.find_all(["script", "style", "nav", "footer", "header", "aside", "noscript", "iframe"]):
            tag.decompose()
        
        # Try to find main content areas
        main_content = None
        for selector in ["article", "main", '[role="main"]', ".content", "#content", ".post", ".article"]:
            main_content = soup.select_one(selector)
            if main_content:
                break
        
        # Use main content if found, otherwise use body
        if main_content:
            text = main_content.get_text(separator=" ", strip=True)
        else:
            body = soup.find("body")
            text = body.get_text(separator=" ", strip=True) if body else soup.get_text(separator=" ", strip=True)
        
        # Clean up whitespace
        import re
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Truncate to max_chars
        if len(text) > max_chars:
            text = text[:max_chars] + "..."
        
        return text if text else None
        
    except Exception as e:
        logger.debug(f"Failed to fetch content from {url}: {e}")
        return None


async def run_single_search(
    query: str,
    num_results: int,
    fetch_content: bool = False,
    max_content_chars: int = 500,
) -> list[dict]:
    """Run a single web search and return results."""
    import asyncio

    results = await search_brave(query, num_results)
    
    # Optionally fetch content from each result
    if fetch_content and results:
        async def fetch_for_result(result: dict) -> dict:
            content = await fetch_page_content(result["url"], max_content_chars)
            if content:
                result["text"] = content
            return result
        
        # Fetch content in parallel (limit concurrency)
        tasks = [fetch_for_result(r) for r in results[:5]]  # Limit to 5 for speed
        results[:5] = await asyncio.gather(*tasks)
    
    return results


@search_router.post(
    "",
    response_model=SearchResponse,
    summary="Search the web",
    description="""Search the web using DuckDuckGo scraping with GPT-4o-mini query expansion.

Set `num_searches` to control how many related queries are generated:
- 1: Single optimized query (fast)
- 3-5: Multiple angles for better coverage (recommended)
- 5-10: Comprehensive research mode (thorough)

Set `contents` to fetch and extract text from result pages:
- `{"text": {"max_characters": 500}}` - Extract up to 500 chars from each result

Results are deduplicated by URL and sorted by relevance score.""",
)
async def search_web(
    request: SearchRequest,
    background_tasks: BackgroundTasks,
    auth: Optional[AuthContext] = Depends(validate_api_key),
) -> SearchResponse:
    """Search the web with multi-query expansion for comprehensive results."""
    import asyncio

    # Check usage limit if authenticated
    if auth:
        await check_usage_limit(auth, "search")

    start_time = time.time()

    try:
        # Generate search queries
        if request.optimize_query and request.num_searches > 1:
            # Multi-query mode: generate related queries
            search_queries = await generate_search_queries(request.query, request.num_searches)
        elif request.optimize_query:
            # Single query mode: just expand to one good query
            search_queries = await generate_search_queries(request.query, 1)
        else:
            # No optimization: use original query
            search_queries = [request.query]

        logger.info(f"Searching with {len(search_queries)} queries: {search_queries}")

        # Determine if we should fetch content
        fetch_content = False
        max_content_chars = 500
        if request.contents and isinstance(request.contents, dict):
            text_config = request.contents.get("text", {})
            if text_config:
                fetch_content = True
                max_content_chars = text_config.get("max_characters", 500)

        # Run all searches in parallel
        search_tasks = [
            run_single_search(
                query=q,
                num_results=request.num_results,
                fetch_content=fetch_content,
                max_content_chars=max_content_chars,
            )
            for q in search_queries
        ]
        
        all_results = await asyncio.gather(*search_tasks)

        # Flatten and deduplicate results by URL
        seen_urls = set()
        unique_results = []
        
        for result_list in all_results:
            for item in result_list:
                url = item.get("url", "")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    unique_results.append(item)

        # Sort by score (highest first)
        unique_results.sort(key=lambda x: x.get("score", 0), reverse=True)

        # Convert to SearchResult objects
        results = [
            SearchResult(
                title=item.get("title", ""),
                url=item.get("url", ""),
                text=item.get("text"),
                score=item.get("score"),
                published_date=item.get("published_date"),
                author=item.get("author"),
            )
            for item in unique_results
        ]

        elapsed_ms = int((time.time() - start_time) * 1000)

        # Track search usage
        if auth:
            background_tasks.add_task(
                track_usage, auth, "search",
                endpoint="/v1/search", status_code=200,
                execution_time_ms=elapsed_ms,
            )

        # Warn the caller if we got no results (likely cloud IP blocking)
        search_error = None
        if len(results) == 0:
            search_error = (
                "No results found. If running on cloud infrastructure, search engines "
                "may be blocking requests. Ensure a valid BRAVE_API_KEY is configured."
            )

        return SearchResponse(
            success=len(results) > 0,
            query=request.query,
            generated_queries=search_queries if len(search_queries) > 1 else None,
            results=results,
            num_results=len(results),
            num_searches_performed=len(search_queries),
            error=search_error,
        )

    except Exception as e:
        elapsed_ms = int((time.time() - start_time) * 1000)
        logger.error(f"Search error: {e}")
        if auth:
            background_tasks.add_task(
                track_usage, auth, "search",
                endpoint="/v1/search", status_code=500,
                execution_time_ms=elapsed_ms, error=str(e),
            )
        return SearchResponse(
            success=False,
            query=request.query,
            results=[],
            num_results=0,
            num_searches_performed=0,
            error=str(e),
        )


# =============================================================================
# Register Routers
# =============================================================================

web_app.include_router(health_router)
web_app.include_router(construct_router)
web_app.include_router(builds_router)
web_app.include_router(tools_router)
web_app.include_router(execution_router)
web_app.include_router(search_router)

# Auth, keys, usage, and secrets routers
from src.api.keys import keys_router
from src.api.usage import usage_router
from src.api.secrets import secrets_router
web_app.include_router(keys_router)
web_app.include_router(usage_router)
web_app.include_router(secrets_router)


# =============================================================================
# Legacy Exports for Tests
# =============================================================================

def get_registry_instance():
    """Get the registry instance (for tests)."""
    return get_registry()
