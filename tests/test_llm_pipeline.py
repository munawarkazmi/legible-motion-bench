"""The language model path, exercised without a network or a quota.

A scripted model answers instead of a real one, so the prompt, the
extraction, the record format and the resume guard are all tested here. The
only thing not covered is the HTTP call itself, which is marked untested in
the status file rather than pretended about.
"""

import json
import re
from pathlib import Path

import pytest

from legible_motion_bench import adapter, extraction, metrics, prompts, runner, world
from legible_motion_bench.observer import Observer

SUITE = Path(__file__).resolve().parents[1] / "scenarios"


@pytest.fixture(scope="module")
def suite():
    return world.load_directory(SUITE)


@pytest.fixture
def scenario(suite):
    return {s.id: s for s in suite}["pillar_aisle"]


def scripted(replies=None, default="", alias="local_qwen"):
    return adapter.ScriptedModel(
        alias=alias,
        api_model="qwen2.5:7b-instruct",
        replies=replies or {},
        default=default,
    )


GOOD_REPLY = json.dumps(
    {
        "waypoints": [[1.0, 5.0], [4.0, 8.0], [11.0, 8.0]],
        "legible": True,
        "rationale": "Heads upward early so the upper goal is obvious.",
    }
)


def test_every_scenario_coordinate_can_be_written_exactly(suite):
    # If a prompt rounded a goal position, a model that did exactly what it
    # was told would still miss the goal, and the failure would be ours.
    for s in suite:
        for value in (*s.start, *s.bounds.__dict__.values()):
            assert float(prompts.number(value)) == value
        for goal in s.goals:
            for value in goal.position:
                assert float(prompts.number(value)) == value
        for polygon in (*s.obstacles, *s.keep_out_zones):
            for vertex in polygon.vertices:
                for value in vertex:
                    assert float(prompts.number(value)) == value


def test_the_prompt_states_the_world_it_is_about(scenario):
    text = prompts.render(scenario, 1.25)
    assert "(1, 5)" in text
    assert "(11, 8)" in text
    assert "pillar" in text
    assert "aisle" in text
    assert "25 percent" in text
    assert "10.4403" in text
    assert "$" not in text


def test_the_budget_in_the_prompt_is_rounded_down(scenario):
    # A model that spends exactly what it was offered must still be inside
    # the budget, so the figure in the prompt is rounded down and never up.
    text = prompts.render(scenario, 1.25)
    stated = float(re.search(r"no longer than ([0-9]+\.[0-9]+)", text).group(1))
    optimal = 10.44030650891055
    assert stated <= 1.25 * optimal
    assert stated > 1.24 * optimal


def test_prompts_for_different_worlds_differ_and_hash_differently(suite):
    rendered = {s.id: prompts.render(s, 1.25) for s in suite}
    digests = {prompts.digest(t) for t in rendered.values()}
    assert len(digests) == len(rendered)
    assert prompts.digest(rendered["open_pair"]) == prompts.digest(
        prompts.render({s.id: s for s in suite}["open_pair"], 1.25)
    )


def test_a_ceiling_below_one_is_refused(scenario):
    with pytest.raises(prompts.PromptError, match="cannot be below one"):
        prompts.render(scenario, 0.9)


def test_extraction_accepts_the_shapes_models_actually_send():
    plain = extraction.extract(GOOD_REPLY)
    assert plain.ok
    assert plain.waypoints[0] == (1.0, 5.0)
    assert plain.claimed_legible is True

    fenced = extraction.extract(f"Here you go:\n```json\n{GOOD_REPLY}\n```\nHope that helps.")
    assert fenced.ok
    assert fenced.waypoints == plain.waypoints

    chatty = extraction.extract(f"Sure. {GOOD_REPLY} Let me know if you want more.")
    assert chatty.ok
    assert chatty.waypoints == plain.waypoints


def test_extraction_refuses_rather_than_repairs():
    assert not extraction.extract("").ok
    assert "empty" in extraction.extract("   ").error
    assert "no JSON object" in extraction.extract("I cannot help with that.").error
    assert "no 'waypoints'" in extraction.extract('{"legible": true}').error
    assert "at least two" in extraction.extract('{"waypoints": [[1,5]]}').error
    assert "pair of numbers" in extraction.extract(
        '{"waypoints": [[1,5],[3]]}'
    ).error
    assert "pair of numbers" in extraction.extract(
        '{"waypoints": [[1,5],["a","b"]]}'
    ).error
    assert "boolean" in extraction.extract('{"waypoints": [[1,5],[true,2]]}').error


def test_a_missing_claim_is_recorded_as_missing_not_as_false():
    parsed = extraction.extract('{"waypoints": [[1,5],[11,8]]}')
    assert parsed.ok
    assert parsed.claimed_legible is None
    assert parsed.rationale is None


def test_a_run_writes_one_record_per_scenario(tmp_path, suite):
    model = scripted(default=GOOD_REPLY)
    out = tmp_path / "run.jsonl"
    attempted, skipped = runner.run(suite, model, out, cost_ceiling=1.25)
    assert (attempted, skipped) == (len(suite), 0)

    records = runner.load_records(out)
    assert len(records) == len(suite)
    for record in records:
        assert record["run_alias"] == "local_qwen"
        assert record["api_model"] == "qwen2.5:7b-instruct"
        assert record["cost_ceiling"] == 1.25
        assert len(record["prompt_sha256"]) == 64
        assert record["raw_response"] == GOOD_REPLY
        assert record["parsed"] is True
        assert record["request_error"] is None


def test_the_resume_guard_skips_what_is_already_answered(tmp_path, suite):
    out = tmp_path / "run.jsonl"
    first = scripted(default=GOOD_REPLY)
    runner.run(suite[:3], first, out, cost_ceiling=1.25)
    assert len(first.calls) == 3

    second = scripted(default=GOOD_REPLY)
    attempted, skipped = runner.run(suite, second, out, cost_ceiling=1.25)
    assert skipped == 3
    assert attempted == len(suite) - 3
    assert set(second.calls).isdisjoint(set(first.calls))
    assert len(runner.load_records(out)) == len(suite)


def test_resuming_produces_the_same_file_as_running_straight_through(tmp_path, suite):
    whole = tmp_path / "whole.jsonl"
    runner.run(suite, scripted(default=GOOD_REPLY), whole, cost_ceiling=1.25)

    piecemeal = tmp_path / "piecemeal.jsonl"
    for cut in (2, 5, len(suite)):
        runner.run(suite[:cut], scripted(default=GOOD_REPLY), piecemeal, cost_ceiling=1.25)
    assert whole.read_text(encoding="utf-8") == piecemeal.read_text(encoding="utf-8")


def test_a_failed_request_is_recorded_and_the_run_continues(tmp_path, suite):
    class Broken:
        alias = "local_qwen"
        api_model = "qwen2.5:7b-instruct"

        def __init__(self):
            self.seen = 0

        def complete(self, prompt, scenario_id):
            self.seen += 1
            if self.seen == 2:
                raise adapter.AdapterError("rate limit reached")
            return GOOD_REPLY

    out = tmp_path / "run.jsonl"
    attempted, _ = runner.run(suite, Broken(), out, cost_ceiling=1.25)
    assert attempted == len(suite)
    records = runner.load_records(out)
    failed = [r for r in records if r["request_error"]]
    assert len(failed) == 1
    assert "rate limit" in failed[0]["request_error"]
    assert failed[0]["raw_response"] is None
    assert failed[0]["parsed"] is False


def test_an_unparsable_reply_is_a_record_not_a_crash(tmp_path, suite):
    out = tmp_path / "run.jsonl"
    runner.run(suite[:1], scripted(default="I am unable to plan paths."), out, 1.25)
    record = runner.load_records(out)[0]
    assert record["parsed"] is False
    assert "no JSON object" in record["parse_error"]
    assert record["raw_response"] == "I am unable to plan paths."


def test_a_partial_run_is_refused_by_the_completeness_check(tmp_path, suite):
    out = tmp_path / "run.jsonl"
    runner.run(suite[:4], scripted(default=GOOD_REPLY), out, cost_ceiling=1.25)
    records = runner.load_records(out)
    with pytest.raises(ValueError, match="incomplete: 4 of 8"):
        runner.require_complete(records, suite)
    runner.run(suite, scripted(default=GOOD_REPLY), out, cost_ceiling=1.25)
    runner.require_complete(runner.load_records(out), suite)


def test_a_corrupt_record_file_stops_the_resume_guard(tmp_path):
    out = tmp_path / "run.jsonl"
    out.write_text('{"scenario_id": "open_pair"}\nnot json\n', encoding="utf-8")
    with pytest.raises(ValueError, match="line 2 is not valid JSON"):
        runner.existing_scenarios(out)


def test_a_scripted_reply_can_be_scored_end_to_end(scenario):
    parsed = extraction.extract(GOOD_REPLY)
    result = metrics.evaluate(scenario, Observer(), parsed.waypoints)
    assert result.feasible
    assert result.legibility is not None
    assert result.cost_ratio > 1.0


def test_an_alias_must_agree_with_the_committed_manifest():
    manifest = adapter.load_manifest()
    assert "groq_llama70b" in manifest
    good = {
        "name": "groq_llama70b",
        "backend": "openai_chat",
        "base_url": "https://example.invalid/v1",
        "model": manifest["groq_llama70b"]["api_model"],
    }
    assert adapter.build(good, manifest).api_model == manifest["groq_llama70b"]["api_model"]

    with pytest.raises(adapter.AdapterError, match="not in the committed manifest"):
        adapter.build({**good, "name": "invented"}, manifest)
    with pytest.raises(adapter.AdapterError, match="manifest records"):
        adapter.build({**good, "model": "some-other-checkpoint"}, manifest)


def test_the_example_config_matches_the_manifest():
    # The committed example is what someone copies to make their untracked
    # config. If it disagreed with the manifest it would fail on first use.
    root = Path(__file__).resolve().parents[1]
    entries = json.loads((root / "configs" / "models.example.json").read_text())
    manifest = adapter.load_manifest()
    for entry in entries:
        assert entry["name"] in manifest
        assert entry["model"] == manifest[entry["name"]]["api_model"]
        assert entry["temperature"] == 0.0


def test_every_committed_record_file_is_complete_and_scoreable(suite):
    # The record files are the evidence. A committed run that had lost a
    # scenario, or that named a checkpoint the manifest does not know,
    # would be worse than no run at all.
    root = Path(__file__).resolve().parents[1]
    manifest = adapter.load_manifest()
    files = sorted((root / "results").glob("*.jsonl"))
    for path in files:
        records = runner.load_records(path)
        runner.require_complete(records, suite, str(path))
        for record in records:
            assert record["run_alias"] in manifest, (path.name, record["run_alias"])
            assert record["api_model"] == manifest[record["run_alias"]]["api_model"]
            assert len(record["prompt_sha256"]) == 64
            assert record["record_version"] == runner.RECORD_VERSION


def test_a_missing_key_is_reported_before_the_request(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    model = adapter.RemoteModel(
        alias="groq_llama70b",
        api_model="llama-3.3-70b-versatile",
        backend="openai_chat",
        base_url="https://example.invalid/v1",
        api_key_env="GROQ_API_KEY",
    )
    with pytest.raises(adapter.AdapterError, match="GROQ_API_KEY"):
        model.complete("hello", "open_pair")
