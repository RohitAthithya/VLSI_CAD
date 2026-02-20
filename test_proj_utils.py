import pytest

from proj_utils import ret_node_number


@pytest.mark.parametrize(
    "inp, expected",
    [
        ("INPUT(12)", 12),
        ("OUTPUT(0)", 0),
        ("  GATE(  345  )  ", 345),
        ("X(678)", 678),
    ],
)
def test_ret_node_number_valid(inp, expected):
    assert ret_node_number(inp) == (True, expected)


@pytest.mark.parametrize(
    "inp, expected_substr",
    [
        pytest.param("NODE()", "Node number not found", id="empty"),
        pytest.param("NODE(12a)", "Node number not found", id="non-integer"),
        pytest.param(
            "NODE(12) extra",
            "The round brackets need to be at the end",
            id="not_at_end",
        ),
        pytest.param("NO_BRACKETS", "round brackets not found", id="no_brackets"),
    ],
)
def test_ret_node_number_invalid(inp, expected_substr):
    ok, msg = ret_node_number(inp)
    assert ok is False
    assert expected_substr in msg


def test_ret_node_number_non_string():
    ok, msg = ret_node_number(123)  # type: ignore[arg-type]
    assert ok is False
    assert "must be a string" in msg
