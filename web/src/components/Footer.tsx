"use client";

import { motion } from "framer-motion";
import Link from "next/link";

const API_URL = "https://camfleety--toolfoundry-serve.modal.run";

const footerLinks = {
  Product: [
    { name: "Features", href: "#features" },
    { name: "Demo", href: "#demo" },
    { name: "Pricing", href: "/pricing" },
  ],
  Resources: [
    { name: "Documentation", href: `${API_URL}/docs` },
    { name: "API Reference", href: "/api-reference" },
    { name: "Examples", href: "#demo" },
    { name: "Blog", href: "/blog" },
  ],
  Company: [
    { name: "About", href: "#" },
    { name: "Contact", href: "#" },
  ],
  Legal: [
    { name: "Privacy", href: "#" },
    { name: "Terms", href: "#" },
    { name: "Security", href: "#" },
  ],
};

export default function Footer() {
  return (
    <footer className="bg-gray-950 border-t border-white/10">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16 lg:py-20">
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-8 lg:gap-12">
          {/* Brand */}
          <div className="col-span-2 md:col-span-4 lg:col-span-1 mb-8 lg:mb-0">
            <Link href="/" className="inline-block mb-4">
              <span 
                className="text-2xl text-white italic"
                style={{ fontFamily: "var(--font-instrument), Georgia, serif" }}
              >
                Foundry
              </span>
            </Link>
            <p className="text-white/50 text-sm leading-relaxed max-w-xs">
              AI agents building tools for themselves. Dynamic tool creation at
              runtime.
            </p>
          </div>

          {/* Links */}
          {Object.entries(footerLinks).map(([category, links]) => (
            <div key={category}>
              <h3 className="text-sm font-semibold text-white tracking-wider uppercase mb-4">
                {category}
              </h3>
              <ul className="space-y-3">
                {links.map((link) => (
                  <li key={link.name}>
                    <a
                      href={link.href}
                      className="text-white/50 hover:text-white transition-colors text-sm"
                    >
                      {link.name}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        {/* Bottom */}
        <div className="mt-16 pt-8 border-t border-white/10 flex flex-col sm:flex-row justify-between items-center gap-4">
          <p className="text-white/30 text-sm">
            © 2026 Foundry. Built on Modal.
          </p>
          <div className="flex items-center gap-2 text-white/30 text-sm">
            <span className="inline-flex items-center gap-1">
              <span className="w-2 h-2 bg-lime-400 rounded-full animate-pulse" />
              All systems operational
            </span>
            <span className="mx-2">•</span>
            <a href={`${API_URL}/health`} className="hover:text-white/50 transition-colors">
              Status
            </a>
          </div>
        </div>
      </div>
    </footer>
  );
}
