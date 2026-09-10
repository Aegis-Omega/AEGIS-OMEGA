from pathlib import Path


def test_workflow_is_manual_and_read_only():
    text = Path(".github/workflows/navier-openai-research.yml").read_text()
    assert "workflow_dispatch:" in text
    assert "pull_request:" not in text
    assert "issues:" not in text
    assert "contents: read" in text
    assert "contents: write" not in text
    assert "pull-requests: write" not in text
    assert "issues: write" not in text


def test_workflow_cannot_push_or_merge():
    text = Path(".github/workflows/navier-openai-research.yml").read_text().lower()
    forbidden = ["git push", "gh pr merge", "git merge", "gh release", "vercel"]
    assert all(token not in text for token in forbidden)


def test_workflow_marks_model_output_candidate_only():
    text = Path(".github/workflows/navier-openai-research.yml").read_text()
    assert "CANDIDATE_ONLY" in text
    assert "authority_effect=NONE" in text
