"""
sovereign_hd CLI entrypoint.
Usage: python -m sovereign_hd "Some text to evaluate"
       sovereign-hd "Some text to evaluate"
"""
import sys
from .core import SovereignHD


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: sovereign-hd '<text to evaluate>'")
        print("Example: sovereign-hd 'The capital of France is Paris.'")
        sys.exit(0)

    text   = " ".join(sys.argv[1:])
    engine = SovereignHD()
    result = engine.evaluate(text)

    print(f"\n{'─'*60}")
    print(f"  Sovereign HD Evaluation")
    print(f"{'─'*60}")
    print(f"  Text       : {text[:80]}")
    print(f"  HD Score   : {result.hd_score:.4f}  (0.0=perfect, 1.0=hallucination)")
    print(f"  Status     : {result.status}")
    print(f"  Confidence : {result.confidence:.4f}")
    print(f"  Resonance  : {result.resonance:.4f}")
    print(f"  Entropy    : {result.entropy:.4f}")
    print(f"  Latency    : {result.latency_ms:.1f} ms")
    print(f"{'─'*60}\n")


if __name__ == "__main__":
    main()
