from orchestrator_local_patch import ConstitutionalOrchestratorWithLocalModel

def main():
    task = input("Task> ").strip()
    orchestrator = ConstitutionalOrchestratorWithLocalModel()

    metrics = {
        "uncertainty": 0.12,
        "tool_failures": 0,
        "novelty": 0.18,
        "reviewer_disagreement": 0.08,
    }

    result = orchestrator.execute_live(task, metrics)
    print(result)

if __name__ == "__main__":
    main()