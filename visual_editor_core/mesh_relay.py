"""
Mesh Relay — Distributed VPyD Instance Interconnect.

Turns N independent VPyD instances into a distributed execution fabric
by reserving half the Python engine's slots as relay lanes:

    Python (a) has 64 slots:
        a1  .. a32   = USER slots   (your code lives here)
        a33 .. a48   = OUTBOUND relay lanes (push local output to remote peers)
        a49 .. a64   = INBOUND  relay lanes (receive data from remote peers)

Each relay lane is a lightweight Python snippet auto-committed by the mesh.
Outbound lanes periodically read a local slot's output buffer and POST it
to a peer's inbound lane via the existing /api/registry/slot/<id>/push API.
Inbound lanes accumulate data from peers and make it readable by local slots.

Topology:
    - Star:  one MASTER instance, N-1 workers relay through it
    - Mesh:  every instance knows every other (full mesh)
    - Ring:  each instance relays to the next in a ring
    - Custom: user loads a marshal snippet that orchestrates

The mesh is a PROOF OF CONCEPT.  No consensus protocol, no partition
tolerance, no encryption.  It's a plumbing demo showing that the
slot/permission/push architecture already supports distribution.

Usage:
    mesh = MeshRelay(node_registry, session_ledger)
    mesh.add_peer('node-2', 'http://192.168.1.102:5002')
    mesh.add_peer('node-3', 'http://192.168.1.103:5002')
    mesh.activate()   # auto-commits relay snippets into a33..a64
"""

import time
import json
import threading
import uuid
import requests
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum


# ─── Constants ───────────────────────────────────────────────────────
OUTBOUND_START = 33   # a33 .. a48  (16 outbound lanes)
OUTBOUND_END   = 48
INBOUND_START  = 49   # a49 .. a64  (16 inbound lanes)
INBOUND_END    = 64
MAX_PEERS      = 10
RELAY_ENGINE   = 'PYTHON'     # Engine row used for relay slots
RELAY_LETTER   = 'a'

USER_SLOT_END  = 32   # a1..a32 remain for user code


class MeshRole(Enum):
    MASTER  = 'master'
    WORKER  = 'worker'
    PEER    = 'peer'       # full-mesh mode — everyone is equal


class MeshTopology(Enum):
    STAR = 'star'
    MESH = 'mesh'
    RING = 'ring'


@dataclass
class PeerInfo:
    """A remote VPyD instance."""
    peer_id: str                   # e.g., 'node-2'
    url: str                       # e.g., 'http://192.168.1.102:5002'
    role: MeshRole = MeshRole.PEER
    outbound_lane: int = 0         # local slot position used to push TO this peer
    inbound_lane: int = 0          # local slot position used to receive FROM this peer
    last_heartbeat: float = 0.0
    is_alive: bool = False
    latency_ms: float = 0.0
    slot_count: int = 0            # how many occupied slots the peer reports
    peer_instance_id: str = ''     # UUID the peer advertises


@dataclass
class MeshState:
    """Current state of the mesh fabric."""
    instance_id: str = ''
    instance_name: str = ''
    role: MeshRole = MeshRole.PEER
    topology: MeshTopology = MeshTopology.MESH
    peers: Dict[str, PeerInfo] = field(default_factory=dict)
    active: bool = False
    activated_at: float = 0.0
    heartbeat_interval_sec: float = 10.0
    relay_interval_sec: float = 5.0
    outbound_mappings: Dict[str, str] = field(default_factory=dict)  # local_addr -> peer_id
    inbound_mappings: Dict[str, str] = field(default_factory=dict)   # local_addr -> peer_id


class MeshRelay:
    """
    Manages the distributed mesh between VPyD instances.

    Each instance runs one MeshRelay.  When activated, it:
      1. Commits relay snippets into slots a33..a64
      2. Starts a heartbeat thread (pings peers)
      3. Starts a relay thread (pushes local output to peer inbound lanes)
    """

    def __init__(self, node_registry, session_ledger, instance_name: str = ''):
        self._registry = node_registry
        self._ledger = session_ledger
        self._lock = threading.RLock()

        # Identity
        self._state = MeshState(
            instance_id=str(uuid.uuid4())[:12],
            instance_name=instance_name or f'vpyd-{str(uuid.uuid4())[:6]}',
        )

        # Threads
        self._heartbeat_thread: Optional[threading.Thread] = None
        self._relay_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        # Relay subscriptions: which local slots forward to which peers
        # Key: local slot address (e.g., 'a5')
        # Value: list of peer_ids that should receive this slot's output
        self._subscriptions: Dict[str, List[str]] = {}

    # ─── Properties ──────────────────────────────────────────────────

    @property
    def instance_id(self) -> str:
        return self._state.instance_id

    @property
    def instance_name(self) -> str:
        return self._state.instance_name

    @property
    def is_active(self) -> bool:
        return self._state.active

    @property
    def peer_count(self) -> int:
        return len(self._state.peers)

    # ─── Peer Management ─────────────────────────────────────────────

    def add_peer(self, peer_id: str, url: str,
                 role: MeshRole = MeshRole.PEER) -> bool:
        """Register a remote VPyD instance as a peer."""
        with self._lock:
            if len(self._state.peers) >= MAX_PEERS:
                return False
            if peer_id in self._state.peers:
                return False

            # Assign relay lanes
            peer_index = len(self._state.peers)
            outbound_pos = OUTBOUND_START + peer_index   # a33, a34, a35, ...
            inbound_pos  = INBOUND_START  + peer_index   # a49, a50, a51, ...

            if outbound_pos > OUTBOUND_END or inbound_pos > INBOUND_END:
                return False  # out of relay lanes

            peer = PeerInfo(
                peer_id=peer_id,
                url=url.rstrip('/'),
                role=role,
                outbound_lane=outbound_pos,
                inbound_lane=inbound_pos,
            )
            self._state.peers[peer_id] = peer

            # Track the lane assignments
            out_addr = f"{RELAY_LETTER}{outbound_pos}"
            in_addr  = f"{RELAY_LETTER}{inbound_pos}"
            self._state.outbound_mappings[out_addr] = peer_id
            self._state.inbound_mappings[in_addr]   = peer_id

            return True

    def remove_peer(self, peer_id: str) -> bool:
        """Remove a peer (does NOT re-number other peers' lanes)."""
        with self._lock:
            peer = self._state.peers.pop(peer_id, None)
            if not peer:
                return False

            out_addr = f"{RELAY_LETTER}{peer.outbound_lane}"
            in_addr  = f"{RELAY_LETTER}{peer.inbound_lane}"
            self._state.outbound_mappings.pop(out_addr, None)
            self._state.inbound_mappings.pop(in_addr, None)

            # Clear the relay slots in the registry
            for addr in (out_addr, in_addr):
                slot = self._registry.get_slot_by_address(
                    RELAY_LETTER, int(addr[1:]))
                if slot and slot.slot_id:
                    self._registry.clear_slot(slot.slot_id)

            return True

    def get_peer(self, peer_id: str) -> Optional[PeerInfo]:
        return self._state.peers.get(peer_id)

    def list_peers(self) -> List[Dict[str, Any]]:
        return [
            {
                'peer_id': p.peer_id,
                'url': p.url,
                'role': p.role.value,
                'outbound_lane': f"{RELAY_LETTER}{p.outbound_lane}",
                'inbound_lane': f"{RELAY_LETTER}{p.inbound_lane}",
                'is_alive': p.is_alive,
                'latency_ms': round(p.latency_ms, 1),
                'last_heartbeat': p.last_heartbeat,
                'slot_count': p.slot_count,
                'instance_id': p.peer_instance_id,
            }
            for p in self._state.peers.values()
        ]

    # ─── Subscription Management ─────────────────────────────────────

    def subscribe_slot_to_peer(self, local_addr: str, peer_id: str) -> bool:
        """
        Subscribe a local slot's output to be forwarded to a peer.
        e.g., subscribe_slot_to_peer('a5', 'node-2') means:
        whenever a5 produces output, relay it to node-2's inbound lane.
        """
        with self._lock:
            if peer_id not in self._state.peers:
                return False
            self._subscriptions.setdefault(local_addr, [])
            if peer_id not in self._subscriptions[local_addr]:
                self._subscriptions[local_addr].append(peer_id)
            return True

    def unsubscribe_slot_from_peer(self, local_addr: str, peer_id: str) -> bool:
        with self._lock:
            subs = self._subscriptions.get(local_addr, [])
            if peer_id in subs:
                subs.remove(peer_id)
                return True
            return False

    # ─── Activation / Deactivation ───────────────────────────────────

    def activate(self) -> Dict[str, Any]:
        """
        Activate the mesh relay:
          1. Commit relay snippets into the Python engine's relay lanes
          2. Start heartbeat thread
          3. Start relay thread
        """
        with self._lock:
            if self._state.active:
                return {'already_active': True}

            self._state.active = True
            self._state.activated_at = time.time()

            # Commit relay lane marker nodes into the registry
            committed_lanes = self._commit_relay_lanes()

            # Start background threads
            self._stop_event.clear()

            self._heartbeat_thread = threading.Thread(
                target=self._heartbeat_loop, daemon=True,
                name='mesh-heartbeat')
            self._heartbeat_thread.start()

            self._relay_thread = threading.Thread(
                target=self._relay_loop, daemon=True,
                name='mesh-relay')
            self._relay_thread.start()

            return {
                'instance_id': self._state.instance_id,
                'instance_name': self._state.instance_name,
                'peers': len(self._state.peers),
                'relay_lanes_committed': committed_lanes,
                'topology': self._state.topology.value,
            }

    def deactivate(self) -> bool:
        """Stop the mesh relay and clear relay lanes."""
        with self._lock:
            if not self._state.active:
                return False

            self._state.active = False
            self._stop_event.set()

            # Wait for threads
            if self._heartbeat_thread and self._heartbeat_thread.is_alive():
                self._heartbeat_thread.join(timeout=5.0)
            if self._relay_thread and self._relay_thread.is_alive():
                self._relay_thread.join(timeout=5.0)

            # Clear relay slots
            self._clear_relay_lanes()
            return True

    # ─── Relay Lane Commitment ───────────────────────────────────────

    def _commit_relay_lanes(self) -> int:
        """
        Commit marker nodes into relay slot positions so the matrix
        shows them as occupied.  These are lightweight Python snippets
        that describe their relay function.
        """
        committed = 0

        for peer_id, peer in self._state.peers.items():
            # --- Outbound lane ---
            out_code = self._generate_outbound_snippet(peer)
            out_node_id = self._ensure_ledger_node(
                f"relay-out-{peer_id}",
                f"RELAY OUT -> {peer_id}",
                out_code
            )
            if out_node_id:
                slot = self._registry.commit_node(
                    out_node_id, RELAY_ENGINE, peer.outbound_lane)
                if slot:
                    committed += 1

            # --- Inbound lane ---
            in_code = self._generate_inbound_snippet(peer)
            in_node_id = self._ensure_ledger_node(
                f"relay-in-{peer_id}",
                f"RELAY IN <- {peer_id}",
                in_code
            )
            if in_node_id:
                slot = self._registry.commit_node(
                    in_node_id, RELAY_ENGINE, peer.inbound_lane)
                if slot:
                    committed += 1

        return committed

    def _clear_relay_lanes(self):
        """Clear all relay slots from the registry."""
        for pos in range(OUTBOUND_START, INBOUND_END + 1):
            slot = self._registry.get_slot_by_address(RELAY_LETTER, pos)
            if slot and slot.slot_id and slot.slot_id in self._registry._slot_index:
                self._registry.clear_slot(slot.slot_id)

    def _ensure_ledger_node(self, node_id_suffix: str, display_name: str,
                            code: str) -> Optional[str]:
        """
        Create or update a ledger node for a relay lane.
        Returns the node_id.
        """
        from visual_editor_core.session_ledger import LanguageID
        node_id = f"mesh-{self._state.instance_id}-{node_id_suffix}"

        # Check if node already exists
        existing = self._ledger.get_node_snapshot(node_id)
        if existing:
            # Update code if changed
            existing_code = ''
            if existing.code_versions:
                existing_code = existing.code_versions[-1].get('source_code', '')
            if existing_code != code:
                self._ledger.record_code_edit(node_id, code, reason='mesh-relay-update')
            return node_id

        # Create new node via the ledger's import mechanism
        self._ledger.record_node_imported(
            node_id=node_id,
            node_type='function',
            display_name=display_name,
            raw_name=node_id_suffix,
            source_code=code,
            source_language='python',
            source_file='mesh_relay',
            import_session_number=0,
            metadata={'mesh_relay': True, 'instance_id': self._state.instance_id},
        )
        return node_id

    def _generate_outbound_snippet(self, peer: PeerInfo) -> str:
        """Generate the Python relay code for an outbound lane."""
        return f'''# ── MESH RELAY: OUTBOUND -> {peer.peer_id} ──
# Auto-generated by MeshRelay.  Slot: a{peer.outbound_lane}
# Pushes subscribed local slot outputs to peer at {peer.url}
#
# This slot is managed by the mesh fabric.
# Do NOT edit manually — changes will be overwritten.

PEER_URL = "{peer.url}"
PEER_ID  = "{peer.peer_id}"
LANE     = "a{peer.outbound_lane}"
STATUS   = "active"
'''

    def _generate_inbound_snippet(self, peer: PeerInfo) -> str:
        """Generate the Python relay code for an inbound lane."""
        return f'''# ── MESH RELAY: INBOUND <- {peer.peer_id} ──
# Auto-generated by MeshRelay.  Slot: a{peer.inbound_lane}
# Receives data pushed from peer at {peer.url}
#
# Local slots can read this lane's input buffer to get
# data from the remote peer.

PEER_URL = "{peer.url}"
PEER_ID  = "{peer.peer_id}"
LANE     = "a{peer.inbound_lane}"
STATUS   = "active"
'''

    # ─── Heartbeat ───────────────────────────────────────────────────

    def _heartbeat_loop(self):
        """Periodically ping all peers to check liveness."""
        while not self._stop_event.is_set():
            for peer_id, peer in list(self._state.peers.items()):
                self._ping_peer(peer)
            self._stop_event.wait(self._state.heartbeat_interval_sec)

    def _ping_peer(self, peer: PeerInfo):
        """Ping a single peer and update its status."""
        try:
            t0 = time.time()
            resp = requests.get(
                f"{peer.url}/api/mesh/heartbeat",
                timeout=5.0,
                params={'from': self._state.instance_id}
            )
            elapsed = (time.time() - t0) * 1000
            if resp.status_code == 200:
                data = resp.json()
                peer.is_alive = True
                peer.latency_ms = elapsed
                peer.last_heartbeat = time.time()
                peer.slot_count = data.get('slot_count', 0)
                peer.peer_instance_id = data.get('instance_id', '')
            else:
                peer.is_alive = False
        except Exception:
            peer.is_alive = False
            peer.latency_ms = -1

    # ─── Data Relay ──────────────────────────────────────────────────

    def _relay_loop(self):
        """Periodically relay subscribed slot outputs to peers."""
        while not self._stop_event.is_set():
            self._do_relay_pass()
            self._stop_event.wait(self._state.relay_interval_sec)

    def _do_relay_pass(self):
        """
        One relay cycle:
        For each subscription (local_addr -> peer_ids), read the local
        slot's recent output and push it to each subscribed peer's
        inbound lane.
        """
        for local_addr, peer_ids in list(self._subscriptions.items()):
            # Find the local slot
            letter = local_addr[0]
            try:
                pos = int(local_addr[1:])
            except ValueError:
                continue

            slot = self._registry.get_slot_by_address(letter, pos)
            if not slot or not slot.slot_id:
                continue

            # Read recent output
            output = self._registry.read_slot_output(slot.slot_id, last_n=5)
            if not output:
                continue

            # Push to each subscribed peer's inbound lane
            for peer_id in peer_ids:
                peer = self._state.peers.get(peer_id)
                if not peer or not peer.is_alive:
                    continue

                # Find the peer's inbound slot_id on the REMOTE instance
                # We use the peer's push API with the inbound lane address
                try:
                    # Push to the remote peer's inbound relay lane
                    in_addr = f"{RELAY_LETTER}{peer.inbound_lane}"
                    requests.post(
                        f"{peer.url}/api/mesh/relay/push",
                        json={
                            'source_instance': self._state.instance_id,
                            'source_addr': local_addr,
                            'target_addr': in_addr,
                            'data': output,
                        },
                        timeout=5.0,
                    )
                except Exception:
                    pass  # best-effort relay

    # ─── Inbound Handler ─────────────────────────────────────────────

    def handle_inbound_push(self, source_instance: str, source_addr: str,
                            target_addr: str, data: Any) -> bool:
        """
        Called when a remote peer pushes data to one of our inbound lanes.
        Puts the data into the target slot's input buffer.
        """
        try:
            pos = int(target_addr.lstrip(RELAY_LETTER))
        except (ValueError, IndexError):
            return False

        if pos < INBOUND_START or pos > INBOUND_END:
            return False

        slot = self._registry.get_slot_by_address(RELAY_LETTER, pos)
        if not slot or not slot.slot_id:
            return False

        # Push into the slot's input buffer with source metadata
        return self._registry.push_to_slot(
            slot.slot_id,
            {
                'source_instance': source_instance,
                'source_addr': source_addr,
                'relayed_at': time.time(),
                'payload': data,
            },
            source_slot_id=f"remote:{source_instance}:{source_addr}"
        )

    # ─── Full Topology View ──────────────────────────────────────────

    def get_topology(self) -> Dict[str, Any]:
        """
        Build a complete view of the distributed mesh suitable for
        rendering in the runtime panel.
        """
        # Local matrix summary
        local_matrix = self._registry.get_matrix_summary()
        local_occupied = local_matrix.get('total_committed', 0)
        local_capacity = local_matrix.get('total_capacity', 0)

        # Build per-engine summary for the local instance
        local_engines = {}
        for ename, edata in local_matrix.get('engines', {}).items():
            slots = edata.get('slots', {})
            occupied = sum(1 for v in slots.values() if v is not None)
            relay_out = 0
            relay_in = 0
            for pos_str, sdata in slots.items():
                if sdata is None:
                    continue
                pos = int(pos_str)
                if OUTBOUND_START <= pos <= OUTBOUND_END:
                    relay_out += 1
                elif INBOUND_START <= pos <= INBOUND_END:
                    relay_in += 1
            local_engines[ename] = {
                'letter': edata.get('letter', '?'),
                'language': edata.get('language', '?'),
                'occupied': occupied,
                'max_slots': edata.get('max_slots', 16),
                'relay_out': relay_out,
                'relay_in': relay_in,
            }

        # Peer summaries
        peer_summaries = []
        for peer in self._state.peers.values():
            peer_summaries.append({
                'peer_id': peer.peer_id,
                'url': peer.url,
                'role': peer.role.value,
                'is_alive': peer.is_alive,
                'latency_ms': round(peer.latency_ms, 1),
                'slot_count': peer.slot_count,
                'outbound_lane': f"{RELAY_LETTER}{peer.outbound_lane}",
                'inbound_lane': f"{RELAY_LETTER}{peer.inbound_lane}",
                'instance_id': peer.peer_instance_id,
            })

        return {
            'mesh_active': self._state.active,
            'instance_id': self._state.instance_id,
            'instance_name': self._state.instance_name,
            'role': self._state.role.value,
            'topology': self._state.topology.value,
            'activated_at': self._state.activated_at,

            'local': {
                'occupied': local_occupied,
                'capacity': local_capacity,
                'user_slots': sum(
                    1 for e in local_matrix.get('engines', {}).values()
                    for pos_str, s in e.get('slots', {}).items()
                    if s is not None and int(pos_str) <= USER_SLOT_END
                ),
                'relay_out_slots': sum(e.get('relay_out', 0) for e in local_engines.values()),
                'relay_in_slots': sum(e.get('relay_in', 0) for e in local_engines.values()),
                'engines': local_engines,
            },

            'peers': peer_summaries,
            'subscriptions': dict(self._subscriptions),

            'fabric': {
                'outbound_range': f"a{OUTBOUND_START}-a{OUTBOUND_END}",
                'inbound_range': f"a{INBOUND_START}-a{INBOUND_END}",
                'user_range': f"a1-a{USER_SLOT_END}",
                'max_peers': MAX_PEERS,
            },
        }

    def get_remote_slots(self, peer_id: str) -> Optional[Dict[str, Any]]:
        """Fetch the full matrix from a remote peer (for the topology view)."""
        peer = self._state.peers.get(peer_id)
        if not peer or not peer.is_alive:
            return None

        try:
            resp = requests.get(
                f"{peer.url}/api/registry/matrix",
                timeout=5.0,
            )
            if resp.status_code == 200:
                return resp.json()
        except Exception:
            pass
        return None

    # ─── Serialization ───────────────────────────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        return {
            'instance_id': self._state.instance_id,
            'instance_name': self._state.instance_name,
            'role': self._state.role.value,
            'topology': self._state.topology.value,
            'active': self._state.active,
            'activated_at': self._state.activated_at,
            'heartbeat_interval_sec': self._state.heartbeat_interval_sec,
            'relay_interval_sec': self._state.relay_interval_sec,
            'peers': {
                pid: {
                    'url': p.url,
                    'role': p.role.value,
                    'outbound_lane': p.outbound_lane,
                    'inbound_lane': p.inbound_lane,
                }
                for pid, p in self._state.peers.items()
            },
            'subscriptions': dict(self._subscriptions),
        }
