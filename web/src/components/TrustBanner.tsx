"use client";

import React, { useState } from "react";
import { motion } from "framer-motion";

const integrations = [
  { name: "Discord", icon: "discord" },
  { name: "Slack", icon: "slack" },
  { name: "Asana", icon: "asana" },
  { name: "WhatsApp", icon: "whatsapp" },
  { name: "HubSpot", icon: "hubspot" },
  { name: "Microsoft", icon: "microsoft" },
  { name: "Stripe", icon: "stripe" },
  { name: "Google", icon: "google" },
  { name: "OpenAI", icon: "openai" },
  { name: "Anthropic", icon: "anthropic" },
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
            <div className="grid grid-cols-3 gap-4 mb-12 max-w-xs">
              {integrations.slice(0, 9).map((item, index) => (
                <motion.div
                  key={item.name}
                  initial={{ opacity: 0, scale: 0.8 }}
                  whileInView={{ opacity: 1, scale: 1 }}
                  viewport={{ once: true }}
                  transition={{ delay: index * 0.05 }}
                  className={`w-16 h-16 rounded-full flex items-center justify-center ${
                    index % 3 === 0 ? "bg-white/10" : "border border-white/20"
                  }`}
                >
                  <span className="text-2xl text-white/80">
                    {item.name.charAt(0)}
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
