import pytest

from proj_utils import *


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


# Tests for NodeInfo class
class TestNodeInfoInit:
    """Test NodeInfo initialization with default and custom inputs."""

    def test_node_info_default_init(self):
        """Test NodeInfo initialization with default argument."""
        node = NodeInfo()
        assert node._output_node_num == 0
        assert node._input_node_list == []
        assert node._gate_name == ""
        assert node._inp_str == "default"

    def test_node_info_default_string_init(self):
        """Test NodeInfo initialization with 'default' string."""
        node = NodeInfo("default")
        assert node._output_node_num == 0
        assert node._input_node_list == []
        assert node._gate_name == ""

    @pytest.mark.parametrize(
        "inp, expected_output, expected_gate, expected_inputs",
        [
            pytest.param(
                "123 = AND(1,2,3)",
                123,
                "AND",
                [1, 2, 3],
                id="basic_and_gate",
            ),
            pytest.param(
                "456 = OR(10,20)",
                456,
                "OR",
                [10, 20],
                id="basic_or_gate",
            ),
            pytest.param(
                "  789  =  XOR( 5 , 6 , 7 )  ",
                789,
                "XOR",
                [5, 6, 7],
                id="spaces_everywhere",
            ),
            pytest.param(
                "0 = NAND(1)",
                0,
                "NAND",
                [1],
                id="single_input",
            ),
        ],
    )
    def test_node_info_valid_init(self, inp, expected_output, expected_gate, expected_inputs):
        """Test NodeInfo initialization with valid circuit specifications."""
        node = NodeInfo(inp)
        assert node._output_node_num == expected_output
        assert node._gate_name == expected_gate
        assert node._input_node_list == expected_inputs

    @pytest.mark.parametrize(
        "inp, error_msg_substr",
        [
            pytest.param("123 AND(1,2,3)", "Input string is of unexpected format", id="missing_equals"),
            pytest.param("123 = A(1,2)", "Input string is of unexpected format", id="single_letter_gate"),
            pytest.param("ABC = AND(1,2)", "Input string is of unexpected format", id="output_not_integer"),
            pytest.param("123 = AND(1,2) extra", "The round brackets need to be at the end", id="content_after_bracket"),
            pytest.param("123 = AND(1,2a)", "Node number not found", id="non_integer_input"),
            pytest.param("123 = AND()", "Node number not found", id="no_inputs"),
        ],
    )
    def test_node_info_invalid_init(self, inp, error_msg_substr):
        """Test NodeInfo initialization with invalid circuit specifications raises exception."""
        with pytest.raises(UnexpectedInputStringFormat) as exc_info:
            NodeInfo(inp)
        assert error_msg_substr in str(exc_info.value)

    def test_node_info_non_string_init(self):
        """Test NodeInfo initialization with non-string raises exception."""
        with pytest.raises(UnexpectedInputStringFormat) as exc_info:
            NodeInfo(123)  # type: ignore[arg-type]
        assert "Input must be a string" in str(exc_info.value)


class TestNodeInfoStoreMethod:
    """Test NodeInfo.store_info_from_string method."""

    def test_store_info_from_string_valid(self):
        """Test storing valid circuit info after initialization."""
        node = NodeInfo()
        assert node._output_node_num == 0
        node.store_info_from_string("999 = BUFFER(7,8,9)")
        assert node._output_node_num == 999
        assert node._gate_name == "BUFFER"
        assert node._input_node_list == [7, 8, 9]

    def test_store_info_from_string_overwrites_previous(self):
        """Test that store_info_from_string overwrites previous data."""
        node = NodeInfo("50 = NOR(1,2)")
        assert node._output_node_num == 50
        node.store_info_from_string("100 = NAND(3,4,5)")
        assert node._output_node_num == 100
        assert node._gate_name == "NAND"
        assert node._input_node_list == [3, 4, 5]

    def test_store_info_from_string_invalid(self):
        """Test store_info_from_string with invalid input raises exception."""
        node = NodeInfo()
        with pytest.raises(UnexpectedInputStringFormat):
            node.store_info_from_string("INVALID = GATE")

    @pytest.mark.parametrize(
        "inp1, inp2",
        [
            pytest.param(
                "10 = AND(1,2)",
                "20 = OR(3,4,5)",
                id="and_to_or",
            ),
            pytest.param(
                "5 = AB(99)",
                "15 = XYZ(1,2,3,4)",
                id="two_letter_to_three_letter_gate",
            ),
        ],
    )
    def test_store_info_from_string_multiple_stores(self, inp1, inp2):
        """Test multiple store operations."""
        node = NodeInfo(inp1)
        assert node._output_node_num == int(inp1.split("=")[0].strip())
        node.store_info_from_string(inp2)
        assert node._output_node_num == int(inp2.split("=")[0].strip())
