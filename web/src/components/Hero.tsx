"use client";

import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";

const API_URL = "https://camfleety--toolfoundry-serve.modal.run";

const rotatingWords = [
  "themselves",
  "healthcare",
  "eachother",
  "education",
  "researchers",
  "indie devs",
  "startups",
  "enterprise",
];

export default function Hero() {
  const [currentWordIndex, setCurrentWordIndex] = useState(0);

  useEffect(() => {
    const interval = setInterval(() => {
      setCurrentWordIndex((prev) => (prev + 1) % rotatingWords.length);
    }, 2500);
    return () => clearInterval(interval);
  }, []);

  return (
    <section className="relative min-h-screen flex flex-col items-center justify-center overflow-hidden">
      {/* Gradient Background */}
      <div 
        className="absolute inset-0"
        style={{
          background: `
            linear-gradient(180deg,
              #8b5cf6 0%,
              #a78bfa 8%,
              #fb923c 25%,
              #fdba74 40%,
              #fef3c7 50%,
              #fdba74 60%,
              #fb923c 75%,
              #a78bfa 92%,
              #8b5cf6 100%
            )
          `,
        }}
      />

      {/* Radiating Lines from Center */}
      <div 
        className="absolute inset-0 opacity-30"
        style={{
          background: `
            repeating-conic-gradient(
              from 0deg at 50% 50%,
              transparent 0deg,
              transparent 1deg,
              rgba(0,0,0,0.03) 1deg,
              rgba(0,0,0,0.03) 2deg
            )
          `,
        }}
      />

      {/* Horizontal Bands */}
      <div 
        className="absolute inset-0"
        style={{
          background: `
            repeating-linear-gradient(
              0deg,
              transparent 0px,
              transparent 8px,
              rgba(236, 72, 153, 0.15) 8px,
              rgba(236, 72, 153, 0.15) 10px
            )
          `,
        }}
      />

      {/* Content */}
      <div className="relative z-10 max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 text-center pt-20">
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, ease: "easeOut" }}
        >
          <h1 
            className="text-5xl sm:text-6xl md:text-7xl lg:text-8xl text-gray-900 leading-[1.1] tracking-tight"
            style={{ fontFamily: "var(--font-instrument), Georgia, serif" }}
          >
            <span className="block">AI Agents Building</span>
            <span className="block">
              Tools for {" "}<span className="relative inline-block w-[180px] sm:w-[240px] md:w-[280px] lg:w-[320px]">
                <AnimatePresence mode="wait">
                  <motion.span
                    key={currentWordIndex}
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -20 }}
                    transition={{ duration: 0.3, ease: "easeOut" }}
                    className="inline-block italic whitespace-nowrap"
                  >
                    {rotatingWords[currentWordIndex]}
                  </motion.span>
                </AnimatePresence>
              </span>
            </span>
          </h1>

          <motion.p
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 0.2, ease: "easeOut" }}
            className="mt-8 text-lg sm:text-xl text-gray-800 max-w-2xl mx-auto"
          >
            Securely build and deploy tools at runtime. Describe what you need,
            get production-ready code in seconds.
          </motion.p>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 0.4, ease: "easeOut" }}
            className="mt-10 flex flex-col sm:flex-row items-center justify-center gap-6"
          >
            <motion.a
              href={`${API_URL}/docs`}
              className="px-8 py-4 bg-rose-500 text-white font-semibold tracking-wider uppercase text-sm hover:bg-rose-600 transition-colors"
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
            >
              Try It Free
            </motion.a>
            <motion.a
              href="/api-reference"
              className="px-4 py-4 text-gray-900 font-semibold tracking-wider uppercase text-sm hover:text-gray-600 transition-colors"
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
            >
              Docs
            </motion.a>
          </motion.div>
        </motion.div>
      </div>

      {/* Trust Section */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.8, delay: 0.6, ease: "easeOut" }}
        className="relative z-10 mt-20 text-center"
      >
        <p className="text-xs font-semibold tracking-[0.2em] text-gray-700 uppercase mb-8">
          Powering AI agents across industries
        </p>
        <div className="flex flex-wrap justify-center items-center gap-8 md:gap-12 px-4">
          {["Healthcare", "Finance", "Creative", "Research", "Enterprise"].map((name) => (
            <span key={name} className="text-gray-900 font-semibold text-lg">
              {name}
            </span>
          ))}
        </div>
      </motion.div>

      {/* Bottom fade to dark */}
      <div className="absolute bottom-0 left-0 right-0 h-32 bg-gradient-to-t from-gray-950 to-transparent" />
    </section>
  );
}
