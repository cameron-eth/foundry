"use client";

import Navigation from "@/components/Navigation";
import Footer from "@/components/Footer";
import { motion } from "framer-motion";

const API_URL = "https://camfleety--toolfoundry-serve.modal.run";

export default function APIReferencePage() {
  return (
    <main className="min-h-screen bg-gray-950">
      <Navigation />
      <div className="pt-32 pb-24">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="mb-12"
          >
            <h1 
              className="text-5xl sm:text-6xl text-white mb-6"
              style={{ fontFamily: "var(--font-instrument), Georgia, serif" }}
            >
              API Reference
            </h1>
            <p className="text-xl text-white/60 max-w-2xl">
              Complete API documentation for Foundry. Build tools programmatically.
            </p>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="bg-gray-900 border border-white/10 rounded-2xl p-8 mb-8"
          >
            <h2 className="text-2xl text-white mb-4">Base URL</h2>
            <code className="text-lime-400 font-mono">{API_URL}</code>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="text-center"
          >
            <p className="text-white/60 mb-6">
              Full API documentation is available in our interactive docs.
            </p>
            <a
              href={`${API_URL}/docs`}
              className="inline-block px-8 py-4 bg-rose-500 text-white font-semibold tracking-wider uppercase text-sm hover:bg-rose-600 transition-colors"
            >
              View Full API Docs
            </a>
          </motion.div>
        </div>
      </div>
      <Footer />
    </main>
  );
}
