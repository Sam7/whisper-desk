from whisper_desk.config import Config
from whisper_desk.models import Word
from whisper_desk.transcript import Transcript


def test_provisional_replaced_and_stable_words_not_duplicated():
    t = Transcript(Config(overlap=1.0, mutable_tail=2.5))
    assert t.update([Word(0, 1, " Hello."), Word(2, 3, " wrong")], 0, 4) == "Hello. wrong"
    assert t.committed == [" Hello."]
    assert t.start == 0.0
    # Same stable word in overlap; revised provisional word in the tail.
    assert t.update([Word(0, 0.5, " Hello."), Word(1.5, 2.5, " world.")], 0.5, 4, final=True) == "Hello. world."
    assert not t.provisional


def test_word_crossing_frontier_is_preserved():
    t = Transcript(Config(overlap=1.0, mutable_tail=2.5))
    t.update([Word(1, 2, " boundary")], 0, 4)
    assert t.frontier == 0 and t.text == "boundary"
    assert t.update([Word(0.5, 1.5, " boundary")], 0.5, 4, final=True) == "boundary"


def test_silence_advances_frontier_and_final_does_not_erase_stable_words():
    t = Transcript(Config(overlap=1.0, mutable_tail=2.5))
    t.update([Word(0, 1, " Keep.")], 0, 5)
    t.update([], t.start, 8)
    assert t.text == "Keep." and t.frontier == 5.5
    assert t.update([], t.start, 9, final=True) == "Keep."


def test_timestamp_drift_does_not_drop_first_uncommitted_word():
    t = Transcript(Config(overlap=1.0, mutable_tail=2.5))
    t.update([Word(0, 1, " fellow."), Word(1.2, 2.2, " Americans,")], 0, 4)
    assert t.committed == [" fellow."]
    # The next pass moves Americans to BEFORE the previous committed time.
    assert t.update([Word(0, 0.5, " fellow"), Word(0.5, 0.9, " Americans,"),
                     Word(1, 2, " ask")], 0, 4, final=True) == "fellow. Americans, ask"


def test_timestamp_drift_does_not_duplicate_committed_word():
    t = Transcript(Config(overlap=1.0, mutable_tail=2.5))
    t.update([Word(0, 1, " Hello.")], 0, 4)
    assert t.update([Word(0, 1.2, " Hello"), Word(1.2, 2, " world.")], 0, 4, final=True) == "Hello. world."


def test_do_not_crop_incomplete_sentence():
    t = Transcript(Config(overlap=1.0, mutable_tail=2.5))
    t.update([Word(0, 1, " Please"), Word(1, 2, " keep"), Word(2, 3, " context")], 0, 7)
    assert not t.committed and t.frontier == 0
    t.update([Word(0, 1, " Please"), Word(1, 2, " keep"), Word(2, 3, " context.")], 0, 8)
    assert t.committed == [" Please", " keep", " context."] and t.frontier == 3


def test_sessions_have_independent_text():
    a, b = Transcript(Config()), Transcript(Config())
    a.update([Word(0, 1, " One.")], 0, 1, final=True)
    assert b.text == "" and b.frontier == 0
