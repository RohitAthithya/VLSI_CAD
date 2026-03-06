from collections import defaultdict
from platform import node
from tkinter import N
from typing import NewType
from proj_utils import *

IO_PIND_ARE_PRIMARY = True
BENCHFILE_LINE_COMMENT = "#"
BENCHFILE_LINE_INPUT = "INPUT"
BENCHFILE_LINE_OUTPUT = "OUTPUT"


@print_dashed_lines
def print_output():
    print("hello")


class Gate:
    def __init__(self, name, inp_wire, output_wire):
        self.name = name
        self.fan_in = list()
        self.fan_out = list()
        self.fan_in.append(inp_wire)
        self.fan_out.append(output_wire)


class Netlist:
    """Class to verify and process the bench file"""

    def __init__(self, bench_file_path: FilePath, verify=False):
        # check bench file validity
        path_validity = verify_file_path(bench_file_path)
        if not path_validity[0]:
            raise Exception(f"{path_validity[1]}")

        self.inp_file_path = bench_file_path
        # create warning list to note down discrepancies
        self.warning_list = list()
        # note down the info from comments about inputs, outputs, inverters(NOT) and the gates
        # create sets to store input and output nodes
        self.input_pins = dict()
        self.output_pins = dict()
        # create adjacency list to store the nodes: defines the netlist

        # process and create the netlist
        self.process_bench_file(verify)

    def process_bench_file(self, warnings_are_errors: bool = False):
        """Read the bench file line by line, verify the format and build the adjacency list!

        Args:
            inp_file_path (FilePath): _description_
            warnings_are_errors (bool, optional): _description_. Defaults to False.
        """
        self.current_input_nodes = set()
        self.current_output_nodes = set()
        self.gates_info = defaultdict(Gate)
        self.netlist_DAG = defaultdict(list)

        for idx, line in enumerate(chunked_line_reader(self.inp_file_path)):
            if line.strip() == "":
                continue
            elif line.startswith(BENCHFILE_LINE_COMMENT):
                self.process_comment_info()
            elif line.upper().startswith(BENCHFILE_LINE_INPUT):
                self.process_input_info(line)
            elif line.upper().startswith(BENCHFILE_LINE_OUTPUT):
                self.process_output_info(line)
            else:  # it must be a line with node info
                self.process_node_info(line)

    def process_comment_info(self):
        pass

    def process_input_info(self, line):
        node_info = ret_node_number(line)
        self.input_pins.update({node_info: 0})

    def process_output_info(self, line):
        node_info = ret_node_number(line)
        self.output_pins.update({node_info: 0})

    def process_node_info(self, line):
        try:
            inp_name = ""
            output_name = ""
            node_info = NodeInfo(line, do_validation=True)
            self.current_input_nodes.union(set(node_info.input_node_list))
            self.current_output_nodes.add(node_info.output_node_num)
            for inp in node_info.input_node_list:
                if inp in self.current_output_nodes:
                    inp_name = f"{node_info.gate_name}-{inp}"
                else:
                    inp_name = f"INPUT-{inp}"

                output_name = f"{node_info.gate_name}-{node_info.output_node_num}"
                if inp_name in self.netlist_DAG:
                    self.netlist_DAG[inp_name].append(output_name)
                else:
                    self.netlist_DAG.update({inp_name: [output_name]})

                # populate gate info
                if output_name in self.gates_info:
                    self.gates_info[output_name].fan_in.append(inp_name)
                else:
                    self.gates_info.update({output_name: [inp_name]})

                if (node_info.gate_name in inp_name) and (inp_name in self.gates_info):
                    

        except:
            print("erroneous file, node information is not proper!")
            # TODO: handle this separately

    def info_fan_in():

        pass

    def info_fan_out():

        pass


if __name__ == "__main__":
    filepath = "c17.bench"
    obj = Netlist(filepath)
    # obj.process_bench_file()

    print("done")
