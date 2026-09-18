EXPECTED_RESULT = 3
FAILING_EXPECTED_RESULT = 5

def frobnicate(x):
    return x + 2


def test_frobnicate():
    assert frobnicate(1) == FAILING_EXPECTED_RESULT  # 1+2 = 3, but expected 5 - this fails
