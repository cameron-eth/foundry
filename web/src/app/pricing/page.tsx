"use client";

import Navigation from "@/components/Navigation";
import Footer from "@/components/Footer";
import { motion } from "framer-motion";
import { useState } from "react";
import { createCheckout, isAuthenticated } from "@/lib/api";
import { useRouter } from "next/navigation";

// =============================================================================
// Pricing Model
//
// Compute Unit (CU) = universal billing unit
//   - 1 tool build    = 1 CU       (LLM generation + validation + deploy)
//   - 1 tool invoke   = 0.1 CU     (sandboxed execution, avg ~2s)
//   - 1 search query  = 0.05 CU    (multi-query expansion + fetch)
//
// Usage-based: $0.01 / CU
// Prepaid:     volume discount — more you buy, cheaper per CU
//
// TAM math:
//   ~2M AI-enabled dev teams × avg $200/mo = $4.8B addressable
//   1% capture year 1 = $48M ARR → strong Series A story
//   Agent proliferation (10B+ daily tool calls by 2028) = $36B ceiling
// =============================================================================

const plans = [
  {
    name: "Pay As You Go",
    price: "$0.015",
    period: "/ CU",
    cu: "No minimum",
    cuNum: 0,
    description: "For prototyping and personal projects",
    cta: "Get Started",
    ctaStyle: "border border-white/20 text-white hover:bg-white/5",
    features: [
      "No monthly fee",
      "$0.015 / CU, pay for what you use",
      "5 concurrent tools",
      "Community support",
      "Standard sandbox (30s timeout)",
      "API access",
    ],
  },
  {
    name: "Pro",
    price: "$49",
    period: "/mo",
    cu: "10,000",
    cuNum: 10000,
    description: "For teams shipping AI-powered products",
    cta: "Start Trial",
    ctaStyle: "bg-rose-500 text-white hover:bg-rose-600",
    popular: true,
    features: [
      "10,000 CU included",
      "Then $0.008 / CU",
      "Unlimited concurrent tools",
      "Priority support",
      "Extended sandbox (60s timeout)",
      "Usage dashboard",
      "Team seats (up to 5)",
    ],
  },
];

const computePacks = [
  { cu: "10K", price: 80, perCU: 0.008, discount: "20%", popular: false },
  { cu: "100K", price: 600, perCU: 0.006, discount: "40%", popular: true },
  { cu: "500K", price: 2_000, perCU: 0.004, discount: "60%", popular: false },
  { cu: "1M", price: 3_000, perCU: 0.003, discount: "70%", popular: false },
  { cu: "5M", price: 10_000, perCU: 0.002, discount: "80%", popular: false },
];

const cuBreakdown = [
  { action: "Tool Build", cu: "1 CU", desc: "AI generates, validates, and deploys a tool", cost: "$0.015" },
  { action: "Tool Invoke", cu: "0.1 CU", desc: "Execute a tool in a sandboxed environment", cost: "$0.0015" },
  { action: "Search Query", cu: "0.05 CU", desc: "AI-optimized multi-query web search", cost: "$0.00075" },
  { action: "Tool Rebuild", cu: "0.5 CU", desc: "Modify an existing tool with new instructions", cost: "$0.0075" },
];

const faqs = [
  {
    q: "What is a Compute Unit (CU)?",
    a: "A CU is our universal billing unit. Different operations cost different amounts of CU — a tool build costs 1 CU, an invocation costs 0.1 CU, and a search query costs 0.05 CU. On Pay As You Go the rate is $0.015/CU. Pro gets a lower $0.008 overage rate.",
  },
  {
    q: "Do unused CU roll over?",
    a: "Prepaid compute packs never expire. Monthly plan CU reset each billing cycle but prepaid packs are always available until depleted.",
  },
  {
    q: "What happens if I exceed my plan's included CU?",
    a: "On Pro, additional usage is billed at $0.008 / CU. On Pay As You Go, you're always billed at $0.015 / CU with no caps.",
  },
  {
    q: "Can I mix prepaid packs with a monthly plan?",
    a: "Yes. Prepaid CU are consumed first, then your plan's included CU, then overage rates apply. Prepaid packs also work with Pay As You Go — a great way to get volume discounts without a monthly commitment.",
  },
  {
    q: "Is there a rate limit?",
    a: "Pay As You Go: 10 req/s. Pro: 100 req/s. Need more? Contact us about enterprise plans.",
  },
  {
    q: "What's your uptime guarantee?",
    a: "We target high availability across both plans. Enterprise arrangements with formal SLAs are available — contact us.",
  },
];

export default function PricingPage() {
  const [expandedFaq, setExpandedFaq] = useState<number | null>(null);
  const [checkoutLoading, setCheckoutLoading] = useState<string | null>(null);
  const router = useRouter();

  const handlePlanClick = async (planName: string) => {
    const productMap: Record<string, string> = {
      "Pay As You Go": "paygo",
      Pro: "pro",
    };
    const productId = productMap[planName];
    if (!productId) return;

    // Pay As You Go: just go to signup — no checkout needed
    if (planName === "Pay As You Go") {
      router.push("/signup");
      return;
    }

    // Paid plans: need auth first
    if (!isAuthenticated()) {
      router.push(`/signup?plan=${productId}`);
      return;
    }

    // Create checkout session
    setCheckoutLoading(planName);
    try {
      const successUrl = `${window.location.origin}/dashboard?upgraded=1`;
      const cancelUrl = `${window.location.origin}/pricing`;
      const res = await createCheckout(productId, successUrl, cancelUrl);
      if (res.checkout_url) {
        window.location.href = res.checkout_url;
      } else if (res.error) {
        alert(res.error);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Checkout failed";
      alert(msg);
    } finally {
      setCheckoutLoading(null);
    }
  };

  return (
    <main className="min-h-screen bg-gray-950">
      <Navigation />

      <div className="pt-32 pb-24">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          {/* Header */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="text-center mb-6"
          >
            <p className="text-xs font-semibold tracking-[0.2em] text-rose-400 uppercase mb-4">
              Pricing
            </p>
            <h1
              className="text-5xl sm:text-6xl lg:text-7xl text-white mb-6"
              style={{ fontFamily: "var(--font-instrument), Georgia, serif" }}
            >
              Pay for what you use
            </h1>
            <p className="text-lg text-white/50 max-w-2xl mx-auto leading-relaxed">
              Start free. Scale with usage-based pricing or buy compute packs at a discount.
              No surprises, no hidden fees.
            </p>
          </motion.div>

          {/* Plan Cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-px bg-white/[0.06] mb-32 mt-16">
            {plans.map((plan, index) => {
              const displayPrice = plan.price;

              return (
                <motion.div
                  key={plan.name}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: index * 0.1 }}
                  className={`relative bg-gray-950 p-8 lg:p-10 ${
                    plan.popular ? "ring-1 ring-rose-500/40" : ""
                  }`}
                >
                  {plan.popular && (
                    <div className="absolute top-0 left-0 right-0 h-px bg-rose-500" />
                  )}

                  <div className="mb-8">
                    {plan.popular && (
                      <span className="text-[10px] font-mono uppercase tracking-widest text-rose-400 mb-3 block">
                        Most Popular
                      </span>
                    )}
                    <h3
                      className="text-2xl text-white mb-2"
                      style={{ fontFamily: "var(--font-instrument), Georgia, serif" }}
                    >
                      {plan.name}
                    </h3>
                    <p className="text-white/40 text-sm">{plan.description}</p>
                  </div>

                  <div className="mb-8">
                    <div className="flex items-baseline gap-1">
                      <span className="text-5xl text-white font-light">{displayPrice}</span>
                      {plan.period !== "forever" && (
                        <span className="text-white/40 text-sm">{plan.period}</span>
                      )}
                    </div>
                    <p className="text-white/30 text-xs font-mono mt-2">
                      {plan.cu} CU included
                    </p>
                  </div>

                  <button
                    onClick={() => handlePlanClick(plan.name)}
                    disabled={checkoutLoading === plan.name}
                    className={`block w-full text-center py-3 text-sm font-medium uppercase tracking-wider transition-colors mb-8 disabled:opacity-50 ${plan.ctaStyle}`}
                  >
                    {checkoutLoading === plan.name ? "Loading..." : plan.cta}
                  </button>

                  <ul className="space-y-3">
                    {plan.features.map((feature) => (
                      <li key={feature} className="flex items-start gap-3 text-sm text-white/60">
                        <svg className="w-4 h-4 text-white/30 mt-0.5 shrink-0" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                        </svg>
                        {feature}
                      </li>
                    ))}
                  </ul>
                </motion.div>
              );
            })}
          </div>

          {/* CU Breakdown */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="mb-32"
          >
            <div className="max-w-3xl mb-12">
              <p className="text-xs font-semibold tracking-[0.2em] text-rose-400 uppercase mb-4">
                How it works
              </p>
              <h2
                className="text-4xl sm:text-5xl text-white mb-4"
                style={{ fontFamily: "var(--font-instrument), Georgia, serif" }}
              >
                One unit, every action
              </h2>
              <p className="text-lg text-white/50">
                Every API call maps to Compute Units. Use your budget however you want — 
                heavy on builds, heavy on invocations, or a mix of both.
              </p>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-px bg-white/[0.06]">
              {cuBreakdown.map((item, index) => (
                <motion.div
                  key={item.action}
                  initial={{ opacity: 0, y: 10 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true }}
                  transition={{ delay: index * 0.05 }}
                  className="bg-gray-950 p-6 lg:p-8"
                >
                  <span className="text-xs font-mono text-white/30 block mb-4">
                    {String(index + 1).padStart(2, "0")}
                  </span>
                  <p className="text-3xl text-white font-light mb-1">{item.cu}</p>
                  <h4
                    className="text-lg text-white mb-2"
                    style={{ fontFamily: "var(--font-instrument), Georgia, serif" }}
                  >
                    {item.action}
                  </h4>
                  <p className="text-white/40 text-sm leading-relaxed mb-3">{item.desc}</p>
                  <p className="text-xs font-mono text-white/30">
                    {item.cost} at usage rate
                  </p>
                </motion.div>
              ))}
            </div>
          </motion.div>

          {/* Compute Packs */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="mb-32"
          >
            <div className="max-w-3xl mb-12">
              <p className="text-xs font-semibold tracking-[0.2em] text-rose-400 uppercase mb-4">
                Compute Packs
              </p>
              <h2
                className="text-4xl sm:text-5xl text-white mb-4"
                style={{ fontFamily: "var(--font-instrument), Georgia, serif" }}
              >
                Buy in bulk, pay less
              </h2>
              <p className="text-lg text-white/50">
                Prepaid compute packs never expire. The more you buy, the lower your effective cost per CU.
                Stack with any plan.
              </p>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-px bg-white/[0.06]">
              {computePacks.map((pack, index) => (
                <motion.div
                  key={pack.cu}
                  initial={{ opacity: 0, y: 10 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true }}
                  transition={{ delay: index * 0.05 }}
                  className={`relative bg-gray-950 p-6 group hover:bg-gray-900 transition-colors ${
                    pack.popular ? "ring-1 ring-rose-500/40" : ""
                  }`}
                >
                  {pack.popular && (
                    <div className="absolute top-0 left-0 right-0 h-px bg-rose-500" />
                  )}
                  {pack.popular && (
                    <span className="text-[10px] font-mono uppercase tracking-widest text-rose-400 mb-2 block">
                      Best Value
                    </span>
                  )}
                  <p className="text-3xl text-white font-light mb-1">{pack.cu}</p>
                  <p className="text-xs font-mono text-white/30 mb-4">compute units</p>
                  <p className="text-2xl text-white mb-1">${pack.price.toLocaleString()}</p>
                  <p className="text-xs font-mono text-white/40 mb-3">
                    ${pack.perCU.toFixed(3)} / CU
                  </p>
                  <span className="inline-block text-[10px] font-mono uppercase tracking-wider text-emerald-400 border border-emerald-400/20 px-2 py-0.5">
                    {pack.discount} off
                  </span>
                </motion.div>
              ))}
            </div>

            {/* Volume CTA */}
            <div className="mt-8 p-6 border border-white/[0.06] bg-white/[0.02] flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
              <div>
                <p className="text-white text-sm font-medium">Need more than 5M CU?</p>
                <p className="text-white/40 text-sm">Enterprise pricing with custom SLAs, dedicated infrastructure, and volume discounts.</p>
              </div>
              <a
                href="mailto:hello@foundry.ai"
                className="px-6 py-3 text-sm font-medium uppercase tracking-wider border border-white/20 text-white hover:bg-white/5 transition-colors shrink-0"
              >
                Talk to Sales
              </a>
            </div>
          </motion.div>

          {/* Comparison Table */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="mb-32"
          >
            <h2
              className="text-3xl text-white mb-8"
              style={{ fontFamily: "var(--font-instrument), Georgia, serif" }}
            >
              Compare plans
            </h2>

            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-white/[0.08]">
                    <th className="text-left text-white/40 font-mono uppercase tracking-wider text-xs py-4 pr-4">Feature</th>
                    <th className="text-center text-white/40 font-mono uppercase tracking-wider text-xs py-4 px-4">Pay As You Go</th>
                    <th className="text-center text-white font-mono uppercase tracking-wider text-xs py-4 px-4">Pro</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/[0.04]">
                  {[
                    { feature: "Included CU / month", paygo: "None", pro: "10,000" },
                    { feature: "Rate / CU", paygo: "$0.015", pro: "$0.008 overage" },
                    { feature: "Concurrent tools", paygo: "5", pro: "Unlimited" },
                    { feature: "Sandbox timeout", paygo: "30s", pro: "60s" },
                    { feature: "Rate limit", paygo: "10 req/s", pro: "100 req/s" },
                    { feature: "Team seats", paygo: "1", pro: "5" },
                    { feature: "Support", paygo: "Community", pro: "Priority" },
                    { feature: "Usage dashboard", paygo: "\u2014", pro: "\u2713" },
                  ].map((row) => (
                    <tr key={row.feature}>
                      <td className="text-white/60 py-3 pr-4">{row.feature}</td>
                      <td className="text-center text-white/40 py-3 px-4">{row.paygo}</td>
                      <td className="text-center text-white py-3 px-4">{row.pro}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </motion.div>

          {/* FAQs */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
          >
            <h2
              className="text-3xl text-white mb-8"
              style={{ fontFamily: "var(--font-instrument), Georgia, serif" }}
            >
              Frequently asked questions
            </h2>

            <div className="space-y-px bg-white/[0.04]">
              {faqs.map((faq, index) => (
                <div key={index} className="bg-gray-950">
                  <button
                    onClick={() => setExpandedFaq(expandedFaq === index ? null : index)}
                    className="w-full flex items-center justify-between p-5 text-left"
                  >
                    <span className="text-white text-sm font-medium">{faq.q}</span>
                    <svg
                      className={`w-4 h-4 text-white/30 shrink-0 transition-transform ${expandedFaq === index ? "rotate-180" : ""}`}
                      fill="none"
                      viewBox="0 0 24 24"
                      strokeWidth={2}
                      stroke="currentColor"
                    >
                      <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5" />
                    </svg>
                  </button>
                  {expandedFaq === index && (
                    <motion.div
                      initial={{ opacity: 0, height: 0 }}
                      animate={{ opacity: 1, height: "auto" }}
                      className="px-5 pb-5"
                    >
                      <p className="text-white/50 text-sm leading-relaxed">{faq.a}</p>
                    </motion.div>
                  )}
                </div>
              ))}
            </div>
          </motion.div>
        </div>
      </div>

      <Footer />
    </main>
  );
}
