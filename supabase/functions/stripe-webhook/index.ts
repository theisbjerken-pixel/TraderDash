// Future Stripe webhook. Paid plans are not applied in this version.
//
// Stripe POSTs the raw body here. The function does not read a Streamlit
// session. The account is identified later by the internal user id in
// client_reference_id or metadata.user_id, never by email alone.
//
// ENTITLEMENT_UPDATES_ENABLED stays false until Stripe test products exist.
// A valid signature is answered with 503 and is not stored, so an early
// delivery cannot be marked done before a plan is allowed to change.

import { createClient, type SupabaseClient } from "npm:@supabase/supabase-js@2";

const ENTITLEMENT_UPDATES_ENABLED = false;
const SIGNATURE_TOLERANCE_SECONDS = 300;
const USER_ID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

type StripeObject = {
  client_reference_id?: unknown;
  metadata?: { user_id?: unknown; email?: unknown };
};

type StripeEvent = {
  id?: unknown;
  type?: unknown;
  data?: { object?: StripeObject };
};

Deno.serve(async (request: Request): Promise<Response> => {
  if (request.method !== "POST") {
    return json({ received: false }, 405);
  }

  const rawBody = await request.text();
  const secret = Deno.env.get("STRIPE_WEBHOOK_SECRET") ?? "";
  if (!secret) {
    return json({ received: false, entitlement_updated: false }, 503);
  }

  const valid = await verifyStripeSignature(
    rawBody,
    request.headers.get("stripe-signature"),
    secret,
  );
  if (!valid) {
    return json({ received: false }, 400);
  }

  if (!ENTITLEMENT_UPDATES_ENABLED) {
    return json({ received: false, entitlement_updated: false }, 503);
  }

  return await recordVerifiedEvent(rawBody);
});

export function traderDashUserId(event: StripeEvent): string | null {
  const object = event.data?.object;
  if (!object) {
    return null;
  }
  const reference = typeof object.client_reference_id === "string" ? object.client_reference_id : "";
  const fromMetadata = typeof object.metadata?.user_id === "string" ? object.metadata.user_id : "";
  const candidate = reference || fromMetadata;
  if (!USER_ID.test(candidate)) {
    return null;
  }
  return candidate;
}

async function recordVerifiedEvent(rawBody: string): Promise<Response> {
  let event: StripeEvent;
  try {
    event = JSON.parse(rawBody) as StripeEvent;
  } catch {
    return json({ received: false }, 400);
  }

  const eventId = typeof event.id === "string" ? event.id : "";
  const eventType = typeof event.type === "string" ? event.type : "";
  if (!eventId || !eventType) {
    return json({ received: false }, 400);
  }

  // Resolved for the future Checkout mapping. Email is not consulted.
  traderDashUserId(event);

  const supabase = supabaseClient();
  if (!supabase) {
    return json({ received: false, entitlement_updated: false }, 503);
  }

  const inserted = await insertStripeEvent(supabase, eventId, eventType);
  if (inserted === "duplicate") {
    return json({ received: true, duplicate: true, entitlement_updated: false }, 200);
  }
  if (inserted === "failed") {
    return json({ received: false, entitlement_updated: false }, 500);
  }

  // The users table is intentionally not updated here.
  return json({ received: true, entitlement_updated: false }, 200);
}

function supabaseClient(): SupabaseClient | null {
  const url = Deno.env.get("SUPABASE_URL") ?? "";
  const serviceRoleKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "";
  if (!url || !serviceRoleKey) {
    return null;
  }
  return createClient(url, serviceRoleKey, {
    auth: { persistSession: false, autoRefreshToken: false },
  });
}

async function insertStripeEvent(
  supabase: SupabaseClient,
  eventId: string,
  eventType: string,
): Promise<"inserted" | "duplicate" | "failed"> {
  const { error } = await supabase.from("stripe_events").insert({
    stripe_event_id: eventId,
    event_type: eventType,
    processed_at: new Date().toISOString(),
    processing_status: "received",
    error_message: null,
  });
  if (!error) {
    return "inserted";
  }
  if (error.code === "23505") {
    return "duplicate";
  }
  return "failed";
}

async function verifyStripeSignature(
  rawBody: string,
  header: string | null,
  secret: string,
): Promise<boolean> {
  const parsed = parseSignature(header);
  if (!parsed) {
    return false;
  }
  const timestamp = Number(parsed.timestamp);
  if (!Number.isFinite(timestamp)) {
    return false;
  }
  const age = Math.abs(Math.floor(Date.now() / 1000) - timestamp);
  if (age > SIGNATURE_TOLERANCE_SECONDS) {
    return false;
  }

  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const signed = await crypto.subtle.sign(
    "HMAC",
    key,
    new TextEncoder().encode(`${parsed.timestamp}.${rawBody}`),
  );
  const expected = toHex(new Uint8Array(signed));
  return parsed.signatures.some((signature) => safeEqual(signature, expected));
}

function parseSignature(header: string | null): { timestamp: string; signatures: string[] } | null {
  if (!header) {
    return null;
  }
  let timestamp = "";
  const signatures: string[] = [];
  for (const part of header.split(",")) {
    const separator = part.indexOf("=");
    if (separator === -1) {
      continue;
    }
    const key = part.slice(0, separator).trim();
    const value = part.slice(separator + 1).trim();
    if (key === "t") {
      timestamp = value;
    } else if (key === "v1" && value) {
      signatures.push(value);
    }
  }
  if (!timestamp || signatures.length === 0) {
    return null;
  }
  return { timestamp, signatures };
}

function toHex(bytes: Uint8Array): string {
  return [...bytes].map((value) => value.toString(16).padStart(2, "0")).join("");
}

function safeEqual(left: string, right: string): boolean {
  if (left.length !== right.length) {
    return false;
  }
  let difference = 0;
  for (let index = 0; index < left.length; index += 1) {
    difference |= left.charCodeAt(index) ^ right.charCodeAt(index);
  }
  return difference === 0;
}

function json(body: Record<string, boolean>, status: number): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}
