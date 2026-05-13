"""
Postgres advisory-lock helpers shared by writers to the Yjs CRDT store.

Multiple processes can write to `y_updates` for the same room: the
WebSocket consumer's seed path (`collab.consumers._seed_ydoc_from_page`)
and external writers like the REST/MCP path
(`collab.services.apply_text.apply_text_to_room`). Without coordination,
two writers racing on a freshly-empty room can each insert the same
content with different Yjs `clientID`s, and the CRDT merges them into
doubled text. Both writers serialize on the advisory key returned by
`advisory_lock_key_for_room` under the `SEED_LOCK_NAMESPACE` partition.
"""

import hashlib

# First argument to `pg_advisory_xact_lock(int4, int4)`. Partitions the
# advisory lock space by subsystem so unrelated callers cannot
# accidentally collide with the seed/external-writer locks.
SEED_LOCK_NAMESPACE = 1


def advisory_lock_key_for_room(room_id: str) -> int:
    """Hash `room_id` to a signed 32-bit int suitable for the second
    argument of `pg_advisory_xact_lock(int4, int4)`.

    Collisions in the 32-bit space cause spurious cross-room blocking
    bounded by one writer's transaction (a single-digit-ms wait); they
    never cause correctness loss because the in-lock recheck of
    `y_updates` is keyed by the real `room_id`, not the hash.
    """
    digest = hashlib.blake2s(room_id.encode("utf-8"), digest_size=4).digest()
    return int.from_bytes(digest, byteorder="big", signed=True)
