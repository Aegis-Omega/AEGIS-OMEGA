//! Gate 301 — Gossip Routing Table: per-peer next-hop route management with hash-chained audit (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Maintains a routing table mapping (destination_peer_id → next_hop_peer_id) for gossip overlay
//! routing. Each route insertion or removal is recorded as a hash-chained RouteRecord.
//! Routes carry a metric (hop count or cost, u8) used for best-route selection.
//!
//! Constants:
//!   MAX_ROUTES: usize = 256  (max entries in the routing table)
//!   METRIC_DIRECT: u8 = 1    (directly connected peer)
//!   METRIC_INFINITY: u8 = 255 (unreachable)
//!
//! RouteOperation: Insert | Update | Remove
//!
//! RouteRecord:
//!   epoch, destination, next_hop, metric, operation, record_hash, prev_hash
//!   record_hash = SHA-256(prev ‖ epoch_be8 ‖ dest_be4 ‖ hop_be4 ‖ metric ‖ op_byte)
//!
//! RouteLog: hash-chained RouteRecords.
//!   push(), insert_count(), remove_count(), update_count(), verify_chain().
//!
//! RoutingTable:
//!   insert(epoch, destination, next_hop, metric) — adds or updates route; records Insert/Update
//!   remove(epoch, destination) → bool            — removes route if present; records Remove
//!   lookup(destination) → Option<(next_hop, metric)>
//!   best_route(destination) — same as lookup; returns lowest-metric route for destination
//!   route_count() → usize
//!   all_routes() → Vec<(destination, next_hop, metric)>  (BTreeMap order)
//!   log: RouteLog

use sha2::{Sha256, Digest};
use std::collections::BTreeMap;

pub const MAX_ROUTES:      usize = 256;
pub const METRIC_DIRECT:   u8    = 1;
pub const METRIC_INFINITY: u8    = 255;

// ─── Route operation ──────────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum RouteOperation {
    Insert = 0,
    Update = 1,
    Remove = 2,
}

impl RouteOperation {
    pub fn op_byte(self) -> u8 { self as u8 }
}

// ─── Route record ─────────────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct RouteRecord {
    pub epoch:       u64,
    pub destination: u32,
    pub next_hop:    u32,
    pub metric:      u8,
    pub operation:   RouteOperation,
    pub record_hash: [u8; 32],
    pub prev_hash:   [u8; 32],
}

pub const ROUTE_GENESIS_HASH: [u8; 32] = [0u8; 32];

fn compute_route_hash(
    epoch:       u64,
    destination: u32,
    next_hop:    u32,
    metric:      u8,
    operation:   RouteOperation,
    prev:        &[u8; 32],
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch.to_be_bytes());
    h.update(destination.to_be_bytes());
    h.update(next_hop.to_be_bytes());
    h.update([metric, operation.op_byte()]);
    h.finalize().into()
}

pub fn build_route_record(
    epoch:       u64,
    destination: u32,
    next_hop:    u32,
    metric:      u8,
    operation:   RouteOperation,
    prev_hash:   &[u8; 32],
) -> RouteRecord {
    let record_hash = compute_route_hash(epoch, destination, next_hop, metric, operation, prev_hash);
    RouteRecord { epoch, destination, next_hop, metric, operation, record_hash, prev_hash: *prev_hash }
}

// ─── Route log ────────────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct RouteLog {
    records: Vec<RouteRecord>,
}

impl RouteLog {
    pub fn new() -> Self { Self { records: Vec::new() } }

    pub fn len(&self)      -> usize { self.records.len() }
    pub fn is_empty(&self) -> bool  { self.records.is_empty() }
    pub fn records(&self)  -> &[RouteRecord] { &self.records }

    pub fn last_hash(&self) -> [u8; 32] {
        self.records.last().map(|r| r.record_hash).unwrap_or(ROUTE_GENESIS_HASH)
    }

    pub fn push(
        &mut self,
        epoch:       u64,
        destination: u32,
        next_hop:    u32,
        metric:      u8,
        operation:   RouteOperation,
    ) -> &RouteRecord {
        let prev = self.last_hash();
        let r = build_route_record(epoch, destination, next_hop, metric, operation, &prev);
        self.records.push(r);
        self.records.last().unwrap()
    }

    pub fn insert_count(&self) -> usize {
        self.records.iter().filter(|r| r.operation == RouteOperation::Insert).count()
    }

    pub fn update_count(&self) -> usize {
        self.records.iter().filter(|r| r.operation == RouteOperation::Update).count()
    }

    pub fn remove_count(&self) -> usize {
        self.records.iter().filter(|r| r.operation == RouteOperation::Remove).count()
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut expected_prev = ROUTE_GENESIS_HASH;
        for (i, r) in self.records.iter().enumerate() {
            if r.prev_hash != expected_prev { return (false, Some(i)); }
            let recomputed = compute_route_hash(
                r.epoch, r.destination, r.next_hop, r.metric, r.operation, &r.prev_hash,
            );
            if recomputed != r.record_hash { return (false, Some(i)); }
            expected_prev = r.record_hash;
        }
        (true, None)
    }
}

impl Default for RouteLog {
    fn default() -> Self { Self::new() }
}

// ─── Routing table ────────────────────────────────────────────────────────────

/// Per-route entry stored in the table.
#[derive(Debug, Clone, Copy)]
struct RouteEntry {
    next_hop: u32,
    metric:   u8,
}

#[derive(Debug, Clone)]
pub struct RoutingTable {
    routes: BTreeMap<u32, RouteEntry>,
    pub log: RouteLog,
}

#[derive(Debug)]
pub enum RouteError {
    TableFull,
}

impl RoutingTable {
    pub fn new() -> Self { Self { routes: BTreeMap::new(), log: RouteLog::new() } }

    pub fn route_count(&self) -> usize { self.routes.len() }

    pub fn lookup(&self, destination: u32) -> Option<(u32, u8)> {
        self.routes.get(&destination).map(|e| (e.next_hop, e.metric))
    }

    /// Insert or update a route. Returns Err if table is full and this is a new destination.
    pub fn insert(
        &mut self,
        epoch:       u64,
        destination: u32,
        next_hop:    u32,
        metric:      u8,
    ) -> Result<(), RouteError> {
        let op = if self.routes.contains_key(&destination) {
            RouteOperation::Update
        } else {
            if self.routes.len() >= MAX_ROUTES {
                return Err(RouteError::TableFull);
            }
            RouteOperation::Insert
        };
        self.routes.insert(destination, RouteEntry { next_hop, metric });
        self.log.push(epoch, destination, next_hop, metric, op);
        Ok(())
    }

    /// Remove a route. Returns true if it existed.
    pub fn remove(&mut self, epoch: u64, destination: u32) -> bool {
        if let Some(entry) = self.routes.remove(&destination) {
            self.log.push(epoch, destination, entry.next_hop, entry.metric, RouteOperation::Remove);
            true
        } else {
            false
        }
    }

    /// All routes sorted by destination (BTreeMap order).
    pub fn all_routes(&self) -> Vec<(u32, u32, u8)> {
        self.routes.iter().map(|(&d, e)| (d, e.next_hop, e.metric)).collect()
    }
}

impl Default for RoutingTable {
    fn default() -> Self { Self::new() }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    // ── RouteOperation ────────────────────────────────────────────────────────

    #[test]
    fn op_bytes() {
        assert_eq!(RouteOperation::Insert.op_byte(), 0);
        assert_eq!(RouteOperation::Update.op_byte(), 1);
        assert_eq!(RouteOperation::Remove.op_byte(), 2);
    }

    // ── build_route_record ────────────────────────────────────────────────────

    #[test]
    fn record_hash_nonzero() {
        let r = build_route_record(1, 10, 20, 1, RouteOperation::Insert, &ROUTE_GENESIS_HASH);
        assert_ne!(r.record_hash, [0u8; 32]);
    }

    #[test]
    fn record_hash_deterministic() {
        let r1 = build_route_record(1, 10, 20, 1, RouteOperation::Insert, &ROUTE_GENESIS_HASH);
        let r2 = build_route_record(1, 10, 20, 1, RouteOperation::Insert, &ROUTE_GENESIS_HASH);
        assert_eq!(r1.record_hash, r2.record_hash);
    }

    // ── RouteLog ──────────────────────────────────────────────────────────────

    #[test]
    fn log_counts_operations() {
        let mut l = RouteLog::new();
        l.push(1, 10, 20, 1, RouteOperation::Insert);
        l.push(2, 10, 20, 2, RouteOperation::Update);
        l.push(3, 10, 20, 2, RouteOperation::Remove);
        assert_eq!(l.insert_count(), 1);
        assert_eq!(l.update_count(), 1);
        assert_eq!(l.remove_count(), 1);
    }

    #[test]
    fn log_chain_links() {
        let mut l = RouteLog::new();
        l.push(1, 10, 20, 1, RouteOperation::Insert);
        l.push(2, 11, 21, 2, RouteOperation::Insert);
        assert_eq!(l.records()[1].prev_hash, l.records()[0].record_hash);
    }

    #[test]
    fn log_verify_chain_valid() {
        let mut l = RouteLog::new();
        for i in 0..5u32 {
            l.push(i as u64, i, i + 1, 1, RouteOperation::Insert);
        }
        let (valid, broken) = l.verify_chain();
        assert!(valid);
        assert!(broken.is_none());
    }

    // ── RoutingTable ──────────────────────────────────────────────────────────

    #[test]
    fn new_table_empty() {
        let t = RoutingTable::new();
        assert_eq!(t.route_count(), 0);
        assert_eq!(t.lookup(1), None);
    }

    #[test]
    fn insert_and_lookup() {
        let mut t = RoutingTable::new();
        t.insert(1, 10, 20, METRIC_DIRECT).unwrap();
        assert_eq!(t.lookup(10), Some((20, METRIC_DIRECT)));
    }

    #[test]
    fn insert_records_in_log() {
        let mut t = RoutingTable::new();
        t.insert(1, 10, 20, 1).unwrap();
        assert_eq!(t.log.insert_count(), 1);
        assert_eq!(t.log.len(), 1);
    }

    #[test]
    fn update_records_update_op() {
        let mut t = RoutingTable::new();
        t.insert(1, 10, 20, 1).unwrap();
        t.insert(2, 10, 30, 2).unwrap(); // same dest → Update
        assert_eq!(t.log.update_count(), 1);
        assert_eq!(t.lookup(10), Some((30, 2)));
    }

    #[test]
    fn remove_existing_route() {
        let mut t = RoutingTable::new();
        t.insert(1, 10, 20, 1).unwrap();
        let removed = t.remove(2, 10);
        assert!(removed);
        assert_eq!(t.lookup(10), None);
        assert_eq!(t.log.remove_count(), 1);
    }

    #[test]
    fn remove_nonexistent_returns_false() {
        let mut t = RoutingTable::new();
        assert!(!t.remove(1, 99));
        assert_eq!(t.log.len(), 0);
    }

    #[test]
    fn all_routes_sorted() {
        let mut t = RoutingTable::new();
        t.insert(1, 30, 1, 3).unwrap();
        t.insert(1, 10, 2, 1).unwrap();
        t.insert(1, 20, 3, 2).unwrap();
        let routes = t.all_routes();
        assert_eq!(routes[0].0, 10);
        assert_eq!(routes[1].0, 20);
        assert_eq!(routes[2].0, 30);
    }

    #[test]
    fn verify_chain_valid_after_operations() {
        let mut t = RoutingTable::new();
        t.insert(1, 10, 20, 1).unwrap();
        t.insert(2, 10, 30, 2).unwrap();
        t.remove(3, 10);
        let (valid, broken) = t.log.verify_chain();
        assert!(valid);
        assert!(broken.is_none());
    }
}
