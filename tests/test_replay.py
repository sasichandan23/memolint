"""Transcript replay: cue points and pacing."""

from memolint.replay import ANSI, Pacing, find_marks

TRANSCRIPT = (
    "\u256d\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500 Memolint review \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u256e\n"
    "\u2502 memory on | 3 recalled                 \u2502\n"
    "\u2570\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2570\n"
    "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500 memory ON \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n"
    "\x1b[32mF1  HIGH\x1b[0m  N+1 calls in loop\n"
)


def _write(tmp_path, text=TRANSCRIPT):
    p = tmp_path / "t.ansi"
    p.write_text(text, encoding="utf-8")
    return p


def test_marks_find_section_rules_only(tmp_path):
    assert find_marks(_write(tmp_path)) == [(3, "memory ON")]


def test_marks_ignore_square_cornered_panels(tmp_path):
    square = TRANSCRIPT.replace("\u256d", "\u250c").replace("\u256e", "\u2510").replace("\u2570", "\u2514")
    assert find_marks(_write(tmp_path, square)) == [(3, "memory ON")]


def test_rules_get_a_beat_and_panels_go_fast():
    p = Pacing(speed=1.0)
    rule = "\u2500" * 20 + " memory ON " + "\u2500" * 20
    assert p.delay_for(rule, prev_was_panel=False) == p.beat
    assert p.delay_for("\u2502 memory on |", prev_was_panel=False) < 0.1


def test_speed_scales_every_delay():
    slow, fast = Pacing(speed=1.0), Pacing(speed=2.0)
    line = "The reviewer now cites the outage it was told about."
    assert fast.delay_for(line, prev_was_panel=False) == slow.delay_for(line, prev_was_panel=False) / 2


def test_prose_delay_is_bounded():
    p = Pacing(speed=1.0)
    assert p.delay_for("x", prev_was_panel=False) == p.min_line
    assert p.delay_for("y" * 5000, prev_was_panel=False) == p.max_line


def test_colour_codes_do_not_affect_pacing():
    p = Pacing(speed=1.0)
    plain, coloured = "F1  HIGH  N+1", "\x1b[32mF1  HIGH\x1b[0m  N+1"
    assert ANSI.sub("", coloured) == plain
    assert p.delay_for(coloured, prev_was_panel=False) == p.delay_for(plain, prev_was_panel=False)
