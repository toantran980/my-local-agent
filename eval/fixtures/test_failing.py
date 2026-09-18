EXPECTED_RESULT = 3

def frobnicate(x):
    return x + 2


def test_frobnicate():
    assert frobnicate(1) == 5  # 1+2 = 3, but expected 5 - this fails
