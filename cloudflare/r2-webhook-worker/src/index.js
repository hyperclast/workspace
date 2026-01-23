/**
 * Cloudflare Worker that consumes R2 event notifications
 * and forwards them to the backend webhook endpoint.
 *
 * Configuration is via Cloudflare secrets (set per account):
 * - WEBHOOK_URL: The API endpoint to forward events to
 * - WEBHOOK_SECRET: Shared secret for HMAC signature verification
 */

// R2 event types that we process
const OBJECT_CREATE_EVENTS = ["PutObject", "CompleteMultipartUpload", "CopyObject"];
const OBJECT_DELETE_EVENTS = ["DeleteObject", "LifecycleDeletion"];

export default {
  async queue(batch, env) {
    for (const message of batch.messages) {
      const event = message.body;

      // R2 uses "action" field for event type (e.g., "PutObject", "DeleteObject")
      const eventAction = event.action;

      // Log incoming event for debugging
      console.log(`Received event: ${eventAction} for ${event.object?.key}`);

      // Skip if object key doesn't match our pattern
      if (!event.object?.key?.startsWith("users/")) {
        console.log(`Skipping non-user object: ${event.object?.key}`);
        message.ack();
        continue;
      }

      // Determine if this is a create or delete event
      const isCreateEvent = OBJECT_CREATE_EVENTS.includes(eventAction);
      const isDeleteEvent = OBJECT_DELETE_EVENTS.includes(eventAction);

      if (!isCreateEvent && !isDeleteEvent) {
        console.log(`Skipping unhandled event: ${eventAction}`);
        message.ack();
        continue;
      }

      try {
        // Normalize event payload for backend (R2 uses "action", backend expects "eventType")
        const normalizedEvent = {
          ...event,
          eventType: eventAction,
        };

        // Create HMAC signature for verification
        const payload = JSON.stringify(normalizedEvent);
        const signature = await this.createSignature(payload, env.WEBHOOK_SECRET);

        // Forward to backend API
        const response = await fetch(env.WEBHOOK_URL, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-Webhook-Signature": signature,
            "X-Request-Id": crypto.randomUUID(),
          },
          body: payload,
        });

        if (response.ok) {
          message.ack();
          console.log(`Processed ${eventAction}: ${event.object.key}`);
        } else if (response.status >= 400 && response.status < 500) {
          // Client error - don't retry
          message.ack();
          console.warn(`Client error for ${event.object.key}: ${response.status}`);
        } else {
          // Server error - retry
          message.retry();
          console.error(`Server error for ${event.object.key}: ${response.status}`);
        }
      } catch (error) {
        message.retry();
        console.error(`Network error for ${event.object.key}:`, error.message);
      }
    }
  },

  async createSignature(payload, secret) {
    const encoder = new TextEncoder();
    const key = await crypto.subtle.importKey(
      "raw",
      encoder.encode(secret),
      { name: "HMAC", hash: "SHA-256" },
      false,
      ["sign"]
    );
    const signature = await crypto.subtle.sign("HMAC", key, encoder.encode(payload));
    return Array.from(new Uint8Array(signature))
      .map((b) => b.toString(16).padStart(2, "0"))
      .join("");
  },
};
