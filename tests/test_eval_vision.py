import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "eval_vision", Path(__file__).parent.parent / "scripts" / "eval-vision.py"
)
eval_vision = importlib.util.module_from_spec(spec)
spec.loader.exec_module(eval_vision)


def test_matches_each_expected_fact_and_alternatives():
    assert eval_vision.matches_expected_groups(
        "The category with the most units is B, with six units.",
        [["B"], ["6", "six"]],
    )


def test_does_not_match_single_letter_inside_another_word():
    assert not eval_vision.matches_expected_groups("The bar is tallest.", [["B"]])


def test_matches_written_object_count():
    assert eval_vision.matches_expected_groups("There are three red circles.", [["3", "three"]])
