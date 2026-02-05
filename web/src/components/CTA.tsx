"use client";

import { motion } from "framer-motion";

const API_URL = "https://camfleety--toolfoundry-serve.modal.run";

export default function CTA() {
  return (
    <section className="relative py-24 lg:py-32 bg-gray-950 border-t border-white/10 overflow-hidden">
      {/* Gradient Background */}
      <div 
        className="absolute inset-0 opacity-20"
        style={{
          background: `
            linear-gradient(180deg,
              #1a1a1a 0%,
              #5b21b6 30%,
              #7c3aed 50%,
              #5b21b6 70%,
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
              rgba(255,255,255,0.04) 1deg,
              rgba(255,255,255,0.04) 2deg
            )
          `,
        }}
      />

      {/* Horizontal Bands */}
      <div 
        className="absolute inset-0 opacity-25"
        style={{
          background: `
            repeating-linear-gradient(
              0deg,
              transparent 0px,
              transparent 8px,
              rgba(167, 139, 250, 0.15) 8px,
              rgba(167, 139, 250, 0.15) 10px
            )
          `,
        }}
      />

      <div className="relative z-10 max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
        <motion.h2
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="text-4xl sm:text-5xl lg:text-6xl text-white mb-6"
          style={{ fontFamily: "var(--font-instrument), Georgia, serif" }}
        >
          Ready to build?
        </motion.h2>

        <motion.p
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ delay: 0.1 }}
          className="text-xl text-white/60 mb-10 max-w-2xl mx-auto"
        >
          Start creating AI tools in seconds. No credit card required.
        </motion.p>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ delay: 0.2 }}
          className="flex flex-col sm:flex-row items-center justify-center gap-4"
        >
          <motion.a
            href={`${API_URL}/docs`}
            className="px-8 py-4 bg-rose-500 text-white font-semibold tracking-wider uppercase text-sm hover:bg-rose-600 transition-colors"
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
          >
            Get Started Free
          </motion.a>
          <motion.a
            href={`${API_URL}/docs`}
            className="px-8 py-4 border border-white/20 text-white font-semibold tracking-wider uppercase text-sm hover:bg-white/10 transition-colors"
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
          >
            View Documentation
          </motion.a>
        </motion.div>
      </div>
    </section>
  );
}
