EXPECTED_RESULT = 3

def frobnicate(x):
    return x + 2


def test_frobnicate():
    assert frobnicate(1) == EXPECTED_RESULT  # 1+2 = 3, assertion now passes
