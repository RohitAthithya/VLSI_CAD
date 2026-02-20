import pytest

from proj_utils import ret_node_number_list


# Tests for ret_node_number_list
@pytest.mark.parametrize(
    "inp, expected",
    [
        ("INPUT(12)", [12]),
        ("OUTPUT(0)", [0]),
        ("  GATE(  345  )  ", [345]),
        ("X(678)", [678]),
        ("INPUT(1,2,3)", [1, 2, 3]),
        ("OUTPUT(  42  ,7)", [42, 7]),
        ("(9,10)", [9, 10]),
        ("NODE(0)", [0]),
        ("GATE(001,02)", [1, 2]),
    ],
)
def test_ret_node_number_list_valid(inp, expected):
    assert ret_node_number_list(inp) == (True, expected)


@pytest.mark.parametrize(
    "inp, expected_substr",
    [
        pytest.param("NODE()", "Node number not found", id="empty"),
        pytest.param("NODE(12a,3)", "Node number not found", id="non_integer_token"),
        pytest.param(
            "NODE(1,2) extra",
            "The round brackets need to be at the end",
            id="not_at_end",
        ),
        pytest.param("NO_BRACKETS", "round brackets not found", id="no_brackets"),
        pytest.param("NODE(,)", "Node number not found", id="only_commas"),
    ],
)
def test_ret_node_number_list_invalid(inp, expected_substr):
    ok, msg = ret_node_number_list(inp)
    assert ok is False
    assert expected_substr in msg


def test_ret_node_number_list_non_string():
    ok, msg = ret_node_number_list(123)  # type: ignore[arg-type]
    assert ok is False
    assert "must be a string" in msg
