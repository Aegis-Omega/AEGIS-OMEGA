"""AEGIS Omega transition analytics: streaming, mergeable sufficient statistics.

Q16.16 entropy/adjacent-symbol MI use rational log enclosures, not float.
This is a lossy first-order Markov statistic, NOT a replay of source events.
A source hash only detects changes relative to a trusted external anchor.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from fractions import Fraction
from functools import lru_cache
from hashlib import sha256
import argparse
import json
import sys
from typing import Iterable

SCALE = 1 << 16
MAX_ALPHABET = 256
SCHEMA = "AEGIS_TRANSITION_STATS_V14_1"


class InvalidStats(ValueError):
    pass


def _check_int(value: object, low: int, upper: int | None = None) -> bool:
    return type(value) is int and value >= low and (upper is None or value < upper)


@dataclass(frozen=True, slots=True)
class TransitionStats:
    alphabet: int
    length: int
    first: int | None
    last: int | None
    edges: tuple[tuple[int, int, int], ...]

    def __post_init__(self):
        if not _check_int(self.alphabet, 1) or self.alphabet > MAX_ALPHABET:
            raise InvalidStats("INVALID_ALPHABET")
        if not _check_int(self.length, 0):
            raise InvalidStats("INVALID_LENGTH")
        if type(self.edges) is not tuple or len(self.edges) > self.alphabet ** 2:
            raise InvalidStats("INVALID_EDGES")
        if self.length == 0:
            if self.first is not None or self.last is not None or self.edges:
                raise InvalidStats("INVALID_EMPTY")
            return
        if not _check_int(self.first, 0, self.alphabet) or not _check_int(self.last, 0, self.alphabet):
            raise InvalidStats("INVALID_ENDPOINTS")
        if self.length == 1:
            if self.first != self.last or self.edges:
                raise InvalidStats("INVALID_SINGLETON")
            return
        outdeg, indeg = Counter(), Counter()
        neighbors: dict[int, set[int]] = defaultdict(set)
        seen: set[int] = set()
        last_edge: tuple[int, int] | None = None
        total = 0
        for edge in self.edges:
            if type(edge) is not tuple or len(edge) != 3:
                raise InvalidStats("MALFORMED_EDGE")
            a, b, count = edge
            if not _check_int(a, 0, self.alphabet) or not _check_int(b, 0, self.alphabet) or not _check_int(count, 1):
                raise InvalidStats("INVALID_EDGE_VALUE")
            if last_edge is not None and (a, b) <= last_edge:
                raise InvalidStats("UNSORTED_OR_DUPLICATE_EDGES")
            last_edge = a, b
            outdeg[a] += count
            indeg[b] += count
            neighbors[a].add(b)
            neighbors[b].add(a)
            seen.update((a, b))
            total += count
        if total != self.length - 1 or self.first not in seen or self.last not in seen:
            raise InvalidStats("INVALID_EDGE_COUNT")
        for vertex in seen:
            if outdeg[vertex] - indeg[vertex] != int(vertex == self.first) - int(vertex == self.last):
                raise InvalidStats("NOT_EULERIAN")
        reached = {self.first}
        todo = [self.first]
        while todo:
            for candidate in neighbors[todo.pop()]:
                if candidate not in reached:
                    reached.add(candidate)
                    todo.append(candidate)
        if reached != seen:
            raise InvalidStats("DISCONNECTED_TRANSITIONS")

    @classmethod
    def from_iterable(cls, symbols: Iterable[int], alphabet: int, *, source_digest=None) -> TransitionStats:
        if not _check_int(alphabet, 1) or alphabet > MAX_ALPHABET:
            raise InvalidStats("INVALID_ALPHABET")
        counts: Counter[tuple[int, int]] = Counter()
        first = last = None
        length = 0
        for symbol in symbols:
            if not _check_int(symbol, 0, alphabet):
                raise InvalidStats("INVALID_SYMBOL")
            if source_digest is not None:
                digits = str(symbol).encode("ascii")
                source_digest.update(str(len(digits)).encode("ascii") + b":" + digits + b";")
            if length == 0:
                first = symbol
            else:
                counts[last, symbol] += 1
            last = symbol
            length += 1
        return cls(alphabet, length, first, last, tuple((a, b, count) for (a, b), count in sorted(counts.items())))

    def concat(self, other: TransitionStats) -> TransitionStats:
        if not isinstance(other, TransitionStats) or self.alphabet != other.alphabet:
            raise InvalidStats("ALPHABET_MISMATCH")
        if not self.length:
            return other
        if not other.length:
            return self
        counts = Counter({(a, b): n for a, b, n in self.edges})
        counts.update({(a, b): n for a, b, n in other.edges})
        counts[self.last, other.first] += 1
        return TransitionStats(self.alphabet, self.length + other.length, self.first, other.last,
                               tuple((a, b, n) for (a, b), n in sorted(counts.items())))

    def margins(self):
        previous, following = Counter(), Counter()
        for a, b, n in self.edges:
            previous[a] += n
            following[b] += n
        return previous, following

    def canonical_bytes(self) -> bytes:
        obj = {"schema": SCHEMA, "alphabet": self.alphabet, "length": self.length,
               "first": self.first, "last": self.last, "edges": [list(e) for e in self.edges]}
        return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")

    def digest(self) -> str:
        return sha256(b"AEGIS-V14-STATISTIC\0" + self.canonical_bytes()).hexdigest()

    @classmethod
    def parse(cls, data: bytes) -> TransitionStats:
        if type(data) is not bytes or len(data) > 4_000_000:
            raise InvalidStats("SERIALIZATION_LIMIT")
        def unique(pairs):
            d = {}
            for key, value in pairs:
                if key in d:
                    raise InvalidStats("DUPLICATE_JSON_KEY")
                d[key] = value
            return d
        try:
            obj = json.loads(data.decode("ascii"), object_pairs_hook=unique)
            if type(obj) is not dict or set(obj) != {"schema", "alphabet", "length", "first", "last", "edges"}:
                raise InvalidStats("SERIALIZATION_SCHEMA")
            if obj["schema"] != SCHEMA or type(obj["edges"]) is not list:
                raise InvalidStats("SERIALIZATION_VERSION")
            stats = cls(obj["alphabet"], obj["length"], obj["first"], obj["last"],
                        tuple(tuple(edge) if type(edge) is list else edge for edge in obj["edges"]))
            if stats.canonical_bytes() != data:
                raise InvalidStats("NONCANONICAL_JSON")
            return stats
        except (UnicodeError, ValueError, TypeError, KeyError) as exc:
            if isinstance(exc, InvalidStats):
                raise
            raise InvalidStats("INVALID_JSON") from exc


def _nearest_even(value: Fraction) -> int:
    integer, remainder = divmod(value.numerator, value.denominator)
    doubled = remainder * 2
    if doubled < value.denominator:
        return integer
    if doubled > value.denominator:
        return integer + 1
    return integer if integer % 2 == 0 else integer + 1


def _ln_atanh_bounds(x: Fraction, n: int) -> tuple[Fraction, Fraction]:
    """ln((1+x)/(1-x)), rigorous atanh-series interval, 0 <= x <= 1/3."""
    square = x * x
    term = x
    low = Fraction(0)
    for k in range(n):
        low += 2 * term / (2 * k + 1)
        term *= square
    remainder = 2 * term / ((2 * n + 1) * (1 - square))
    return low, low + remainder


@lru_cache(maxsize=65536)
def log2_ratio_bounds(a: int, b: int, terms: int = 28) -> tuple[Fraction, Fraction]:
    """Mathematically proved rational enclosure for log2(a/b)."""
    if not _check_int(a, 1) or not _check_int(b, 1) or type(terms) is not int or not 1 <= terms <= 128:
        raise InvalidStats("LOG_DOMAIN")
    if a == b:
        return Fraction(0), Fraction(0)
    if a < b:
        lo, hi = log2_ratio_bounds(b, a, terms)
        return -hi, -lo
    k = a.bit_length() - b.bit_length()
    if a < b << k:
        k -= 1
    m = Fraction(a, b << k)
    if m == 1:
        return Fraction(k), Fraction(k)
    # For a>=b, 1 < m < 2, hence x<1/3 and the remainder bound applies.
    x = (m - 1) / (m + 1)
    m_lo, m_hi = _ln_atanh_bounds(x, terms)
    two_lo, two_hi = _ln_atanh_bounds(Fraction(1, 3), terms)
    return Fraction(k) + m_lo / two_hi, Fraction(k) + m_hi / two_lo


def _certified_weighted_log_sum(items: list[tuple[int, int, int]], total: int) -> int:
    if total <= 0:
        return 0
    for terms in (16, 24, 32, 48, 64, 96, 128):
        lo = hi = Fraction(0)
        for weight, a, b in items:
            low, high = log2_ratio_bounds(a, b, terms)
            lo += weight * low
            hi += weight * high
        qlow = _nearest_even(lo * SCALE / total)
        qhigh = _nearest_even(hi * SCALE / total)
        if qlow == qhigh:
            return qlow
    raise InvalidStats("UNDECIDABLE_Q16_ROUNDING")


def entropy_rate_q16(stats: TransitionStats) -> int:
    """Certified empirical H(next | previous), rounded ONCE to Q16.16."""
    if not isinstance(stats, TransitionStats):
        raise TypeError("NOT_STATS")
    if stats.length < 2:
        return 0
    previous, _ = stats.margins()
    return _certified_weighted_log_sum([(n, previous[a], n) for a, b, n in stats.edges], stats.length - 1)


def adjacent_mi_q16(stats: TransitionStats) -> int:
    """Certified empirical I(previous; next) from unsquashed integer counts."""
    if not isinstance(stats, TransitionStats):
        raise TypeError("NOT_STATS")
    if stats.length < 2:
        return 0
    previous, following = stats.margins()
    total = stats.length - 1
    return _certified_weighted_log_sum([(n, n * total, previous[a] * following[b])
                                        for a, b, n in stats.edges], total)


def analyze(symbols: Iterable[int], alphabet: int, *, source_id: str) -> dict:
    if type(source_id) is not str or not source_id or len(source_id) > 256 or not all(32 <= ord(ch) <= 126 for ch in source_id):
        raise InvalidStats("INVALID_SOURCE_ID")
    raw = sha256(b"AEGIS-V14-RAW-ORDER\0" + source_id.encode("ascii") + b"\0" + str(alphabet).encode("ascii") + b"\0")
    stats = TransitionStats.from_iterable(symbols, alphabet, source_digest=raw)
    return {"schema": SCHEMA, "source_id": source_id, "source_order_sha256": raw.hexdigest(),
            "statistics_sha256": stats.digest(), "length": stats.length,
            "observed_transitions": len(stats.edges),
            "entropy_rate_q16": entropy_rate_q16(stats),
            "adjacent_mi_q16": adjacent_mi_q16(stats)}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Read symbol stream from stdin; output certified transition analytics")
    parser.add_argument("--alphabet", required=True, type=int)
    parser.add_argument("--source-id", required=True)
    args = parser.parse_args(argv)
    def symbols():
        for line in sys.stdin:
            stripped = line.strip()
            if not stripped or not stripped.isascii() or not stripped.isdecimal():
                raise InvalidStats("BAD_SYMBOL_LINE")
            yield int(stripped)
    try:
        print(json.dumps(analyze(symbols(), args.alphabet, source_id=args.source_id), sort_keys=True))
        return 0
    except InvalidStats as exc:
        print("transition_info: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
