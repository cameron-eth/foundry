"use client";

import React, { useState } from "react";
import { motion } from "framer-motion";

// SVG icons for supported integrations
const IntegrationIcons: Record<string, React.ReactElement> = {
  openai: (
    <svg className="w-7 h-7" viewBox="0 0 24 24" fill="currentColor">
      <path d="M22.2819 9.8211a5.9847 5.9847 0 0 0-.5157-4.9108 6.0462 6.0462 0 0 0-6.5098-2.9A6.0651 6.0651 0 0 0 4.9807 4.1818a5.9847 5.9847 0 0 0-3.9977 2.9 6.0462 6.0462 0 0 0 .7427 7.0966 5.98 5.98 0 0 0 .511 4.9107 6.051 6.051 0 0 0 6.5146 2.9001A5.9847 5.9847 0 0 0 13.2599 24a6.0557 6.0557 0 0 0 5.7718-4.2058 5.9894 5.9894 0 0 0 3.9977-2.9001 6.0557 6.0557 0 0 0-.7475-7.0729zm-9.022 12.6081a4.4755 4.4755 0 0 1-2.8764-1.0408l.1419-.0804 4.7783-2.7582a.7948.7948 0 0 0 .3927-.6813v-6.7369l2.02 1.1686a.071.071 0 0 1 .038.052v5.5826a4.504 4.504 0 0 1-4.4945 4.4944zm-9.6607-4.1254a4.4708 4.4708 0 0 1-.5346-3.0137l.142.0852 4.783 2.7582a.7712.7712 0 0 0 .7806 0l5.8428-3.3685v2.3324a.0804.0804 0 0 1-.0332.0615L9.74 19.9502a4.4992 4.4992 0 0 1-6.1408-1.6464zM2.3408 7.8956a4.485 4.485 0 0 1 2.3655-1.9728V11.6a.7664.7664 0 0 0 .3879.6765l5.8144 3.3543-2.0201 1.1685a.0757.0757 0 0 1-.071 0l-4.8303-2.7865A4.504 4.504 0 0 1 2.3408 7.872zm16.5963 3.8558L13.1038 8.364 15.1192 7.2a.0757.0757 0 0 1 .071 0l4.8303 2.7913a4.4944 4.4944 0 0 1-.6765 8.1042v-5.6772a.79.79 0 0 0-.407-.667zm2.0107-3.0231l-.142-.0852-4.7735-2.7818a.7759.7759 0 0 0-.7854 0L9.409 9.2297V6.8974a.0662.0662 0 0 1 .0284-.0615l4.8303-2.7866a4.4992 4.4992 0 0 1 6.6802 4.66zM8.3065 12.863l-2.02-1.1638a.0804.0804 0 0 1-.038-.0567V6.0742a4.4992 4.4992 0 0 1 7.3757-3.4537l-.142.0805L8.704 5.459a.7948.7948 0 0 0-.3927.6813zm1.0976-2.3654l2.602-1.4998 2.6069 1.4998v2.9994l-2.5974 1.4997-2.6067-1.4997Z" />
    </svg>
  ),
  anthropic: (
    <svg className="w-7 h-7" viewBox="0 0 24 24" fill="currentColor">
      <path d="M13.827 3.52h3.603L24 20.48h-3.603l-6.57-16.96zm-7.257 0h3.603L16.743 20.48h-3.603L6.57 3.52zM0 20.48h3.603L10.173 3.52H6.57L0 20.48z" />
    </svg>
  ),
  polymarket: (
    <svg className="w-7 h-7" viewBox="0 0 24 24" fill="currentColor">
      <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" stroke="currentColor" strokeWidth="1.5" fill="none" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ),
  stripe: (
    <svg className="w-7 h-7" viewBox="0 0 24 24" fill="currentColor">
      <path d="M13.976 9.15c-2.172-.806-3.356-1.426-3.356-2.409 0-.831.683-1.305 1.901-1.305 2.227 0 4.515.858 6.09 1.631l.89-5.494C18.252.975 15.697 0 12.165 0 9.667 0 7.589.654 6.104 1.872 4.56 3.147 3.757 4.992 3.757 7.218c0 4.039 2.467 5.76 6.476 7.219 2.585.92 3.445 1.574 3.445 2.583 0 .98-.84 1.545-2.354 1.545-1.875 0-4.965-.921-6.99-2.109l-.9 5.555C5.175 22.99 8.385 24 11.714 24c2.641 0 4.843-.624 6.328-1.813 1.664-1.305 2.525-3.236 2.525-5.732 0-4.128-2.524-5.851-6.591-7.305z" />
    </svg>
  ),
  google: (
    <svg className="w-7 h-7" viewBox="0 0 24 24" fill="currentColor">
      <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" />
      <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
      <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
      <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
    </svg>
  ),
  slack: (
    <svg className="w-7 h-7" viewBox="0 0 24 24" fill="currentColor">
      <path d="M5.042 15.165a2.528 2.528 0 0 1-2.52 2.523A2.528 2.528 0 0 1 0 15.165a2.527 2.527 0 0 1 2.522-2.52h2.52v2.52zm1.271 0a2.527 2.527 0 0 1 2.521-2.52 2.527 2.527 0 0 1 2.521 2.52v6.313A2.528 2.528 0 0 1 8.834 24a2.528 2.528 0 0 1-2.521-2.522v-6.313zM8.834 5.042a2.528 2.528 0 0 1-2.521-2.52A2.528 2.528 0 0 1 8.834 0a2.528 2.528 0 0 1 2.521 2.522v2.52H8.834zm0 1.271a2.528 2.528 0 0 1 2.521 2.521 2.528 2.528 0 0 1-2.521 2.521H2.522A2.528 2.528 0 0 1 0 8.834a2.528 2.528 0 0 1 2.522-2.521h6.312zm10.122 2.521a2.528 2.528 0 0 1 2.522-2.521A2.528 2.528 0 0 1 24 8.834a2.528 2.528 0 0 1-2.522 2.521h-2.522V8.834zm-1.268 0a2.528 2.528 0 0 1-2.523 2.521 2.527 2.527 0 0 1-2.52-2.521V2.522A2.527 2.527 0 0 1 15.165 0a2.528 2.528 0 0 1 2.523 2.522v6.312zm-2.523 10.122a2.528 2.528 0 0 1 2.523 2.522A2.528 2.528 0 0 1 15.165 24a2.527 2.527 0 0 1-2.52-2.522v-2.522h2.52zm0-1.268a2.527 2.527 0 0 1-2.52-2.523 2.526 2.526 0 0 1 2.52-2.52h6.313A2.527 2.527 0 0 1 24 15.165a2.528 2.528 0 0 1-2.522 2.523h-6.313z" />
    </svg>
  ),
  github: (
    <svg className="w-7 h-7" viewBox="0 0 24 24" fill="currentColor">
      <path d="M12 .297c-6.63 0-12 5.373-12 12 0 5.303 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61C4.422 18.07 3.633 17.7 3.633 17.7c-1.087-.744.084-.729.084-.729 1.205.084 1.838 1.236 1.838 1.236 1.07 1.835 2.809 1.305 3.495.998.108-.776.417-1.305.76-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.96-.267 1.98-.399 3-.405 1.02.006 2.04.138 3 .405 2.28-1.552 3.285-1.23 3.285-1.23.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22 0 1.606-.015 2.896-.015 3.286 0 .315.21.69.825.57C20.565 22.092 24 17.592 24 12.297c0-6.627-5.373-12-12-12" />
    </svg>
  ),
  discord: (
    <svg className="w-7 h-7" viewBox="0 0 24 24" fill="currentColor">
      <path d="M20.317 4.3698a19.7913 19.7913 0 0 0-4.8851-1.5152.0741.0741 0 0 0-.0785.0371c-.211.3753-.4447.8648-.6083 1.2495-1.8447-.2762-3.68-.2762-5.4868 0-.1636-.3933-.4058-.8742-.6177-1.2495a.077.077 0 0 0-.0785-.037 19.7363 19.7363 0 0 0-4.8852 1.515.0699.0699 0 0 0-.0321.0277C.5334 9.0458-.319 13.5799.0992 18.0578a.0824.0824 0 0 0 .0312.0561c2.0528 1.5076 4.0413 2.4228 5.9929 3.0294a.0777.0777 0 0 0 .0842-.0276c.4616-.6304.8731-1.2952 1.226-1.9942a.076.076 0 0 0-.0416-.1057c-.6528-.2476-1.2743-.5495-1.8722-.8923a.077.077 0 0 1-.0076-.1277c.1258-.0943.2517-.1923.3718-.2914a.0743.0743 0 0 1 .0776-.0105c3.9278 1.7933 8.18 1.7933 12.0614 0a.0739.0739 0 0 1 .0785.0095c.1202.099.246.1981.3728.2924a.077.077 0 0 1-.0066.1276 12.2986 12.2986 0 0 1-1.873.8914.0766.0766 0 0 0-.0407.1067c.3604.698.7719 1.3628 1.225 1.9932a.076.076 0 0 0 .0842.0286c1.961-.6067 3.9495-1.5219 6.0023-3.0294a.077.077 0 0 0 .0313-.0552c.5004-5.177-.8382-9.6739-3.5485-13.6604a.061.061 0 0 0-.0312-.0286zM8.02 15.3312c-1.1825 0-2.1569-1.0857-2.1569-2.419 0-1.3332.9555-2.4189 2.157-2.4189 1.2108 0 2.1757 1.0952 2.1568 2.419 0 1.3332-.9555 2.4189-2.1569 2.4189zm7.9748 0c-1.1825 0-2.1569-1.0857-2.1569-2.419 0-1.3332.9554-2.4189 2.1569-2.4189 1.2108 0 2.1757 1.0952 2.1568 2.419 0 1.3332-.946 2.4189-2.1568 2.4189z" />
    </svg>
  ),
  exa: (
    <svg className="w-7 h-7" viewBox="0 0 24 24" fill="currentColor">
      <path d="M4 4h6v6H4zM14 4h6v6h-6zM4 14h6v6H4zM14 14h6v6h-6z" opacity="0.8" />
      <path d="M9 9h6v6H9z" />
    </svg>
  ),
};

const integrations = [
  { name: "OpenAI", key: "openai" },
  { name: "Anthropic", key: "anthropic" },
  { name: "Polymarket", key: "polymarket" },
  { name: "Stripe", key: "stripe" },
  { name: "Google", key: "google" },
  { name: "Slack", key: "slack" },
  { name: "GitHub", key: "github" },
  { name: "Discord", key: "discord" },
  { name: "Exa", key: "exa" },
];

const codeExamples = {
  python: `import os
from foundry import Foundry

USER_ID = "unique_user_id"
PROMPT = "Create a tool that analyzes patient vitals and flags anomalies"

client = Foundry(
    base_url="https://api.foundry.ai",
    api_key=os.environ.get("FOUNDRY_API_KEY")
)

# Build a new tool from description
tool = client.tools.create(
    description=PROMPT,
    user=USER_ID,
)

# Invoke the tool with real data
result = client.tools.invoke(
    tool_id=tool.id,
    input={"heart_rate": 142, "bp": "180/95"}
)

print(result.output)`,
  javascript: `import Foundry from '@foundry/sdk';

const client = new Foundry({
  apiKey: process.env.FOUNDRY_API_KEY,
});

// Build a new tool from description
const tool = await client.tools.create({
  description: "Analyze patient vitals and flag anomalies",
  userId: "unique_user_id",
});

// Invoke the tool with real data
const result = await client.tools.invoke({
  toolId: tool.id,
  input: { heartRate: 142, bp: "180/95" },
});

console.log(result.output);`,
  curl: `curl -X POST https://api.foundry.ai/v1/construct \\
  -H "Authorization: Bearer $FOUNDRY_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{
    "description": "Analyze patient vitals",
    "user_id": "unique_user_id"
  }'

# Response:
# { "tool_id": "tool-abc123", "status": "ready" }

curl -X POST https://api.foundry.ai/v1/tools/tool-abc123/invoke \\
  -H "Authorization: Bearer $FOUNDRY_API_KEY" \\
  -d '{"input": {"heart_rate": 142, "bp": "180/95"}}'`,
};

const tabs = [
  { id: "python", label: "Python", icon: "py" },
  { id: "javascript", label: "JavaScript", icon: "js" },
  { id: "curl", label: "API", icon: "</>" },
];

export default function TrustBanner() {
  const [activeTab, setActiveTab] = useState("python");

  return (
    <section className="relative py-24 bg-gray-950 overflow-hidden">
      {/* Gradient Background */}
      <div 
        className="absolute inset-0 opacity-20"
        style={{
          background: `
            linear-gradient(180deg,
              #1a1a1a 0%,
              #2d1b4e 30%,
              #4c1d95 50%,
              #2d1b4e 70%,
              #1a1a1a 100%
            )
          `,
        }}
      />
      
      {/* Radiating Lines */}
      <div 
        className="absolute inset-0 opacity-30"
        style={{
          background: `
            repeating-conic-gradient(
              from 0deg at 50% 50%,
              transparent 0deg,
              transparent 1deg,
              rgba(255,255,255,0.03) 1deg,
              rgba(255,255,255,0.03) 2deg
            )
          `,
        }}
      />

      {/* Horizontal Bands */}
      <div 
        className="absolute inset-0 opacity-20"
        style={{
          background: `
            repeating-linear-gradient(
              0deg,
              transparent 0px,
              transparent 8px,
              rgba(139, 92, 246, 0.15) 8px,
              rgba(139, 92, 246, 0.15) 10px
            )
          `,
        }}
      />

      <div className="relative z-10 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-16 items-start">
          {/* Left: Integrations Grid */}
          <motion.div
            initial={{ opacity: 0, x: -20 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true }}
          >
            {/* Icons Grid */}
            <div className="grid grid-cols-3 gap-3 mb-12 max-w-xs">
              {integrations.map((item, index) => (
                <motion.div
                  key={item.name}
                  initial={{ opacity: 0, scale: 0.8 }}
                  whileInView={{ opacity: 1, scale: 1 }}
                  viewport={{ once: true }}
                  transition={{ delay: index * 0.05 }}
                  className="group relative w-16 h-16 rounded-2xl flex items-center justify-center bg-white/[0.06] border border-white/[0.08] hover:bg-white/[0.12] hover:border-white/[0.16] transition-all cursor-default"
                  title={item.name}
                >
                  <span className="text-white/60 group-hover:text-white/90 transition-colors">
                    {IntegrationIcons[item.key]}
                  </span>
                </motion.div>
              ))}
            </div>

            <h2 
              className="text-4xl sm:text-5xl text-white mb-6"
              style={{ fontFamily: "var(--font-instrument), Georgia, serif" }}
            >
              Dynamic Tool Creation
            </h2>
            <p className="text-lg text-white/60 mb-8 max-w-md">
              Drop in AI-powered tool generation for any use case. 
              Healthcare, finance, creative—the possibilities are endless. 
              We handle the complexity.
            </p>
            <motion.a
              href="#features"
              className="inline-block px-6 py-3 border border-white/30 text-white font-medium uppercase tracking-wider text-sm hover:bg-white/10 transition-colors"
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
            >
              Learn More
            </motion.a>
          </motion.div>

          {/* Right: Code Editor */}
          <motion.div
            initial={{ opacity: 0, x: 20 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true }}
            className="bg-[#0d1117] rounded-lg overflow-hidden border border-white/10"
          >
            {/* Tabs */}
            <div className="flex items-center border-b border-white/10">
              {tabs.map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`flex items-center gap-2 px-6 py-4 text-sm font-medium transition-colors ${
                    activeTab === tab.id
                      ? "text-white bg-white/5 border-b-2 border-lime-400"
                      : "text-white/50 hover:text-white/80"
                  }`}
                >
                  <span className="text-xs font-mono opacity-60">{tab.icon}</span>
                  {tab.label}
                </button>
              ))}
            </div>

            {/* Code Content */}
            <div className="p-6 overflow-x-auto">
              <pre className="text-sm font-mono leading-relaxed">
                <code>
                  {codeExamples[activeTab as keyof typeof codeExamples].split('\n').map((line, i) => (
                    <div key={i} className="whitespace-pre">
                      {highlightCode(line)}
                    </div>
                  ))}
                </code>
              </pre>
            </div>

            {/* Copy Button */}
            <div className="px-6 pb-6">
              <button 
                onClick={() => navigator.clipboard.writeText(codeExamples[activeTab as keyof typeof codeExamples])}
                className="flex items-center gap-2 px-4 py-2 border border-white/20 text-white/70 text-sm font-medium uppercase tracking-wider hover:bg-white/10 transition-colors"
              >
                Copy
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                </svg>
              </button>
            </div>
          </motion.div>
        </div>
      </div>
    </section>
  );
}

// Simple syntax highlighting
function highlightCode(line: string): React.ReactElement {
  // Keywords
  const keywords = ['import', 'from', 'const', 'let', 'var', 'await', 'async', 'def', 'class', 'return', 'if', 'else', 'for', 'while', 'try', 'catch', 'export', 'default'];
  // Built-ins
  const builtins = ['print', 'console', 'os', 'process'];
  
  let result = line;
  
  // Check for comments
  if (line.trim().startsWith('#') || line.trim().startsWith('//')) {
    return <span className="text-gray-500">{line}</span>;
  }
  
  // Check for strings
  const parts: React.ReactElement[] = [];
  let currentIndex = 0;
  const stringRegex = /(["'`])(?:(?!\1)[^\\]|\\.)*\1/g;
  let match;
  
  while ((match = stringRegex.exec(line)) !== null) {
    // Add text before the string
    if (match.index > currentIndex) {
      parts.push(
        <span key={`text-${currentIndex}`}>
          {highlightNonString(line.slice(currentIndex, match.index))}
        </span>
      );
    }
    // Add the string
    parts.push(
      <span key={`string-${match.index}`} className="text-lime-400">
        {match[0]}
      </span>
    );
    currentIndex = match.index + match[0].length;
  }
  
  // Add remaining text
  if (currentIndex < line.length) {
    parts.push(
      <span key={`text-${currentIndex}`}>
        {highlightNonString(line.slice(currentIndex))}
      </span>
    );
  }
  
  return <>{parts.length > 0 ? parts : highlightNonString(line)}</>;
}

function highlightNonString(text: string): React.ReactElement {
  const keywords = ['import', 'from', 'const', 'let', 'var', 'await', 'async', 'def', 'class', 'return', 'if', 'else', 'for', 'while', 'try', 'catch', 'export', 'default', 'curl', '-X', '-H', '-d'];
  const builtins = ['print', 'console', 'os', 'process', 'POST', 'GET'];
  
  const words = text.split(/(\s+|[(){}[\],;:.=])/);
  
  return (
    <>
      {words.map((word, i) => {
        if (keywords.includes(word)) {
          return <span key={i} className="text-purple-400">{word}</span>;
        }
        if (builtins.includes(word)) {
          return <span key={i} className="text-amber-400">{word}</span>;
        }
        return <span key={i} className="text-white/90">{word}</span>;
      })}
    </>
  );
}
