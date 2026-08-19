/**
 * Lightweight client-side password hashing using the Web Crypto API
 * (salted SHA-256). This is a meaningful improvement over storing plain
 * text passwords, but it is NOT a substitute for a proper server-side
 * auth system.
 *
 * RECOMMENDED NEXT STEP (do this in Claude Code before going live):
 * Replace this with Supabase Auth (supabase.auth.signUp / signInWithPassword),
 * which handles hashing, sessions, and password resets on the server side
 * correctly. This file is a pragmatic bridge so the app works end-to-end
 * today without requiring an auth migration up front.
 */

function bufferToHex(buffer) {
  return Array.from(new Uint8Array(buffer))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

function randomSaltHex(bytes = 16) {
  const arr = new Uint8Array(bytes);
  crypto.getRandomValues(arr);
  return bufferToHex(arr.buffer);
}

async function sha256Hex(text) {
  const encoded = new TextEncoder().encode(text);
  const digest = await crypto.subtle.digest("SHA-256", encoded);
  return bufferToHex(digest);
}

/** Returns { hash, salt } for a freshly chosen password. */
export async function hashPassword(password) {
  const salt = randomSaltHex();
  const hash = await sha256Hex(`${salt}:${password}`);
  return { hash, salt };
}

/** Verifies a password attempt against a stored hash + salt. */
export async function verifyPassword(password, hash, salt) {
  if (!hash || !salt) return false;
  const attempt = await sha256Hex(`${salt}:${password}`);
  return attempt === hash;
}
