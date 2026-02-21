import crypto from "crypto";

/**
 * Generate a Foundry API key.
 * Mirrors Python's generate_api_key() in src/api/keys.py exactly.
 * Format: fnd_{32 random bytes as hex} = 68 chars total
 */
export function generateApiKey(): {
  fullKey: string;
  prefix: string;
  keyHash: string;
} {
  const raw = crypto.randomBytes(32).toString("hex"); // 64 hex chars
  const fullKey = `fnd_${raw}`;
  const prefix = fullKey.slice(0, 12); // "fnd_" + 8 chars
  const keyHash = crypto
    .createHash("sha256")
    .update(fullKey)
    .digest("hex");

  return { fullKey, prefix, keyHash };
}
