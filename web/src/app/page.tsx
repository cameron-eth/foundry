"use client";

import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import Navigation from "@/components/Navigation";
import Hero from "@/components/Hero";
import TrustBanner from "@/components/TrustBanner";
import Features from "@/components/Features";
import CodeDemo from "@/components/CodeDemo";
import CTA from "@/components/CTA";
import Footer from "@/components/Footer";

export default function Home() {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted) return null;

  return (
    <main className="overflow-x-hidden">
      <Navigation />
      <Hero />
      <TrustBanner />
      <Features />
      <CodeDemo />
      <CTA />
      <Footer />
      </main>
  );
}
