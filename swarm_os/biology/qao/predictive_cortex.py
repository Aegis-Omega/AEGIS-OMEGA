import numpy as np

class PredictiveCortex:
    def calculate_free_energy(self, expected_vector: np.ndarray, actual_vector: np.ndarray) -> float:
        """Calculates Semantic surprise (Free Energy) via Cosine distance mapped to [0,1]"""
        norm_expected = np.linalg.norm(expected_vector)
        norm_actual = np.linalg.norm(actual_vector)
        
        if norm_expected == 0 or norm_actual == 0:
            return 1.0
            
        cosine_sim = np.dot(expected_vector, actual_vector) / (norm_expected * norm_actual)
        free_energy = (1.0 - cosine_sim) / 2.0  # Cosine dist [0,1]
        
        print(f"[PREDICTIVE CORTEX] Semantic Expectation generated vs Actual. Free Energy (Surprise): {free_energy:.4f}")
        return free_energy
