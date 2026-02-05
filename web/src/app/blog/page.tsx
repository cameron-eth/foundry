"use client";

import Navigation from "@/components/Navigation";
import Footer from "@/components/Footer";
import { motion } from "framer-motion";

export default function BlogPage() {
  return (
    <main className="min-h-screen bg-gray-950">
      <Navigation />
      <div className="pt-32 pb-24">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="text-center mb-20"
          >
            <h1 
              className="text-5xl sm:text-6xl text-white mb-6"
              style={{ fontFamily: "var(--font-instrument), Georgia, serif" }}
            >
              Blog
            </h1>
            <p className="text-xl text-white/60 max-w-2xl mx-auto">
              Latest updates, tutorials, and insights from the Foundry team.
            </p>
          </motion.div>

          <div className="text-center">
            <p className="text-white/50">Coming soon</p>
          </div>
        </div>
      </div>
      <Footer />
    </main>
  );
}
