from pathlib import Path
from os.path import exists as os_exists
from typing import NewType
from re import fullmatch as re_fullmatch, findall as re_findall


ErrorMessage = NewType("ErrorMessage", str)
SuccessMessage = NewType("SuccessMessage", str)
InputFileText = NewType("InputFileText", list[str])


# CONSTANTS
ENCODING_FORMAT_DEFAULT = "utf-8"
BIN_DATA_CHUNK_SIZE = 8192  # 8kibi at a time
DASHED_LINES = "".join(["-" for i in range(32)])

# TEXT CONSTANTS
TXT_FILE_PRESENT = "File present at given path, user can read!"
TXT_FILE_MISSING = "File not found at given path"


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
def verify_file_path(
    file_path: str | Path,
) -> tuple[bool, SuccessMessage | ErrorMessage]:
    """Verify if the input file path is a valid file

    Args:
        file_path (str | Path): file path as string or name or Path variable

    Returns:
        tuple[bool, SuccessMessage | ErrorMessage]:
            - if given file exists - returns : (True, "file present at given path")
            - if given file does not exist - returns: (False, "File not found at given path!")
    """
    try:
        # convert input to Path object
        file_path = Path(file_path)

        # check if file exists using the os.path.exists method
        os_exists(file_path)

        # all good: then return (True, TXT_FILE_PRESENT)
        return (True, TXT_FILE_PRESENT)
    except TypeError:
        return (False, "Input must be of string or Path data type")
    except FileNotFoundError:
        return (False, f"{TXT_FILE_MISSING}: {file_path}")


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

        if not re_fullmatch(r"\d+", str_with_node_num):
            raise UnexpectedInputStringFormat(
                "Node number not found in between the brackets"
            )

        node_num = int(str_with_node_num)
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

        for token in tokens:
            if not re_fullmatch(r"\d+", token):
                raise UnexpectedInputStringFormat(
                    "Node number not found in between the brackets"
                )

        lst_node_numbers = [int(t) for t in tokens]
        return (True, lst_node_numbers)

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
        self._output_node_num: int = int()
        self._input_node_list: list[int] = list()
        self._gate_name: str = str()
        self._inp_str: str = (
            inp_str  # if user pases any randomn object the validate input is gonna throu wit of!
        )

        # TODO: create the getters for the members but no setters
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

        # left side must be an integer (possibly with surrounding spaces)
        if not re_fullmatch(r"\s*\d+\s*", left):
            raise UnexpectedInputStringFormat("Input string is of unexpected format!")

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
        mo = re_findall(r"\d+", left)
        if not mo:
            raise UnexpectedInputStringFormat("Could not extract output node number")
        self._output_node_num = int(mo[0])

        # gate name
        right_strip = right.strip()
        open_paren_index = right_strip.find("(")
        gate_name = right_strip[:open_paren_index].strip()
        if not re_fullmatch(r"[A-Za-z]{2,}", gate_name):
            raise UnexpectedInputStringFormat("Could not extract gate name")
        self._gate_name = gate_name

        # input node list - reuse existing helper
        ok, result = ret_node_number_list(processed_inp_str)
        if not ok:
            raise UnexpectedInputStringFormat(result)
        self._input_node_list = result

    def store_info_from_string(self, inp_str: str, do_validation: bool = False):
        self._inp_str = inp_str
        if do_validation:
            self._validate_input()
        self._populate_data()


# endregion: input file processing methods

if __name__ == "__main__":
    verify_file_path("c17.bench")
    for line in chunked_line_reader("c17.bench"):
        if "INPUT" in line:
            print(f">>>>> {line}:")
        elif "OUTPUT" in line:
            print(f"<<<<< {line}:")
        else:
            print(line)

    pass
