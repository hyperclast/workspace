/**
 * Yjs Collaboration Setup
 * Integrates Yjs CRDT with CodeMirror for real-time collaborative editing
 */
import { yCollab } from "y-codemirror.next";
import { WebsocketProvider } from "y-websocket";
import * as Y from "yjs";
import { WS_HOST } from "./config.js";

/**
 * Create collaboration objects for a page.
 * This should be called BEFORE creating the editor view.
 * @param {string} pageExternalId - The page's external_id (used as room identifier)
 * @param {string} userEmail - Email of the authenticated user
 * @returns {Object} - { ydoc, provider, ytext, awareness, extension, syncPromise } for use in editor
 */
export function createCollaborationObjects(pageExternalId, userEmail = "Anonymous") {
  // Create a new Yjs document
  const ydoc = new Y.Doc();

  // Get the shared text type (this will sync across all clients)
  const ytext = ydoc.getText("codemirror");

  // Determine WebSocket URL based on environment
  const wsProtocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const wsUrl = `${wsProtocol}//${WS_HOST}/ws/pages/${pageExternalId}`;

  console.log("Connecting to WebSocket:", wsUrl);

  // Create WebSocket provider for syncing
  // Pass empty string as room name since the room ID is already in the URL path
  const provider = new WebsocketProvider(wsUrl, "", ydoc, {
    connect: true,
  });

  // Setup awareness (for showing who's online, cursors, etc.)
  const awareness = provider.awareness;

  // Set local user info
  awareness.setLocalStateField("user", {
    name: userEmail,
    color: getRandomColor(),
  });

  // Listen to provider events
  provider.on("status", ({ status }) => {
    console.log("WebSocket status:", status); // 'connecting' | 'connected' | 'disconnected'
    if (status === "disconnected") {
      // Log stack trace to see what triggered the disconnect
      console.log("WebSocket disconnected - stack trace:", new Error().stack);
    }
  });

  // Track connection close reasons
  provider.on("connection-close", (event) => {
    console.log("WebSocket connection-close event:", {
      code: event?.code,
      reason: event?.reason,
      wasClean: event?.wasClean,
    });
  });

  // Track connection errors
  provider.on("connection-error", (error) => {
    console.error("WebSocket connection-error:", error);
  });

  // Track sync state for the caller
  let syncResolved = false;

  // Create a promise that resolves when first sync completes
  const syncPromise = new Promise((resolve) => {
    // Check if already synced (unlikely but possible)
    if (provider.synced) {
      console.log("Already synced, ytext.length=" + ytext.length);
      syncResolved = true;
      resolve({ synced: true, ytextHasContent: ytext.length > 0 });
      return;
    }

    const onSync = (isSynced) => {
      console.log("Sync status:", isSynced ? "synced" : "syncing", "ytext.length=" + ytext.length);
      if (isSynced && !syncResolved) {
        syncResolved = true;
        provider.off("sync", onSync);
        resolve({ synced: true, ytextHasContent: ytext.length > 0 });
      }
    };

    provider.on("sync", onSync);

    // Fallback timeout - resolve but indicate sync didn't complete
    setTimeout(() => {
      if (!syncResolved) {
        console.warn("Sync timeout after 2s - provider.synced=" + provider.synced);
        syncResolved = true;
        provider.off("sync", onSync);
        resolve({ synced: false, ytextHasContent: ytext.length > 0 });
      }
    }, 2000);
  });

  // Listen to awareness changes (who joined/left)
  awareness.on("change", () => {
    const states = awareness.getStates();
    console.log("Awareness changed, total users:", states.size);
  });

  // Listen for custom messages (like access revocation, links updated)
  // The WebSocket provider exposes the underlying WebSocket
  provider.ws?.addEventListener("message", (event) => {
    // Check if this is a text message (not binary Yjs sync message)
    if (typeof event.data === "string") {
      try {
        const message = JSON.parse(event.data);
        if (message.type === "access_revoked") {
          console.warn("Access to this page has been revoked");
          window.dispatchEvent(new CustomEvent("pageAccessRevoked", {
            detail: { pageId: pageExternalId, message: message.message }
          }));
        } else if (message.type === "links_updated") {
          console.log("Links updated notification received for page:", message.page_id);
          window.dispatchEvent(new CustomEvent("linksUpdated", {
            detail: { pageId: message.page_id }
          }));
        }
      } catch (e) {
        // Not a JSON message, ignore
      }
    }
  });

  console.log("Collaboration objects created for page:", pageExternalId);

  // Return objects for use in editor and cleanup
  // Extension is created lazily after sync completes to ensure ytext has content
  let _extension = null;
  return {
    ydoc,
    provider,
    ytext,
    awareness,
    get extension() {
      if (!_extension) {
        _extension = yCollab(ytext, awareness);
        console.log("yCollab extension created, ytext.length=" + ytext.length);
      }
      return _extension;
    },
    syncPromise, // Caller can await this for sync to complete
  };
}

/**
 * Cleanup collaboration resources.
 * Call this when closing a page.
 */
export function destroyCollaboration(collabObjects) {
  if (!collabObjects) return;

  const { provider, ydoc } = collabObjects;

  if (provider) {
    provider.destroy();
    console.log("WebSocket provider destroyed");
  }

  if (ydoc) {
    ydoc.destroy();
    console.log("Yjs document destroyed");
  }
}

/**
 * Generate a random color for user awareness.
 */
function getRandomColor() {
  const colors = [
    "#FF6B6B",
    "#4ECDC4",
    "#45B7D1",
    "#FFA07A",
    "#98D8C8",
    "#F7DC6F",
    "#BB8FCE",
    "#85C1E2",
    "#F8B739",
    "#52B788",
  ];
  return colors[Math.floor(Math.random() * colors.length)];
}
