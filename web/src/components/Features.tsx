"use client";

import { motion } from "framer-motion";

const features = [
  {
    number: "01",
    title: "AI-Powered Generation",
    description:
      "Describe what you need in plain English. GPT-5.2 generates production-ready Python tools automatically.",
  },
  {
    number: "02",
    title: "Instant Deployment",
    description:
      "Tools are deployed and ready to invoke in under 2 seconds. No build steps, no containers to manage.",
  },
  {
    number: "03",
    title: "Secure Sandboxing",
    description:
      "Every tool runs in an isolated sandbox with no network, filesystem, or system access. Safe by design.",
  },
  {
    number: "04",
    title: "Rich Output Types",
    description:
      "Return numbers, text, tables, or even images. Typed responses make parsing deterministic.",
  },
  {
    number: "05",
    title: "Web Search Built-in",
    description:
      "Tools can search the web via Exa API. Give your agents access to real-time information.",
  },
  {
    number: "06",
    title: "Pay Per Use",
    description:
      "Only pay for compute time. No idle servers, no minimum fees. Scale from zero to millions.",
  },
];

export default function Features() {
  return (
    <section id="features" className="py-24 lg:py-32 bg-gray-950">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6 }}
          className="max-w-3xl mb-20"
        >
          <p className="text-xs font-semibold tracking-[0.2em] text-rose-400 uppercase mb-4">
            Capabilities
          </p>
          <h2 
            className="text-4xl sm:text-5xl lg:text-6xl text-white mb-6"
            style={{ fontFamily: "var(--font-instrument), Georgia, serif" }}
          >
            Everything you need to build AI tools
          </h2>
          <p className="text-lg text-white/60 leading-relaxed">
            Foundry gives your AI agents the power to create custom tools on
            demand. No pre-built integrations needed—just describe and deploy.
          </p>
        </motion.div>

        {/* Features Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-px bg-white/10">
          {features.map((feature, index) => (
            <motion.div
              key={feature.title}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: index * 0.1 }}
              className="bg-gray-950 p-8 lg:p-10 group hover:bg-gray-900 transition-colors"
            >
              <span className="text-xs font-mono text-white/30 mb-6 block">
                {feature.number}
              </span>
              <h3 
                className="text-2xl text-white mb-4"
                style={{ fontFamily: "var(--font-instrument), Georgia, serif" }}
              >
                {feature.title}
              </h3>
              <p className="text-white/50 leading-relaxed">
                {feature.description}
              </p>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
