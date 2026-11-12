from app.prompts import candidate_clipping_prompt


def system_prompt() -> str:
    system, _user = candidate_clipping_prompt("Title", "Summary", "S001 | 00:00 | text", "en")
    return system


def test_good_example_does_not_model_internal_chunk_wording() -> None:
    system = system_prompt()
    good_example = system[system.index("Good example:") : system.index("Bad example:")]

    assert "chunk" not in good_example.lower()


def test_contextual_explanation_rule_does_not_ask_for_chunk_wording() -> None:
    assert "in this specific chunk" not in system_prompt()


def test_candidate_prompt_forbids_pipeline_terms_in_explanations() -> None:
    assert "Never mention chunks, segments, or transcripts" in system_prompt()
