import psutil
import time

class MetabolicEngine:
    def __init__(self, base_atp: float = 1000.0):
        self.max_atp = base_atp
        self.current_atp = base_atp
        self.scarcity_threshold = 150.0
        print("[METABOLISM] AMD Telemetry active (psutil fallback).")

    def consume_atp(self) -> float:
        """Drains ATP based on actual host CPU and RAM load (AMD Host)."""
        cpu_load = psutil.cpu_percent()
        ram_info = psutil.virtual_memory()
        ram_percent = ram_info.percent
        
        # ATP Burn Formula (OMEGA: Grounded in Node Core Count + Throughput)
        core_count = psutil.cpu_count() or 1
        burn_rate = (core_count * 0.5) + (ram_percent * 0.4) + (cpu_load * 0.6)
        self.current_atp = max(0, self.current_atp - burn_rate)
        
        print(f"[METABOLISM] CPU Load: {cpu_load}% | RAM: {ram_percent}% | ATP Remaining: {self.current_atp:.1f}/{self.max_atp}")
        return self.current_atp

    def check_homeostasis(self):
        """Forces a physical power-gate alert if ATP is critical."""
        if self.current_atp <= self.scarcity_threshold:
            print("\n[⚠ METABOLIC DEPLETION] ATP Critical. Host strain exceeding safety envelope.")
            # Zero Slop: No simulated sleep. The system must adapt or fail.
            print("[AUTONOMIC RESPONSE] Energy scarcity detected. Triggering cognitive throttling...\n")
