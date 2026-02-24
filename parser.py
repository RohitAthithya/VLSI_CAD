from collections import defaultdict
from typing import Newtype
from proj_utils import *

IO_PIND_ARE_PRIMARY = True
BENCHFILE_LINE_COMMENT = "#"
BENCHFILE_LINE_INPUT = "INPUT"
BENCHFILE_LINE_OUTPUT = "OUTPUT"


@print_dashed_lines
def print_output():
    print("hello")


class Netlist:
    """Class to verify and process the bench file"""

    def __init__(self, bench_file_path: FilePath, verify=False):
        # check bench file validity
        path_validity = verify_file_path(bench_file_path)
        if not path_validity[0]:
            raise Exception(f"{path_validity[1]}")

        # create warning list to note down discrepancies
        self.warning_list = list()
        # note down the info from comments about inputs, outputs, inverters(NOT) and the gates
        # create sets to store input and output nodes
        self.input_pins = dict()
        self.output_pins = dict()
        # create adjacency list to store the nodes: defines the netlist

        # process and create the netlist
        self.process_bench_file(bench_file_path, verify)

    def process_bench_file(
        self, inp_file_path: FilePath, warnings_are_errors: bool = False
    ):
        """Read the bench file line by line, verify the format and build the adjacency list!

        Args:
            inp_file_path (FilePath): _description_
            warnings_are_errors (bool, optional): _description_. Defaults to False.
        """
        self.current_input_nodes = set()
        self.current_output_nodes = set()
        self.gates_info = dict()
        self.netlist_DAG = defaultdict(list)

        for idx, line in enumerate(chunked_line_reader(inp_file_path)):
            if line.startswith(BENCHFILE_LINE_COMMENT):
                self.process_comment_info()
            elif line.upper().startswith(BENCHFILE_LINE_INPUT):
                self.process_input_info()
            elif line.upper().startswith(BENCHFILE_LINE_OUTPUT):
                self.process_output_info()
            else:  # it must be a line with node info
                try:
                    node_info = NodeInfo(line, do_validation=True)
                    output_node = node_info.output_node_num
                    input_nodes = node_info.input_node_list
                    gate_name = node_info.gate_name.upper()

                    for inp in input_nodes:
                        self.netlist_DAG[inp].append(output_node)

                except:
                    print("erroneous file, node information is not proper!")
                    # TODO: handle this separately

    def process_comment_info(self):
        pass

    def process_input_info(self):
        node_info = ret_node_number()
        self.input_pins.update({node_info: 0})

    def process_output_info(self):
        node_info = ret_node_number()
        self.output_pins.update({node_info: 0})

    def info_fan_in():

        pass

    def info_fan_out():

        pass


if __name__ == "__main__":
    print_output()
