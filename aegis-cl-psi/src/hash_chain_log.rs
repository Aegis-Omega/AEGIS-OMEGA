#[derive(Debug, Clone)]
pub struct HashChainLog<T> {
    genesis_hash: [u8; 32],
    entries: Vec<T>,
}

pub trait HashChainEntry {
    fn previous_hash(&self) -> &[u8; 32];
    fn entry_hash(&self) -> &[u8; 32];
    fn hash_for(&self, previous_hash: &[u8; 32]) -> [u8; 32];
    fn set_hashes(&mut self, previous_hash: [u8; 32], entry_hash: [u8; 32]);
}

impl<T: HashChainEntry> HashChainLog<T> {
    pub fn new(genesis_hash: [u8; 32]) -> Self {
        Self {
            genesis_hash,
            entries: Vec::new(),
        }
    }

    pub fn len(&self) -> usize {
        self.entries.len()
    }

    pub fn is_empty(&self) -> bool {
        self.entries.is_empty()
    }

    pub fn entries(&self) -> &[T] {
        &self.entries
    }

    #[cfg(test)]
    pub(crate) fn entries_mut_for_test(&mut self) -> &mut [T] {
        &mut self.entries
    }

    pub fn terminal_hash(&self) -> [u8; 32] {
        self.entries
            .last()
            .map(|entry| *entry.entry_hash())
            .unwrap_or(self.genesis_hash)
    }

    pub fn append(&mut self, mut entry: T) -> &T {
        let previous_hash = self.terminal_hash();
        let entry_hash = entry.hash_for(&previous_hash);
        entry.set_hashes(previous_hash, entry_hash);
        self.entries.push(entry);
        self.entries.last().unwrap()
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut previous_hash = self.genesis_hash;
        for (index, entry) in self.entries.iter().enumerate() {
            if entry.previous_hash() != &previous_hash
                || entry.entry_hash() != &entry.hash_for(&previous_hash)
            {
                return (false, Some(index));
            }
            previous_hash = *entry.entry_hash();
        }
        (true, None)
    }
}

impl<T: HashChainEntry> Default for HashChainLog<T> {
    fn default() -> Self {
        Self::new([0; 32])
    }
}

#[cfg(test)]
mod tests {
    use super::{HashChainEntry, HashChainLog};

    struct TestEntry {
        value: u8,
        previous_hash: [u8; 32],
        entry_hash: [u8; 32],
    }

    impl TestEntry {
        fn new(value: u8) -> Self {
            Self {
                value,
                previous_hash: [0; 32],
                entry_hash: [0; 32],
            }
        }
    }

    impl HashChainEntry for TestEntry {
        fn previous_hash(&self) -> &[u8; 32] {
            &self.previous_hash
        }

        fn entry_hash(&self) -> &[u8; 32] {
            &self.entry_hash
        }

        fn hash_for(&self, previous_hash: &[u8; 32]) -> [u8; 32] {
            previous_hash.map(|byte| byte.wrapping_add(self.value))
        }

        fn set_hashes(&mut self, previous_hash: [u8; 32], entry_hash: [u8; 32]) {
            self.previous_hash = previous_hash;
            self.entry_hash = entry_hash;
        }
    }

    #[test]
    fn empty_log_uses_genesis_and_verifies() {
        let log = HashChainLog::<TestEntry>::default();
        assert!(log.is_empty());
        assert_eq!(log.terminal_hash(), [0; 32]);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn append_uses_nonzero_genesis_hash() {
        let genesis_hash = [7; 32];
        let mut log = HashChainLog::new(genesis_hash);

        let entry = log.append(TestEntry::new(1));

        assert_eq!(entry.previous_hash(), &genesis_hash);
        assert_eq!(entry.entry_hash(), &[8; 32]);
        assert_eq!(log.terminal_hash(), [8; 32]);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn appends_link_entries_and_verify_for_varied_lengths() {
        for length in 0..32 {
            let mut log = HashChainLog::default();
            for value in 1..=length {
                log.append(TestEntry::new(value));
            }
            assert_eq!(log.len(), length as usize);
            assert_eq!(log.verify_chain(), (true, None));
            if let Some(first) = log.entries().first() {
                assert_eq!(first.previous_hash(), &[0; 32]);
            }
            for entries in log.entries().windows(2) {
                assert_eq!(entries[1].previous_hash(), entries[0].entry_hash());
            }
        }
    }

    #[test]
    fn detects_tampering_at_first_invalid_entry() {
        let mut log = HashChainLog::default();
        log.append(TestEntry::new(1));
        log.append(TestEntry::new(2));
        log.append(TestEntry::new(3));
        log.entries[1].value = 9;

        assert_eq!(log.verify_chain(), (false, Some(1)));
    }

    #[test]
    fn detects_tampered_previous_hash() {
        let mut log = HashChainLog::default();
        log.append(TestEntry::new(1));
        log.append(TestEntry::new(2));
        log.entries[1].previous_hash = [9; 32];

        assert_eq!(log.verify_chain(), (false, Some(1)));
    }

    #[test]
    fn detects_tampered_entry_hash() {
        let mut log = HashChainLog::default();
        log.append(TestEntry::new(1));
        log.append(TestEntry::new(2));
        log.entries[1].entry_hash = [9; 32];

        assert_eq!(log.verify_chain(), (false, Some(1)));
    }
}
