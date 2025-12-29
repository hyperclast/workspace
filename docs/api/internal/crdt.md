# Real-Time Collaboration WebSocket

## Table of Contents

- [Overview](#overview)
- [WebSocket Connection](#websocket-connection)
- [Message Protocol](#message-protocol)
- [Access Revocation](#access-revocation)
- [Backend Implementation](#backend-implementation)

## Overview

Hyperclast uses WebSocket connections for real-time collaborative editing of pages.

**Technology Stack:**

- **Yjs**: CRDT (Conflict-free Replicated Data Type) library
- **pycrdt-websocket**: Django Channels consumer for Yjs sync
- **PostgreSQL**: Persistent storage (`y_updates` and `y_snapshots` tables)

**Key Features:**

- Real-time multi-user editing with automatic conflict resolution
- User presence awareness (cursors, active users)
- Persistent storage of all edit operations
- Access control at connection time

## WebSocket Connection

### URL Format

```
wss://{host}/ws/pages/{page_id}/
```

For local development (HTTP):

```
ws://localhost:9800/ws/pages/{page_id}/
```

### Path Parameters

- `page_id` (String, required): The note's `external_id`

### Authentication

**Required:** Session-based authentication

- User must be authenticated via Django session cookie
- Session cookie is automatically sent by browser
- Access is validated at connection time using the same permission model as the REST API

**Permission Check:**

The backend validates that the user has access to the page via org membership or as project editor before accepting the WebSocket connection.

### Connection Lifecycle

1. **Connect**: Client initiates WebSocket connection
2. **Auth Check**: Backend validates user session and page access (`can_access_page()`)
3. **Accept/Reject**:
   - If authorized: Connection accepted, user joins room
   - If unauthorized: Connection closed with code `4003`
4. **Sync**: Client and server exchange Yjs sync messages
5. **Disconnect**: User leaves room, connection cleaned up

## Message Protocol

### Binary Messages (Yjs Protocol)

The primary message format is the Yjs sync protocol. Messages are handled automatically by the Yjs library:

- **Sync Step 1**: Request current document state
- **Sync Step 2**: Send document state to requesting client
- **Update**: Incremental edit operations
- **Awareness**: User presence information (cursors, selections, user info)

### Text Messages (Custom Protocol)

In addition to binary Yjs messages, the server may send JSON text messages for custom events:

#### Access Revoked Message

Sent when a user's edit access to the page is removed.

**Format:**

```json
{
  "type": "access_revoked",
  "message": "Your access to this note has been revoked"
}
```

**Expected Client Behavior:**

1. Close the WebSocket connection
2. Close the editor view
3. Show a notification to the user
4. Redirect to the pages list or home page

### Connection Close Codes

Custom close codes used by the server:

- `4001` - Access revoked (user removed from org/project)
- `4003` - Unauthorized (failed authentication or permission check)

Standard WebSocket close codes also apply:

- `1000` - Normal closure
- `1001` - Going away (server shutdown, browser navigation)
- `1006` - Abnormal closure (connection lost)

## Access Revocation

When a user loses access to a page (removed from org or project), active WebSocket connections for that user are notified.

### Flow

1. User is removed from org membership or project editors
2. Backend sends message to Django Channels layer: `note_{uuid}.access_revoked`
3. All WebSocket consumers in that room receive the message
4. Each consumer checks if the revocation applies to their user
5. Matching consumers send `access_revoked` JSON message to client
6. Connection closed with code `4001`

### Implementation

**Backend:** `backend/collab/consumers.py:157` - `PageYjsConsumer.access_revoked()`

**Frontend:** `frontend/src/collaboration.js:69` - Listens for `access_revoked` messages and dispatches `noteAccessRevoked` event

## Backend Implementation

### Architecture

**WebSocket Consumer:** `backend/collab/consumers.py` - `PageYjsConsumer`

- Subclasses `pycrdt-websocket`'s `YjsConsumer`
- Handles authentication and permission checks
- Manages CRDT document lifecycle
- Persists updates to PostgreSQL

### Key Components

**1. Consumer** (`backend/collab/consumers.py`)

- `connect()` - Validates user access before accepting connection
- `make_ydoc()` - Creates and hydrates Yjs document from persisted updates
- `receive()` - Handles incoming Yjs protocol messages
- `disconnect()` - Writes snapshot and cleans up resources
- `access_revoked()` - Notifies user when access is removed

**2. YStore** (`backend/collab/ystore.py`)

- `PostgresYStore` - Implements pycrdt's `BaseYStore` interface
- `write()` - Appends CRDT updates to `y_updates` table
- `read()` - Streams all updates for a room in order
- `upsert_snapshot()` - Writes snapshot to `y_snapshots` table

**3. Permissions** (`backend/collab/permissions.py`)

- `can_access_page()` - Async function that checks if user has access via org/project

**4. Routing** (`backend/collab/routing.py`)

- WebSocket URL patterns for Django Channels

### Database Schema

**y_updates table:**

```sql
id BIGINT PRIMARY KEY AUTO INCREMENT
room_id VARCHAR(255)  -- "page_{uuid}"
yupdate BYTEA         -- Binary CRDT update
timestamp TIMESTAMPTZ
```

**y_snapshots table:**

```sql
room_id VARCHAR(255) PRIMARY KEY  -- "page_{uuid}"
snapshot BYTEA                    -- Binary CRDT snapshot
last_update_id BIGINT             -- Last update ID included in snapshot
timestamp TIMESTAMPTZ
```

### Frontend Integration

**File:** `frontend/src/collaboration.js`

Key exports:

- `createCollaborationObjects()` - Creates Yjs doc, WebSocket provider, and CodeMirror extension
- `destroyCollaboration()` - Cleanup function

Dependencies:

- `yjs` - CRDT implementation
- `y-websocket` - WebSocket sync provider
- `y-codemirror.next` - CodeMirror 6 integration

## Related Documentation

- [Pages API](./pages.md) - REST API for page CRUD operations
- [Authentication API](./auth.md) - Session-based authentication
- [Overview](./overview.md) - General API conventions
