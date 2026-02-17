from pathlib import Path
from os.path import exists as os_exists
from typing import NewType


ErrorMessage = NewType("ErrorMessage", str)
SuccessMessage = NewType("SuccessMessage", str)
InputFileText = NewType("InputFileText", list[str])


# CONSTANTS
ENCODING_FORMAT_DEFAULT = "utf-8"
BIN_DATA_CHUNK_SIZE = 8192  # 8kibi at a time

# TEXT CONSTANTS
TXT_FILE_PRESENT = "File present at given path, user can read!"
TXT_FILE_MISSING = "File not found at given path"

# output:
# output header and footer
DASHED_LINES = "".join(["-" for i in range(32)])

# region: WRAPPERS
#


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

if __name__ == "__main__":
    verify_file_path("c17.bench")
    for line in chunked_line_reader("c17.bench"):
        if "INPUT" in line:
            print(f">>>>> {line}:")
        elif "OUTPUT" in line:
            print(f"<<<<< {line}:")
        else:
            print(line)
