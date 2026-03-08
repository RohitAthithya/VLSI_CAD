# imports
from pathlib import Path
from os.path import exists as os_exists
from typing import NewType
from re import fullmatch as re_fullmatch, findall as re_findall

# custom type aliases
ErrorMessage = NewType("ErrorMessage", str)
SuccessMessage = NewType("SuccessMessage", str)
InputFileText = NewType("InputFileText", list[str])
FilePath = NewType("FilePath", str)


# CONSTANTS
ENCODING_FORMAT_DEFAULT = "utf-8"
BIN_DATA_CHUNK_SIZE = 8192  # 8kibi at a time
DASHED_LINES = "".join(["-" for i in range(32)])

# TEXT CONSTANTS
TXT_FILE_PRESENT = "File present at given path, user can read!"
TXT_FILE_MISSING = "File not found at given path"
TXT_CELL = "cell"
TXT_CAPACITANCE = "capacitance"
TXT_INDEX_1 = "index_1" 
TXT_INDEX_2 = "index_2"


# CUSTOM EXCEPTIONS:
class UnexpectedInputStringFormat(Exception):
    def __init__(self, message: str = "Input string was of unexpected format"):
        super().__init__(message)
class UnexpectedFileFormatError(Exception):
    def __init__(self, message: str = "Input File was of unexpected format"):
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
def verify_file_path(file_path: str | Path) -> tuple[bool, SuccessMessage | ErrorMessage]:
    """Verify if the input file path is a valid file

    Args:
        file_path (str | Path): file path as string or name or Path variable

    Returns:
        tuple[bool, SuccessMessage | ErrorMessage]:
            - if given file exists - returns : (True, "file present at given path")
            - if given file does not exist - returns: (False, "File not found at given path : {path given}")
            - if input is not of type string or Path - returns: (False, "Input must be of string or Path data type")
    """
    try:
        file_path = Path(file_path)
        if file_path.exists() and file_path.is_file():
            return (True, TXT_FILE_PRESENT)
        return (False, f"{TXT_FILE_MISSING}: {file_path}")
    except TypeError:
        return (False, "Input must be of string or Path data type")



def chunked_line_reader(
    file_path: Path, chunk_size=BIN_DATA_CHUNK_SIZE, encoding=ENCODING_FORMAT_DEFAULT
):
    """Read input file and yield each line of the text

    Args:
        file_path (Path): Must be a WindowsPath datatype, else error not handled
        chunk_size (str, optional): Chunk size to process at a time. This affects, how much data is processed at a time in the RAM.\
            If files are huge better to stick with default value. Defaults to BIN_DATA_CHUNK_SIZE.
        encoding (str, optional):encoding format of file. Defaults to ENCODING_FORMAT_DEFAULT.

    Yields:
        str: each line in the file @ path: file_path (input)

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
def ret_node_number(inp_str: str) -> tuple[bool, int | ErrorMessage]:
    """### From the input string, find the integers at the end string surrounded with brackets
    INPUT MUST HAVE A NUMBER ENCLOSED WITH ROUND BRACKETS PRESENT AT THE END OF THE STRING:
    ### POSSIBLE INPUTS:
        - INPUT(**)
        - OUTPUT(**)

    ## If you are looking to get list of numbers within the round brackets: checkout: ret_node_num_list

    Args:
        inp_str (str): input string

    Returns:
        if input is valid and number found:
            (True, int): True says that number was found, int is node number
        otherwise:
            (False, ErrorMessage): Error message if the INPUT was wrong or if the node number was not found
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


def ret_node_number_list(inp_str: str) -> tuple[bool, list[int] | ErrorMessage]:
    """### From the input string, Extract the list of node numbers list at the end of the string surrounded with brackets
    INPUT STRING MUST HAVE COMMA SEPARATED NUMBER BETWEEN THE ROUND BRACKETS THAT ARE PRESENT AT THE END OF THE STRING
    ### POSSIBLE INPUTS:
        - INPUT(**, **, **, ...)
        - OUTPUT(**, **, **, ...)
        - (**, **, **, ...)
        #### the last case makes this function a generic one.
    Args:
        inp_str (str): Input string

    Returns:
        if input is valid and number found:
            (True, list[int]): True says that number was found, int is node number
        otherwise:
            (False, ErrorMessage): Error message if the INPUT was wrong or if the node number was not found
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

    def __init__(
        self, inp_str: str = "default", do_validation=False
    ):  # optional input, as programmer may intend to parse data later, but has to use the store_info_from_string method!
        self.output_node_num: str = str()
        self.input_node_list: list[str] = list()
        self.gate_name: str = str()
        # if user pases any randomn object the validate input is gonna throw it of!
        self._inp_str: str = inp_str
        self.gate_number: str = ""

        if self._inp_str.lower() != "default":
            # if input is not default then process
            if do_validation:
                self._validate_input()
            self._populate_data()

    def _validate_input(self) -> None:
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

    def _populate_data(self) -> None:
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

    def store_info_from_string(self, inp_str: str, do_validation: bool = False) -> None:
        self._inp_str = inp_str
        if do_validation:
            self._validate_input()
        self._populate_data()


# region: NLDM related parsing
def ret_name_and_logic_type(cell_line: str) -> tuple[str, str]:
    """ Extract cell name and logic type from a liberty cell definition line like:
            -> "cell (NAND2_X1) {"

    Args:
        cell_line (str): A line from a liberty file that defines a cell, expected to be in the format "cell (CellName) {"

    Raises:
        UnexpectedInputStringFormat:    
            - If the line does not start with "cell"
            - If the line does not contain parentheses around the cell name
            - If the cell name does not contain any alphabetic characters to derive logic type from
            - If any other error occurs during parsing, a generic error message with details is raised as UnexpectedInputStringFormat

    Returns:
        tuple[str, str]: A tuple containing:
            - name (str): The extracted cell name (e.g., "NAND2_X1")
            - logic_type (str): The derived logic type in uppercase (e.g., "NAND")

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


def ret_value_for_label(line: str) -> float:
    """ Extract capacitance value from a line in the format "capacitance : value;" 
            (case-insensitive, with optional whitespace)
        - sample input:
            "capacitance : 0.123;"

    Args:
        line (str): A line from a liberty file expected to define capacitance, e.g., 
        "capacitance : 0.123;"

    Raises:
        UnexpectedInputStringFormat: 
            - If the line does not contain the word "capacitance"
            - If the line does not contain a colon separating the label and value
            - If the value cannot be converted to a float
            - If any other error occurs during parsing, a generic error message with details is raised as UnexpectedInputStringFormat

    Returns:
        float: capacitance value
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


def ret_nums_in_str(line: str) -> list[float]:
    """ Extract a list of float values from a line containing quoted comma-separated values, e.g., '"0.1, 0.2, 0.3"'
            - sample input line:
                => index_1 ("0.00117378,0.00472397,0.0171859,0.0409838,0.0780596,0.130081,0.198535");
    Args:
        line (str): A line from a liberty file containing quoted comma-separated values

    Raises:
        UnexpectedInputStringFormat: 
            - If the line does not contain properly quoted comma-separated values
            - If any of the values cannot be converted to a float

    Returns:
        list[float]: A list of extracted float values
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


def parse_values_block(lines: list[str]) -> list[list[float]]:
    """ Extract a 2D list of float values from a block of lines containing quoted comma-separated values, e.g.,
        - sample input lines:
            => ["0.00474878,0.00814768,0.0123804,0.0208480,0.0377848,0.0716838,0.139435", 
                "0.00475427,0.00814708,0.0123814,0.0208446,0.0377762,0.0716641,0.139428",
                "0.00779760,0.00997800,0.0130179,0.0208500,0.0378031,0.0716776,0.139430",
                "0.0122628,0.0156758,0.0191464,0.0247382,0.0382858,0.0716833,0.139437",
                "0.0178385,0.0220827,0.0266676,0.0342116,0.0458454,0.0726908,0.139429",
                "0.0249336,0.0298045,0.0352101,0.0445099,0.0592803,0.0822832,0.139806",
                "0.0337631,0.0391600,0.0452534,0.0559346,0.0736025,0.100571,0.148264"]d
    Args:
        lines (list[str]): A list of lines from a liberty file containing quoted comma-separated values in section: values ( .... )

    Raises:
        UnexpectedInputStringFormat: 
            - If any line does not contain properly quoted comma-separated values
            - If any of the values cannot be converted to a float

    Returns:
        list[list[float]]: 
            - A 2D list of extracted float values, where each inner list corresponds to the values extracted 
                from one line in the input block
    """    
    rows: list[list[float]] = [] # to store the 2D list
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
