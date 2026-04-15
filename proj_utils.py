# imports
from pathlib import Path
from os.path import exists as os_exists
from re import fullmatch as re_fullmatch, findall as re_findall

# # custom type aliases
# ErrorMessage = NewType("ErrorMessage", str)
# SuccessMessage = NewType("SuccessMessage", str)
# InputFileText = NewType("InputFileText", list)
# FilePath = NewType("FilePath", str)


# CONSTANTS
ENCODING_FORMAT_DEFAULT = "utf-8"
BIN_DATA_CHUNK_SIZE = 8192  # 8kibi at a time
DASHED_LINES = "".join(["-" for i in range(32)])

# TEXT CONSTANTS
TXT_FILE_PRESENT = "File present at given path, user can read!"
TXT_FILE_MISSING = "File not found at given path"
TXT_CELL = "cell"
TXT_CAPACITANCE = "capacitance"


# CUSTOM EXCEPTIONS:
class UnexpectedInputStringFormat(Exception):
    def __init__(self, message="Input string was of unexpected format"):
        super().__init__(message)
class UnexpectedFileFormatError(Exception):
    def __init__(self, message="Input File was of unexpected format"):
        super().__init__(message)


# region: WRAPPERS
def print_dashed_lines(func):
    def wrapper(*args, **kwargs):
        print(DASHED_LINES)
        ret_val = func(*args, **kwargs)
        print(DASHED_LINES)
        return ret_val

    return wrapper
# endregion: WRAPPERS


# region: file reading methods
def verify_file_path(file_path):
    """Verify if the input file path is a valid file

    Args:
        file_path: file path as a string or a Path object

    Returns:
        A tuple (ok, message):
            - ok is True when the file exists, False otherwise
            - message is a human-readable status string
    """
    try:
        file_path = Path(file_path)
        if file_path.exists() and file_path.is_file():
            return (True, TXT_FILE_PRESENT)
        return (False, f"{TXT_FILE_MISSING}: {file_path}")
    except TypeError:
        return (False, "Input must be of string or Path data type")



def chunked_line_reader(file_path, chunk_size=BIN_DATA_CHUNK_SIZE, encoding=ENCODING_FORMAT_DEFAULT):
    """Read input file and yield each line of the text

    Args:
        file_path (Path): Must be a WindowsPath datatype, else error not handled
        chunk_size (str, optional): Chunk size to process at a time. This affects, how much data is processed at a time in the RAM.\
            If files are huge better to stick with default value. Defaults to BIN_DATA_CHUNK_SIZE.
        encoding (str, optional):encoding format of file. Defaults to ENCODING_FORMAT_DEFAULT.

    Yields:
        Each line from the file as a decoded string.

    Example usage:
        for line in chunked_line_reader("huge.txt"):
            processed_line = line.split(',') #assuming line contains ',' as delimters
            for words in processed_line:
                print(words)

    """
    with open(file_path, "rb") as f:
        buffer = b""
        while True:
            chunk = f.read(chunk_size)
            if not chunk:  # no more data to read -> b"" returned.
                if buffer.strip():  # Yield final buffered line
                    yield buffer.decode(encoding).rstrip("\n")
                break

            buffer += chunk  # since binary string, loaded lines are not heavy!
            lines = buffer.split(b"\n")

            for line in lines[:-1]:
                if line:  # skip empty lines
                    yield line.decode(encoding).rstrip("\r")

            # last line for previouis chunk will be in the net buffered chunk!
            buffer = lines[-1]
# endregion: file reading methods


# region: input file processing methods
def ret_node_number(inp_str):
    """From the input string, find the integer (or token) inside the last pair of round brackets.
    INPUT MUST HAVE A NUMBER ENCLOSED WITH ROUND BRACKETS PRESENT AT THE END OF THE STRING:
    ### POSSIBLE INPUTS:
        - INPUT(**)
        - OUTPUT(**)

    ## If you are looking to get list of numbers within the round brackets: checkout: ret_node_num_list

    Args:
        inp_str: input string

    Returns:
        A tuple (ok, value_or_message): ok True and the extracted token when successful; otherwise False and an error message.
    """

    try:
        if not isinstance(inp_str, str):
            raise UnexpectedInputStringFormat("Input must be a string")

        processed_inp_str = inp_str.strip()

        # must contain brackets
        if ("(" not in processed_inp_str) or (")" not in processed_inp_str):
            raise UnexpectedInputStringFormat("round brackets not found in string")

        # must end with closing bracket
        if not processed_inp_str.endswith(")"):
            raise UnexpectedInputStringFormat(
                "The round brackets need to be at the end of the string"
            )

        # extract content inside the last pair of brackets
        idx = processed_inp_str.rfind("(")
        if idx == -1:
            raise UnexpectedInputStringFormat("round brackets not found in string")

        str_with_node_num = processed_inp_str[
            idx + 1 : -1
        ].strip()  # need not include ')' in the string
        if str_with_node_num == "":
            raise UnexpectedInputStringFormat(
                "Node number not found in between the brackets"
            )

        node_num = str_with_node_num
        return (True, node_num)

    except UnexpectedInputStringFormat as e:
        return (False, f"{e}")


def ret_node_number_list(inp_str):
    """From the input string, extract the comma-separated tokens inside the last pair of round brackets.
    INPUT STRING MUST HAVE COMMA SEPARATED NUMBER BETWEEN THE ROUND BRACKETS THAT ARE PRESENT AT THE END OF THE STRING
    ### POSSIBLE INPUTS:
        - INPUT(**, **, **, ...)
        - OUTPUT(**, **, **, ...)
        - (**, **, **, ...)
        #### the last case makes this function a generic one.
    Args:
        inp_str: Input string

    Returns:
        A tuple (ok, list_or_message): ok True and a list of extracted tokens when successful; otherwise False and an error message.
    """
    try:
        if not isinstance(inp_str, str):
            raise UnexpectedInputStringFormat("Input must be a string")

        processed_inp_string = inp_str.strip()

        # must contain brackets
        if ("(" not in processed_inp_string) or (")" not in processed_inp_string):
            raise UnexpectedInputStringFormat("round brackets not found in string")

        # must end with closing bracket
        if not processed_inp_string.endswith(")"):
            raise UnexpectedInputStringFormat(
                "Only the round brackets need to be at the end of the string"
            )

        # extract content inside the last pair of brackets
        open_idx = processed_inp_string.rfind("(")
        if open_idx == -1:
            raise UnexpectedInputStringFormat("round brackets not found in string")

        inner_content = processed_inp_string[open_idx + 1 : -1].strip()
        if inner_content == "":
            raise UnexpectedInputStringFormat(
                "Node numbers/list not found in between the brackets"
            )

        # split on commas and validate each token is an integer
        tokens = [token.strip() for token in inner_content.split(",")]
        # remove any empty tokens produced by consecutive commas
        tokens = [t for t in tokens if t != ""]
        if not tokens:
            raise UnexpectedInputStringFormat(
                "Node numbers/list not found in between the brackets, Check delimiter used to seperate node numbers within the round brackets"
            )
            

        return (True, tokens)

    except UnexpectedInputStringFormat as e:
        return (False, f"{e}")


class NodeInfo:
    """
    Class to immediately store the data about all inputs, output and the name of the gate.
    i.e.:
        sample input: 123 = AND(1,2,3)
    then the line is parsed:
        - output_node_num is set to 123
        - input_node_num_lst is set to [1,2,3] - without any change in the order!
        - gate_name is set to AND

    IF NO INPUT IS GIVEN WHILE INSTANTIATION, THEN A EMPTY OBJECT IS CREATED, NO EXCEPTION IS RAISED.
    IF INPUT IS OF NOT THE CORRECT FORMAT AS FOLLOWS, THEN UnexpectedInputStringFormat is raised.

    Class has no dependencies on any of the other code in this class!
    """

    def __init__(self, inp_str="default", do_validation=False):
        # output node number as string
        self.output_node_num = ""
        # list of input node tokens as strings
        self.input_node_list = []
        # gate name as string
        self.gate_name = ""
        # raw input string stored for later parsing
        self._inp_str = inp_str
        self.gate_number = ""

        if self._inp_str.lower() != "default":
            # if input is not default then process
            if do_validation:
                self._validate_input()
            self._populate_data()

    def _validate_input(self):
        if not isinstance(self._inp_str, str):
            raise UnexpectedInputStringFormat("Input must be a string")

        processed_inp_str = self._inp_str.strip()

        # must contain '(' and end with ')'
        if ("(" not in processed_inp_str) or (not processed_inp_str.endswith(")")):
            raise UnexpectedInputStringFormat("Input string is of unexpected format!")

        # must contain '=' separating output and gate spec
        if "=" not in processed_inp_str:
            raise UnexpectedInputStringFormat("Input string is of unexpected format!")

        left, right = processed_inp_str.split("=", 1)

        # left side must be an node number/string
        if not isinstance(left, str) or not left.strip():
            raise UnexpectedInputStringFormat("Input is not a valid string!")

        # right side must start with a gate name made of at least two letters followed by '('
        gate_spec = right.strip()
        open_paren_index = gate_spec.find("(")
        if open_paren_index == -1:
            raise UnexpectedInputStringFormat("Input string is of unexpected format!")

        gate_name = gate_spec[:open_paren_index].strip()
        if not re_fullmatch(r"[A-Za-z]{2,}", gate_name):
            raise UnexpectedInputStringFormat("Input string is of unexpected format!")

    def _populate_data(self):
        processed_inp_str = self._inp_str.strip()
        left, right = processed_inp_str.split("=", 1)
        left, right = left.strip(), right.strip()
        # output node number
        if not left:
            raise UnexpectedInputStringFormat("Could not extract output node number")
        self.output_node_num = left

        # gate name
        right_strip = right.strip()
        open_paren_index = right_strip.find("(")
        gate_name = right_strip[:open_paren_index].strip()
        if not re_fullmatch(r"[A-Za-z]{2,}", gate_name):
            raise UnexpectedInputStringFormat("Could not extract gate name")
        self.gate_name = gate_name
        self.gate_number = f"{gate_name}-{self.output_node_num}"

        # input node list - reuse existing helper
        ok, result = ret_node_number_list(processed_inp_str)
        if not ok:
            raise UnexpectedInputStringFormat(str(result))
        self.input_node_list = [str(x) for x in result]

    def store_info_from_string(self, inp_str, do_validation=False):
        self._inp_str = inp_str
        if do_validation:
            self._validate_input()
        self._populate_data()


# region: NLDM related parsing
def ret_name_and_logic_type(cell_line):
    """Extract cell name and logic type from a liberty cell definition line like: "cell (NAND2_X1) {".

    Args:
        cell_line: A line expected to be in the format "cell (CellName) {".

    Raises:
        UnexpectedInputStringFormat: If parsing fails for various format issues.

    Returns:
        A tuple (name, logic_type) where both are strings.
    """
    try:
        line = cell_line.lower().strip()
        if not line.startswith(TXT_CELL):
            raise UnexpectedInputStringFormat("Not a cell definition line")

        open_parenthesis = line.find("(")
        close_parenthesis = line.find(")", open_parenthesis + 1)
        if open_parenthesis == -1 or close_parenthesis == -1: # closen paren can be -1 only if '{' is missing.
            raise UnexpectedInputStringFormat("Cell line missing parentheses")

        #derive anme
        raw_name = line[open_parenthesis + 1 : close_parenthesis]
        name = raw_name.strip().upper()

        #derive logic type - by taking characters from the start of the name until we hit a non-alphabetic character
        base = raw_name.split("_", 1)[0]
        logic_chars = []
        for ch in base:
            if ch.isalpha():
                logic_chars.append(ch)
            else:
                break
        logic_type = "".join(logic_chars).upper()

        if not logic_type:
            raise UnexpectedInputStringFormat("Could not derive logic type from cell name")

        return (name, logic_type)
    except UnexpectedInputStringFormat:
        raise
    except Exception as e:
        raise UnexpectedInputStringFormat(f"Error parsing cell name: {e}") from e


def ret_value_for_label(line):
    """Extract capacitance value from a line in the format "capacitance : value;".

    Args:
        line: A line expected to define capacitance, e.g. "capacitance : 0.123;".

    Raises:
        UnexpectedInputStringFormat: On parsing errors or invalid value.

    Returns:
        The capacitance value as a float.
    """
    try:
        text = line.strip().lower()
        if TXT_CAPACITANCE  not in text:
            raise UnexpectedInputStringFormat("Line does not contain capacitance")

        if ":"  not in text:
            raise UnexpectedInputStringFormat("Unexpected capacitance line format")

        left, sep, right = text.partition(":")
        if right.endswith(";"):
            right = right[:-1].strip()

        return float(right)
    except ValueError as e:
        raise UnexpectedInputStringFormat(f"Could not convert capacitance to float: {e}") from e


def ret_nums_in_str(line):
    """Extract a list of float values from a line containing quoted comma-separated values, e.g., '"0.1, 0.2"'.

    Args:
        line: A line containing quoted comma-separated numeric values.

    Raises:
        UnexpectedInputStringFormat: If parsing fails or conversion to float fails.

    Returns:
        A list of float values extracted from the quoted segment.
    """
    try:
        text = line.strip()
        first_quote = text.find('"')
        last_quote = text.rfind('"')
        if first_quote == -1 or last_quote == -1 or last_quote <= first_quote:
            raise UnexpectedInputStringFormat("Index line missing quoted values")

        # extract the substring between the quotes characters and split on commas
        actual_str = text[first_quote + 1 : last_quote] 
        tokens = [token.strip() for token in actual_str.split(",") if token.strip() != ""]

        return [float(token) for token in tokens]
    
    except ValueError as e:
        raise UnexpectedInputStringFormat(f"Could not convert index to floats: {e}") from e


def ret_2d_list_from_str(lines):
    """Extract a 2D list of float values from a block of lines containing quoted comma-separated values.
        - sample input lines:
            => ["0.00474878,0.00814768,0.0123804,0.0208480,0.0377848,0.0716838,0.139435", 
                "0.00475427,0.00814708,0.0123814,0.0208446,0.0377762,0.0716641,0.139428",
                "0.00779760,0.00997800,0.0130179,0.0208500,0.0378031,0.0716776,0.139430",
                "0.0122628,0.0156758,0.0191464,0.0247382,0.0382858,0.0716833,0.139437",
                "0.0178385,0.0220827,0.0266676,0.0342116,0.0458454,0.0726908,0.139429",
                "0.0249336,0.0298045,0.0352101,0.0445099,0.0592803,0.0822832,0.139806",
                "0.0337631,0.0391600,0.0452534,0.0559346,0.0736025,0.100571,0.148264"]d
    Args:
        lines: A list of lines containing quoted comma-separated values.

    Raises:
        UnexpectedInputStringFormat: On parsing or conversion failures.

    Returns:
        A 2D list (list of lists) of floats extracted from each line.
    """
    rows = []  # to store the 2D list
    for line in lines:
        line = line.strip()
        first_quote = line.find('"')
        last_quote = line.rfind('"')
        if first_quote == -1 or last_quote == -1 or last_quote <= first_quote:
            continue

        inner = line[first_quote + 1 : last_quote]
        tokens = [token.strip() for token in inner.split(",") if token.strip() != ""]
        if not tokens:
            continue

        try:
            row = [float(token) for token in tokens]
        except ValueError as e:
            raise UnexpectedInputStringFormat(f"Error parsing values row: {e}") from e
        rows.append(row)

    return rows

# region: interpolation related helper functions
def find_bounds(vals, x):
    """Find the indices of two entries in vals that bound x.

    Args:
        vals: A list of values sorted in ascending order.
        x: The value to locate within vals.

    Returns:
        A tuple (i_low, i_high) of indices bounding x.
    """
    if not vals:
        return (0, 0)

    if x <= vals[0]:
        return (0, 0)

    n = len(vals)
    for i in range(1, n):
        if x < vals[i]:
            return (i - 1, i)

    return (n - 1, n - 1)


def lut_lookup_2d(idx1, idx2, table, tau_ns, cap_ff):
    """Perform 2D LUT lookup with bilinear interpolation for the given indices and table.

    Args:
        idx1: First-dimension index list (e.g., time).
        idx2: Second-dimension index list (e.g., capacitance).
        table: 2D table of LUT values.
        tau_ns: Query value along first dimension.
        cap_ff: Query value along second dimension.

    Returns:
        Interpolated LUT value for the given query point.
    """
    if not idx1 or not idx2 or not table:
        raise ValueError("Empty LUT indices/table")

    i1, i2 = find_bounds(idx1, tau_ns)
    j1, j2 = find_bounds(idx2, cap_ff)

    v11 = table[i1][j1]
    if i1 == i2 and j1 == j2:
        return v11

    # 1D along cap
    if i1 == i2 and j1 != j2:
        c1, c2 = idx2[j1], idx2[j2]
        if c2 == c1:
            return v11
        v12 = table[i1][j2]
        return v11 + (v12 - v11) * (cap_ff - c1) / (c2 - c1)

    # 1D along tau
    if j1 == j2 and i1 != i2:
        t1, t2 = idx1[i1], idx1[i2]
        if t2 == t1:
            return v11
        v21 = table[i2][j1]
        return v11 + (v21 - v11) * (tau_ns - t1) / (t2 - t1)

    # True 2D bilinear
    t1, t2 = idx1[i1], idx1[i2]
    c1, c2 = idx2[j1], idx2[j2]
    if (t2 == t1) or (c2 == c1):
        return v11

    v12 = table[i1][j2]
    v21 = table[i2][j1]
    v22 = table[i2][j2]
    
    # bilinear interpolation formula
    num = (
        v11 * (c2 - cap_ff) * (t2 - tau_ns)
        + v12 * (cap_ff - c1) * (t2 - tau_ns)
        + v21 * (c2 - cap_ff) * (tau_ns - t1)
        + v22 * (cap_ff - c1) * (tau_ns - t1)
    )
    den = (c2 - c1) * (t2 - t1)
    interpolated_value = num / den

    return interpolated_value


def fmt_ps(x_ns):
    import math
    if math.isinf(x_ns):
        return "inf"
    ps = x_ns * 1000.0
    s = f"{ps:.5f}"
    s = s.rstrip("0").rstrip(".")
    if s == "-0":
        s = "0"
    return s








if __name__ == "__main__":
    verify_file_path("c7552.bench")
    for line in chunked_line_reader("c7552.bench"):
        if "INPUT" in line:
            print(f">>>>> {line}:")
        elif "OUTPUT" in line:
            print(f"<<<<< {line}:")
        else:
            print(line)

    pass
