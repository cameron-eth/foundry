"use client";

import { useState, useEffect, Fragment } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Menu, Transition } from "@headlessui/react";
import { ChevronDownIcon, Bars3Icon, XMarkIcon } from "@heroicons/react/24/outline";
import Link from "next/link";

const API_URL = "https://camfleety--toolfoundry-serve.modal.run";

const developers = [
  { name: "API Reference", href: "/api-reference", description: "Full endpoint documentation" },
  { name: "Interactive Docs", href: `${API_URL}/docs`, description: "Try endpoints in the browser" },
  { name: "Blog", href: "/blog", description: "Updates and tutorials" },
];

export default function Navigation() {
  const [scrolled, setScrolled] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  useEffect(() => {
    const handleScroll = () => {
      setScrolled(window.scrollY > 50);
    };
    window.addEventListener("scroll", handleScroll);
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  return (
    <motion.nav
      initial={{ y: -100 }}
      animate={{ y: 0 }}
      transition={{ duration: 0.6, ease: "easeOut" }}
      className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 ${
        scrolled
          ? "bg-black/90 backdrop-blur-xl border-b border-white/10"
          : "bg-transparent"
      }`}
    >
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16 lg:h-20">
          {/* Logo */}
          <Link href="/" className="flex items-center">
            <motion.div
              whileHover={{ scale: 1.03 }}
              whileTap={{ scale: 0.97 }}
              className="relative"
            >
              <span
                className={`text-2xl tracking-tight transition-colors duration-300 ${
                  scrolled ? "text-white" : "text-gray-900"
                }`}
                style={{ fontFamily: "var(--font-instrument), Georgia, serif" }}
              >
                Foundry
              </span>
            </motion.div>
          </Link>

          {/* Desktop Navigation */}
          <div className="hidden lg:flex items-center gap-1">
            <Link
              href="/pricing"
              className={`px-4 py-2 text-sm font-medium uppercase tracking-wider transition-colors ${
                scrolled ? "text-white hover:text-white/80" : "text-gray-700 hover:text-gray-900"
              }`}
            >
              Pricing
            </Link>

            {/* Developers Dropdown */}
            <Menu as="div" className="relative">
              {({ open }) => (
                <>
                  <Menu.Button className={`flex items-center gap-1 px-4 py-2 text-sm font-medium uppercase tracking-wider transition-colors ${
                    scrolled ? "text-white hover:text-white/80" : "text-gray-700 hover:text-gray-900"
                  }`}>
                    Developers
                    <ChevronDownIcon
                      className={`w-4 h-4 transition-transform ${open ? "rotate-180" : ""}`}
                    />
                  </Menu.Button>
                  <Transition
                    as={Fragment}
                    enter="transition ease-out duration-200"
                    enterFrom="opacity-0 translate-y-2"
                    enterTo="opacity-100 translate-y-0"
                    leave="transition ease-in duration-150"
                    leaveFrom="opacity-100 translate-y-0"
                    leaveTo="opacity-0 translate-y-2"
                  >
                    <Menu.Items className="absolute left-0 mt-2 w-72 origin-top-left bg-[#0a0a0f] border border-white/[0.08] rounded-none shadow-2xl overflow-hidden focus:outline-none">
                      <div>
                        {developers.map((item) => (
                          <Menu.Item key={item.name}>
                            {({ active }) => (
                              <a
                                href={item.href}
                                className={`block px-6 py-5 transition-colors border-b border-white/[0.08] last:border-b-0 ${
                                  active ? "bg-white/[0.03]" : ""
                                }`}
                              >
                                <p 
                                  className="text-white text-lg mb-1"
                                  style={{ fontFamily: "var(--font-instrument), Georgia, serif" }}
                                >
                                  {item.name}
                                </p>
                                <p className="text-white/40 text-sm">{item.description}</p>
                              </a>
                            )}
                          </Menu.Item>
                        ))}
                      </div>
                    </Menu.Items>
                  </Transition>
                </>
              )}
            </Menu>

            {/* CTA Buttons */}
            <div className="flex items-center gap-2 ml-4">
              <Link
                href="/login"
                className={`px-4 py-2 text-sm font-medium uppercase tracking-wider transition-colors ${
                  scrolled ? "text-white hover:text-white/80" : "text-gray-700 hover:text-gray-900"
                }`}
              >
                Login
              </Link>
              <motion.a
                href="/signup"
                className={`px-4 py-2 text-sm font-medium uppercase tracking-wider border transition-colors ${
                  scrolled 
                    ? "text-white border-white/50 hover:border-white" 
                    : "text-gray-700 hover:text-gray-900 border-gray-300 hover:border-gray-400"
                }`}
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
              >
                Sign Up
              </motion.a>
            </div>
          </div>

          {/* Mobile menu button */}
          <button
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            className={`lg:hidden p-2 rounded-lg transition-colors ${
              scrolled ? "text-white" : "text-gray-900"
            }`}
          >
            {mobileMenuOpen ? (
              <XMarkIcon className="w-6 h-6" />
            ) : (
              <Bars3Icon className="w-6 h-6" />
            )}
          </button>
        </div>
      </div>

      {/* Mobile Menu */}
      <AnimatePresence>
        {mobileMenuOpen && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="lg:hidden bg-black/95 backdrop-blur-xl border-t border-white/10"
          >
            <div className="px-4 py-6 space-y-4">
              <Link href="/pricing" className="block text-white py-2 font-medium uppercase tracking-wider text-sm">
                Pricing
              </Link>
              <Link href="/api-reference" className="block text-white py-2 font-medium uppercase tracking-wider text-sm">
                API Reference
              </Link>
              <a href={`${API_URL}/docs`} className="block text-white py-2 font-medium uppercase tracking-wider text-sm">
                Interactive Docs
              </a>
              <Link href="/blog" className="block text-white py-2 font-medium uppercase tracking-wider text-sm">
                Blog
              </Link>
              <div className="pt-4 border-t border-white/10 flex gap-3">
                <Link
                  href="/login"
                  className="flex-1 text-center text-white py-3 font-medium uppercase tracking-wider text-sm border border-white/20"
                >
                  Login
                </Link>
                <Link
                  href="/signup"
                  className="flex-1 text-center bg-rose-500 text-white py-3 font-semibold uppercase tracking-wider text-sm"
                >
                  Sign Up
                </Link>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.nav>
  );
}
