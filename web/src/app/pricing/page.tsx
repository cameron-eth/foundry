"use client";

import Navigation from "@/components/Navigation";
import Footer from "@/components/Footer";
import { motion } from "framer-motion";

export default function PricingPage() {
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
              Pricing
            </h1>
            <p className="text-xl text-white/60 max-w-2xl mx-auto">
              Simple, transparent pricing. Pay only for what you use.
            </p>
          </motion.div>

          {/* Pricing cards placeholder */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8 max-w-5xl mx-auto">
            {["Starter", "Pro", "Enterprise"].map((tier, index) => (
              <motion.div
                key={tier}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: index * 0.1 }}
                className="bg-gray-900 border border-white/10 rounded-2xl p-8"
              >
                <h3 className="text-2xl text-white mb-4">{tier}</h3>
                <p className="text-white/50 mb-8">Coming soon</p>
              </motion.div>
            ))}
          </div>
        </div>
      </div>
      <Footer />
    </main>
  );
}
