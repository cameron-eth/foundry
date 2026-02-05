"use client";

import { motion } from "framer-motion";

const API_URL = "https://camfleety--toolfoundry-serve.modal.run";

export default function CodeDemo() {
  return (
    <section id="demo" className="py-24 lg:py-32 bg-gray-950 border-t border-white/10">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-16 items-center">
          {/* Left: Content */}
          <motion.div
            initial={{ opacity: 0, x: -20 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true }}
          >
            <p className="text-xs font-semibold tracking-[0.2em] text-rose-400 uppercase mb-4">
              How it works
            </p>
            <h2 
              className="text-4xl sm:text-5xl text-white mb-6"
              style={{ fontFamily: "var(--font-instrument), Georgia, serif" }}
            >
              One API call. <br />Infinite possibilities.
            </h2>
            <p className="text-lg text-white/60 leading-relaxed mb-8">
              Describe the tool you need in natural language. Foundry handles the rest—
              generating code, validating safety, and deploying instantly.
            </p>

            {/* Steps */}
            <div className="space-y-5">
              {[
                { step: "1", title: "Describe", desc: "Tell Foundry what capability you need" },
                { step: "2", title: "Generate", desc: "AI creates production-ready Python code" },
                { step: "3", title: "Deploy", desc: "Tool is live and ready in under 2 seconds" },
                { step: "4", title: "Invoke", desc: "Call your tool with any input data" },
              ].map((item, index) => (
                <motion.div
                  key={item.step}
                  initial={{ opacity: 0, x: -20 }}
                  whileInView={{ opacity: 1, x: 0 }}
                  viewport={{ once: true }}
                  transition={{ delay: index * 0.1 }}
                  className="flex items-start gap-4"
                >
                  <span className="shrink-0 w-9 h-9 rounded-full border border-white/20 flex items-center justify-center text-sm text-white/50">
                    {item.step}
                  </span>
                  <div>
                    <h4 className="text-white font-medium text-[15px]">{item.title}</h4>
                    <p className="text-white/40 text-sm">{item.desc}</p>
                  </div>
                </motion.div>
              ))}
            </div>

            <motion.a
              href={`${API_URL}/docs`}
              className="inline-block mt-10 px-8 py-4 bg-rose-500 text-white font-semibold tracking-wider uppercase text-sm hover:bg-rose-600 transition-colors"
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
            >
              Try It Now
            </motion.a>
          </motion.div>

          {/* Right: Stats Grid (matching Features style) */}
          <motion.div
            initial={{ opacity: 0, x: 20 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true }}
            className="relative"
          >
            <div className="grid grid-cols-2 border-l border-t border-white/[0.08]">
              {[
                { number: "01", title: "Under 2 Seconds", desc: "Average build time from description to deployed tool" },
                { number: "02", title: "100% Sandboxed", desc: "Every tool runs in complete isolation for safety" },
                { number: "03", title: "Zero Cold Starts", desc: "Tools are pre-warmed and ready to execute instantly" },
                { number: "04", title: "Infinite Scale", desc: "Automatically scales from zero to millions of requests" },
              ].map((stat, index) => (
                <motion.div
                  key={stat.number}
                  initial={{ opacity: 0, y: 20 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true }}
                  transition={{ delay: index * 0.1 }}
                  className="p-8 lg:p-10 border-r border-b border-white/[0.08] hover:bg-white/[0.02] transition-colors"
                >
                  <span className="text-white/30 text-sm font-mono mb-6 block">
                    {stat.number}
                  </span>
                  <h3 
                    className="text-xl lg:text-2xl text-white mb-3"
                    style={{ fontFamily: "var(--font-instrument), Georgia, serif" }}
                  >
                    {stat.title}
                  </h3>
                  <p className="text-white/40 text-sm leading-relaxed">
                    {stat.desc}
                  </p>
                </motion.div>
              ))}
            </div>
          </motion.div>
        </div>
      </div>
    </section>
  );
}
