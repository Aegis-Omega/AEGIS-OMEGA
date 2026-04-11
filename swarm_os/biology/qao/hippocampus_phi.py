import numpy as np
from typing import List, Tuple

class KnowledgeHippocampus:
    def __init__(self):
        self.nodes = [f"node_{i}" for i in range(80)]
        self.edges = { (self.nodes[i], self.nodes[(i+1)%80]): 1.0 for i in range(80) } 
        self.phi = 1.618 
        self.max_weight = 10.0  
        self.min_weight = 0.01  

    def reinforce_pathway(self, traversed_edges: List[Tuple[str, str]], hd_score: float, target_hd: float = 0.05):
        if hd_score <= target_hd:
            scale = self.phi
            action = "reinforced (*1.618)"
        else:
            scale = 1.0 / self.phi
            action = "penalized (÷1.618)"
            
        updated = 0
        for edge in traversed_edges:
            if edge in self.edges:
                new_weight = self.edges[edge] * scale
                self.edges[edge] = max(self.min_weight, min(self.max_weight, new_weight))
                updated += 1
                
        print(f"[PLASTICITY] {updated} specific synapses {action}. (Raw HD={hd_score:.4f})")

    def dream_state_consolidation(self):
        """Asynchronous REM Cycle. A² Matrix dot product Epiphany wiring."""
        print("\n[DREAM STATE DAEMON] Initializing REM Cycle. Consolidating A² Matrix...")
        n = len(self.nodes)
        A = np.zeros((n, n))
        node_to_idx = {name: i for i, name in enumerate(self.nodes)}
        
        for (u, v), weight in self.edges.items():
            if weight > self.min_weight: 
                i, j = node_to_idx[u], node_to_idx[v]
                A[i, j] = weight
                
        # A² Calculation (Dot Product)
        A2 = np.dot(A, A)
        
        epiphanies_wired = 0
        for i in range(n):
            for j in range(n):
                if i != j and A[i, j] == 0.0 and A2[i, j] > 0.5:
                    new_edge = (self.nodes[i], self.nodes[j])
                    self.edges[new_edge] = min(self.max_weight, A2[i, j] * 0.1)
                    epiphanies_wired += 1
                    print(f"  -> [EPIPHANY] A² Calculation Complete. Hidden path discovered: [{self.nodes[i]}] -> [{self.nodes[j]}]. Semantic shortcut wired.")
                    
                    if epiphanies_wired >= 3: 
                        break
            if epiphanies_wired >= 3:
                break
        print(f"[DREAM STATE DAEMON] REM Cycle Complete. {epiphanies_wired} new synaptic bridges formed.")
