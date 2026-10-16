import time

import pytest

from support_bot.recorder import CassetteMissing, Recorder, RunTimeExceeded, cassette_key
from tests.fakes import FakeLLM


def test_key_changes_with_each_input():
    base = cassette_key("m", "s", "u", {"a": 1, "b": 2})
    assert cassette_key("m2", "s", "u", {"a": 1, "b": 2}) != base
    assert cassette_key("m", "s2", "u", {"a": 1, "b": 2}) != base
    assert cassette_key("m", "s", "u2", {"a": 1, "b": 2}) != base
    assert cassette_key("m", "s", "u", {"a": 1, "b": 3}) != base
    assert cassette_key("m", "s", "u", {"b": 2, "a": 1}) == base


def test_replay_returns_recorded_completion(tmp_path):
    recorded = Recorder(FakeLLM(default="recorded"), tmp_path, mode="record").complete("s", "u")
    other = FakeLLM(default="different")
    replayed = Recorder(other, tmp_path, mode="replay").complete("s", "u")
    assert replayed == recorded
    assert replayed.text == "recorded"
    assert other.calls == []


def test_replay_missing_key_raises(tmp_path):
    with pytest.raises(CassetteMissing, match="run the Record workflow"):
        Recorder(FakeLLM(), tmp_path, mode="replay").complete("s", "u")


def test_replay_missing_directory_raises_cassette_missing(tmp_path):
    with pytest.raises(CassetteMissing):
        Recorder(FakeLLM(), tmp_path / "absent", mode="replay").complete("s", "u")


def test_live_calls_without_writing(tmp_path):
    llm = FakeLLM()
    Recorder(llm, tmp_path, mode="live").complete("s", "u")
    assert len(llm.calls) == 1
    assert list(tmp_path.iterdir()) == []


def test_record_writes_one_cassette(tmp_path):
    Recorder(FakeLLM(), tmp_path, mode="record").complete("s", "u")
    assert len(list(tmp_path.glob("*.json"))) == 1


def test_time_budget_exceeded(tmp_path):
    with pytest.raises(RunTimeExceeded):
        Recorder(FakeLLM(), tmp_path, mode="record", time_budget_s=0).complete("s", "u")


def test_recorder_exposes_wrapped_model_and_options(tmp_path):
    rec = Recorder(FakeLLM(model="m1", options={"seed": 1}), tmp_path)
    assert (rec.model, rec.options) == ("m1", {"seed": 1})


def test_key_changes_with_schema():
    assert cassette_key("m", "s", "u", {}) != cassette_key("m", "s", "u", {}, schema={"type": "object"})


def test_record_reuses_existing_cassette_without_calling(tmp_path):
    Recorder(FakeLLM(default="first"), tmp_path, mode="record").complete("s", "u")
    second = FakeLLM(default="second")
    assert Recorder(second, tmp_path, mode="record").complete("s", "u").text == "first"
    assert second.calls == []


def test_interrupted_record_run_resumes(tmp_path):
    Recorder(FakeLLM(default="kept"), tmp_path, mode="record").complete("s", "q1")
    out_of_time = Recorder(FakeLLM(), tmp_path, mode="record", time_budget_s=0)
    assert out_of_time.complete("s", "q1").text == "kept"
    with pytest.raises(RunTimeExceeded):
        out_of_time.complete("s", "q2")


def test_record_rerecords_unreadable_cassette(tmp_path):
    rec = Recorder(FakeLLM(default="old"), tmp_path, mode="record")
    rec.complete("s", "u")
    next(tmp_path.glob("*.json")).write_text("{broken")
    assert Recorder(FakeLLM(default="new"), tmp_path, mode="record").complete("s", "u").text == "new"


def test_recorders_share_start_time(tmp_path):
    rec = Recorder(FakeLLM(), tmp_path, mode="live", time_budget_s=10, started=time.monotonic() - 11)
    with pytest.raises(RunTimeExceeded):
        rec.complete("s", "u")


def test_structured_request_is_recorded_under_its_schema(tmp_path):
    llm = FakeLLM(default="{}")
    rec = Recorder(llm, tmp_path, mode="record")
    rec.complete("s", "u", schema={"type": "object"})
    assert llm.calls == [("s", "u", {"type": "object"})]
    with pytest.raises(CassetteMissing):
        Recorder(FakeLLM(), tmp_path, mode="replay").complete("s", "u")


def test_recorder_logs_latency_of_every_completion(tmp_path):
    rec = Recorder(FakeLLM(), tmp_path, mode="record")
    rec.complete("s", "u1")
    rec.complete("s", "u1")
    assert rec.latencies_ms == [7, 7]
