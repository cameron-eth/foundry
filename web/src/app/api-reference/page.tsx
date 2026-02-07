"use client";

import Navigation from "@/components/Navigation";
import Footer from "@/components/Footer";
import { motion } from "framer-motion";
import { useState } from "react";

const API_URL = "https://camfleety--toolfoundry-serve.modal.run";

interface Endpoint {
  method: "GET" | "POST" | "DELETE";
  path: string;
  summary: string;
  description: string;
  auth: boolean;
  tag: string;
  request?: {
    headers?: Record<string, string>;
    body?: string;
  };
  response?: string;
}

const endpoints: Endpoint[] = [
  // Health
  {
    method: "GET",
    path: "/health",
    summary: "Health check",
    description: "Returns service health status and available features.",
    auth: false,
    tag: "Health",
    response: `{
  "status": "healthy",
  "service": "tool-foundry",
  "version": "1.0.0",
  "features": {
    "agent_enabled": true,
    "sandbox_enabled": true,
    "async_builds": true
  }
}`,
  },
  // Construct
  {
    method: "POST",
    path: "/v1/construct",
    summary: "Build tool from description",
    description:
      "Describe a capability in plain English. The AI agent generates a production-ready Python tool, validates it, and deploys it instantly.",
    auth: true,
    tag: "Construct",
    request: {
      body: `{
  "capability_description": "Calculate compound interest given principal, rate, and years",
  "org_id": "my-org",
  "conversation_id": "conv-123",
  "async_build": false
}`,
    },
    response: `{
  "request_id": "req-099ae401e73a",
  "tool_id": "tool-06052bf749b3",
  "status": "ready",
  "message": "Tool created successfully",
  "manifest_url": "${API_URL}/v1/tools/tool-06052bf749b3",
  "invoke_url": "${API_URL}/v1/tools/tool-06052bf749b3/invoke"
}`,
  },
  {
    method: "GET",
    path: "/v1/builds/{request_id}",
    summary: "Check build status",
    description:
      "Check the status of an async build request. Use this when you set async_build: true in the construct request.",
    auth: true,
    tag: "Construct",
    response: `{
  "request_id": "req-099ae401e73a",
  "status": "ready",
  "tool_id": "tool-06052bf749b3",
  "message": "Build complete"
}`,
  },
  // Tools
  {
    method: "POST",
    path: "/v1/tools",
    summary: "Create tool with code",
    description:
      "Create a tool by providing Python implementation directly. Useful when you want full control over the tool code.",
    auth: true,
    tag: "Tools",
    request: {
      body: `{
  "name": "add_numbers",
  "description": "Add two numbers together",
  "org_id": "my-org",
  "conversation_id": "conv-123",
  "implementation": "def main(a: float, b: float):\\n    return a + b",
  "input_schema": {
    "type": "object",
    "properties": {
      "a": { "type": "number" },
      "b": { "type": "number" }
    },
    "required": ["a", "b"]
  }
}`,
    },
    response: `{
  "tool_id": "tool-abc123",
  "status": "ready",
  "manifest_url": "${API_URL}/v1/tools/tool-abc123",
  "invoke_url": "${API_URL}/v1/tools/tool-abc123/invoke",
  "message": "Tool created successfully"
}`,
  },
  {
    method: "GET",
    path: "/v1/tools",
    summary: "List tools",
    description: "List all tools, optionally filtered by organization or conversation.",
    auth: true,
    tag: "Tools",
    response: `[
  {
    "tool_id": "tool-abc123",
    "name": "add_numbers",
    "description": "Add two numbers",
    "status": "ready",
    "created_at": "2026-02-07T20:00:00Z"
  }
]`,
  },
  {
    method: "GET",
    path: "/v1/tools/{tool_id}",
    summary: "Get tool manifest",
    description:
      "Returns the full tool manifest including name, description, input schema, and metadata.",
    auth: false,
    tag: "Tools",
    response: `{
  "tool_id": "tool-06052bf749b3",
  "name": "calculate_compound_interest",
  "description": "Calculate compound interest...",
  "input_schema": {
    "type": "object",
    "properties": {
      "principal": { "type": "number" },
      "annual_rate": { "type": "number" },
      "years": { "type": "number" }
    },
    "required": ["principal", "annual_rate", "years"]
  },
  "status": "ready"
}`,
  },
  {
    method: "POST",
    path: "/v1/tools/{tool_id}/rebuild",
    summary: "Rebuild tool",
    description:
      "Rebuild an existing tool with new instructions or fix a broken tool. Keeps the same tool_id.",
    auth: true,
    tag: "Tools",
    request: {
      body: `{
  "instructions": "Add support for monthly compounding",
  "fix_error": false
}`,
    },
    response: `{
  "tool_id": "tool-06052bf749b3",
  "status": "ready",
  "message": "Tool rebuilt successfully"
}`,
  },
  // Execution
  {
    method: "POST",
    path: "/v1/tools/{tool_id}/invoke",
    summary: "Invoke tool",
    description:
      "Execute a tool with the provided input. The tool runs in a secure sandbox with a 30-second timeout.",
    auth: true,
    tag: "Execution",
    request: {
      body: `{
  "input": {
    "principal": 10000,
    "annual_rate": 0.05,
    "years": 10
  }
}`,
    },
    response: `{
  "success": true,
  "result_type": "object",
  "result": {
    "object": {
      "final_amount": 16288.95,
      "interest_earned": 6288.95
    }
  },
  "raw_result": { "final_amount": 16288.95, "interest_earned": 6288.95 },
  "error": null,
  "execution_time_ms": 2022
}`,
  },
  // Search
  {
    method: "POST",
    path: "/v1/search",
    summary: "Web search",
    description:
      "Search the web with AI-optimized queries. Generates multiple related searches from a single query for comprehensive results.",
    auth: true,
    tag: "Search",
    request: {
      body: `{
  "query": "How does compound interest work?",
  "num_results": 5,
  "num_searches": 3,
  "optimize_query": true
}`,
    },
    response: `{
  "success": true,
  "query": "How does compound interest work?",
  "optimized_query": "compound interest formula explanation",
  "generated_queries": [
    "compound interest formula explanation",
    "compound vs simple interest difference",
    "compound interest calculator examples"
  ],
  "results": [ ... ],
  "num_results": 15,
  "num_searches_performed": 3
}`,
  },
  // API Keys
  {
    method: "POST",
    path: "/v1/keys/create",
    summary: "Create API key",
    description:
      "Generate a new API key for your organization. The full key is only shown once — store it securely.",
    auth: true,
    tag: "API Keys",
    request: {
      body: `{
  "name": "Production Key",
  "scopes": ["tools:create", "tools:invoke", "tools:read", "search"]
}`,
    },
    response: `{
  "key": "fnd_a1b2c3d4e5f6...",
  "key_id": "uuid",
  "prefix": "fnd_a1b2c3d4",
  "name": "Production Key"
}`,
  },
  {
    method: "GET",
    path: "/v1/keys/list",
    summary: "List API keys",
    description: "List all API keys for the authenticated organization.",
    auth: true,
    tag: "API Keys",
    response: `{
  "keys": [
    {
      "key_id": "uuid",
      "name": "Production Key",
      "prefix": "fnd_a1b2c3d4",
      "scopes": ["tools:create", "tools:invoke"],
      "is_active": true,
      "created_at": "2026-02-07T20:00:00Z",
      "last_used_at": "2026-02-07T21:30:00Z"
    }
  ]
}`,
  },
  {
    method: "POST",
    path: "/v1/keys/{key_id}/revoke",
    summary: "Revoke API key",
    description: "Permanently revoke an API key. This action cannot be undone.",
    auth: true,
    tag: "API Keys",
    response: `{
  "message": "API key revoked",
  "key_id": "uuid"
}`,
  },
  // Usage
  {
    method: "GET",
    path: "/v1/usage/current",
    summary: "Current usage",
    description: "Get current month usage stats for your organization.",
    auth: true,
    tag: "Usage",
    response: `{
  "builds": 42,
  "invocations": 580,
  "searches": 120,
  "builds_limit": 1000,
  "invocations_limit": 25000,
  "searches_limit": 5000,
  "plan": "pro"
}`,
  },
  {
    method: "GET",
    path: "/v1/usage/detailed",
    summary: "Detailed usage",
    description: "Get detailed usage stats with recent events and cost estimates.",
    auth: true,
    tag: "Usage",
    response: `{
  "stats": { "builds": 42, "invocations": 580, ... },
  "recent_events": [
    {
      "event_type": "tool_invoke",
      "tool_id": "tool-abc123",
      "execution_time_ms": 1500,
      "tokens_used": 0,
      "created_at": "2026-02-07T21:30:00Z"
    }
  ],
  "estimated_cost_usd": 12.50
}`,
  },
  {
    method: "GET",
    path: "/v1/usage/plans",
    summary: "Billing plans",
    description: "Get available billing plans and your current plan.",
    auth: true,
    tag: "Usage",
    response: `{
  "plans": [
    { "id": "free", "name": "Free", "price_monthly_usd": 0, "monthly_builds": 100 },
    { "id": "pro", "name": "Pro", "price_monthly_usd": 49, "monthly_builds": 1000 },
    { "id": "scale", "name": "Scale", "price_monthly_usd": 199, "monthly_builds": 10000 }
  ],
  "current_plan": "pro"
}`,
  },
];

const tags = ["Health", "Construct", "Tools", "Execution", "Search", "API Keys", "Usage"];

const methodColors: Record<string, { bg: string; text: string; border: string }> = {
  GET: { bg: "bg-emerald-500/10", text: "text-emerald-400", border: "border-emerald-500/20" },
  POST: { bg: "bg-blue-500/10", text: "text-blue-400", border: "border-blue-500/20" },
  DELETE: { bg: "bg-red-500/10", text: "text-red-400", border: "border-red-500/20" },
};

function CodeBlock({ code, label }: { code: string; label?: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="relative group">
      {label && (
        <div className="text-[11px] uppercase tracking-wider text-white/30 mb-2 font-mono">
          {label}
        </div>
      )}
      <div className="bg-black/40 border border-white/[0.06] overflow-x-auto">
        <button
          onClick={handleCopy}
          className="absolute top-2 right-2 text-[10px] uppercase tracking-wider text-white/20 hover:text-white/60 transition-colors opacity-0 group-hover:opacity-100 font-mono"
        >
          {copied ? "Copied" : "Copy"}
        </button>
        <pre className="p-4 text-[13px] font-mono text-white/70 leading-relaxed">
          {code}
        </pre>
      </div>
    </div>
  );
}

function EndpointCard({ endpoint, index }: { endpoint: Endpoint; index: number }) {
  const [expanded, setExpanded] = useState(false);
  const colors = methodColors[endpoint.method];

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true }}
      transition={{ delay: index * 0.03 }}
      className="border border-white/[0.06] hover:border-white/[0.12] transition-colors"
    >
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-4 p-5 text-left"
      >
        <span
          className={`${colors.bg} ${colors.text} ${colors.border} border px-2.5 py-1 text-[11px] font-mono font-semibold tracking-wider shrink-0`}
        >
          {endpoint.method}
        </span>
        <code className="text-white/80 font-mono text-sm">{endpoint.path}</code>
        <span className="text-white/40 text-sm ml-auto hidden sm:block">{endpoint.summary}</span>
        {endpoint.auth && (
          <span className="text-[10px] uppercase tracking-wider text-amber-400/60 border border-amber-400/20 px-2 py-0.5 shrink-0">
            Auth
          </span>
        )}
        <svg
          className={`w-4 h-4 text-white/30 shrink-0 transition-transform ${expanded ? "rotate-180" : ""}`}
          fill="none"
          viewBox="0 0 24 24"
          strokeWidth={2}
          stroke="currentColor"
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5" />
        </svg>
      </button>

      {expanded && (
        <motion.div
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: "auto" }}
          className="border-t border-white/[0.06] p-5 space-y-5"
        >
          <p className="text-white/50 text-sm leading-relaxed">{endpoint.description}</p>

          {endpoint.request?.body && (
            <CodeBlock code={endpoint.request.body} label="Request body" />
          )}

          {endpoint.response && (
            <CodeBlock code={endpoint.response} label="Response" />
          )}
        </motion.div>
      )}
    </motion.div>
  );
}

export default function APIReferencePage() {
  const [activeTag, setActiveTag] = useState<string | null>(null);
  const filtered = activeTag ? endpoints.filter((e) => e.tag === activeTag) : endpoints;

  return (
    <main className="min-h-screen bg-gray-950">
      <Navigation />

      <div className="pt-32 pb-24">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">
          {/* Header */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="mb-16"
          >
            <p className="text-xs font-semibold tracking-[0.2em] text-rose-400 uppercase mb-4">
              Documentation
            </p>
            <h1
              className="text-5xl sm:text-6xl text-white mb-6"
              style={{ fontFamily: "var(--font-instrument), Georgia, serif" }}
            >
              API Reference
            </h1>
            <p className="text-lg text-white/50 max-w-2xl leading-relaxed">
              Everything you need to build, deploy, and invoke tools programmatically. All endpoints
              return JSON and use standard HTTP status codes.
            </p>
          </motion.div>

          {/* Base URL */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.05 }}
            className="mb-12 p-5 border border-white/[0.06] bg-white/[0.02]"
          >
            <div className="flex items-center justify-between flex-wrap gap-3">
              <div>
                <span className="text-[11px] uppercase tracking-wider text-white/30 font-mono block mb-1">
                  Base URL
                </span>
                <code className="text-white font-mono text-sm">{API_URL}</code>
              </div>
              <div>
                <span className="text-[11px] uppercase tracking-wider text-white/30 font-mono block mb-1">
                  Authentication
                </span>
                <code className="text-white/70 font-mono text-sm">X-API-Key: fnd_...</code>
              </div>
              <a
                href={`${API_URL}/docs`}
                target="_blank"
                rel="noopener noreferrer"
                className="text-sm text-rose-400 hover:text-rose-300 transition-colors font-mono"
              >
                Interactive Docs &rarr;
              </a>
            </div>
          </motion.div>

          {/* Tag Filters */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="flex flex-wrap gap-2 mb-8"
          >
            <button
              onClick={() => setActiveTag(null)}
              className={`px-3 py-1.5 text-xs font-mono uppercase tracking-wider transition-colors ${
                activeTag === null
                  ? "bg-white text-black"
                  : "text-white/40 hover:text-white/70 border border-white/[0.08]"
              }`}
            >
              All
            </button>
            {tags.map((tag) => (
              <button
                key={tag}
                onClick={() => setActiveTag(tag === activeTag ? null : tag)}
                className={`px-3 py-1.5 text-xs font-mono uppercase tracking-wider transition-colors ${
                  activeTag === tag
                    ? "bg-white text-black"
                    : "text-white/40 hover:text-white/70 border border-white/[0.08]"
                }`}
              >
                {tag}
              </button>
            ))}
          </motion.div>

          {/* Endpoints */}
          <div className="space-y-px">
            {tags
              .filter((tag) => !activeTag || tag === activeTag)
              .map((tag) => {
                const tagEndpoints = filtered.filter((e) => e.tag === tag);
                if (tagEndpoints.length === 0) return null;

                return (
                  <div key={tag} className="mb-10">
                    <h2
                      className="text-2xl text-white mb-4"
                      style={{ fontFamily: "var(--font-instrument), Georgia, serif" }}
                    >
                      {tag}
                    </h2>
                    <div className="space-y-px bg-white/[0.04]">
                      {tagEndpoints.map((endpoint, i) => (
                        <EndpointCard
                          key={`${endpoint.method}-${endpoint.path}`}
                          endpoint={endpoint}
                          index={i}
                        />
                      ))}
                    </div>
                  </div>
                );
              })}
          </div>

          {/* SDK */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="mt-20 border border-white/[0.06] p-8"
          >
            <div className="grid md:grid-cols-2 gap-8">
              <div>
                <p className="text-xs font-semibold tracking-[0.2em] text-rose-400 uppercase mb-3">
                  Python SDK
                </p>
                <h3
                  className="text-3xl text-white mb-4"
                  style={{ fontFamily: "var(--font-instrument), Georgia, serif" }}
                >
                  Prefer code over cURL?
                </h3>
                <p className="text-white/50 leading-relaxed mb-6">
                  The Foundry Python SDK wraps all API endpoints with typed methods, tool chaining, and
                  automatic retries.
                </p>
                <code className="text-sm font-mono text-white/60 bg-black/30 px-4 py-2 inline-block border border-white/[0.06]">
                  pip install foundry-sdk
                </code>
              </div>
              <CodeBlock
                code={`from foundry import Foundry

client = Foundry(api_key="fnd_...")

# Build a tool from a description
tool = client.create(
    "Calculate compound interest"
)

# Invoke it
result = tool.invoke(
    principal=10000,
    annual_rate=0.05,
    years=10
)

print(result.result)
# {"final_amount": 16288.95, ...}`}
                label="Quick start"
              />
            </div>
          </motion.div>

          {/* Error Codes */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="mt-12"
          >
            <h2
              className="text-2xl text-white mb-6"
              style={{ fontFamily: "var(--font-instrument), Georgia, serif" }}
            >
              Status Codes
            </h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-px bg-white/[0.04]">
              {[
                { code: "200", label: "Success", desc: "Request completed successfully" },
                { code: "400", label: "Bad Request", desc: "Invalid parameters or request body" },
                { code: "401", label: "Unauthorized", desc: "Missing or invalid API key" },
                { code: "403", label: "Forbidden", desc: "API key lacks required scope" },
                { code: "404", label: "Not Found", desc: "Tool or resource not found" },
                { code: "410", label: "Gone", desc: "Tool has expired or is deprecated" },
                { code: "422", label: "Validation Error", desc: "Request body failed validation" },
                { code: "429", label: "Rate Limited", desc: "Monthly usage limit exceeded" },
              ].map((status) => (
                <div
                  key={status.code}
                  className="bg-gray-950 p-5 flex items-start gap-4"
                >
                  <span className="font-mono text-sm text-white/80 shrink-0 w-8">
                    {status.code}
                  </span>
                  <div>
                    <span className="text-white text-sm font-medium">{status.label}</span>
                    <p className="text-white/40 text-sm mt-0.5">{status.desc}</p>
                  </div>
                </div>
              ))}
            </div>
          </motion.div>
        </div>
      </div>

      <Footer />
    </main>
  );
}
