#generic imports
from argparse import ArgumentParser
from collections import defaultdict, OrderedDict
from pathlib import Path

#custom imports
from proj_utils import *

BENCHFILE_LINE_COMMENT = "#"
BENCHFILE_LINE_INPUT = "INPUT"
BENCHFILE_LINE_OUTPUT = "OUTPUT"


class Gate:
    def __init__(self, gate_type: str, output_wire: str, input_wires: list[str]):
        self.gate_type = gate_type.upper()
        self.output_wire = str(output_wire)
        self.name = f"{self.gate_type}-{self.output_wire}"
        self.input_wires = [str(x) for x in input_wires]
        self.fanin = []
        self.fanout = []


class Netlist:
    def __init__(self, bench_file_path: FilePath, verify=False):
        ok, msg = verify_file_path(bench_file_path)
        if not ok:
            raise FileNotFoundError(msg)
        self.warning_list = list()

        # process the bench file
        self.inp_file_path = Path(bench_file_path)
        self.input_pins = OrderedDict()
        self.output_pins = OrderedDict()
        self.gates = OrderedDict()
        self.wire_to_gate = {}
        self.gate_type_counts = defaultdict(int)

        self.process_bench_file(verify=verify)
        self.build_connectivity()

    def process_bench_file(self, verify=False):
        """Read the bench file line by line, verify the format and build the adjacency list!

        Args:
            verify (bool, optional): if True, verify the format of each line. Defaults to False.
        """   

        for raw_line in chunked_line_reader(self.inp_file_path):
            line = raw_line.strip()
            if not line or line.startswith(BENCHFILE_LINE_COMMENT):
                continue
            if line.upper().startswith(BENCHFILE_LINE_INPUT):
                self.process_input_info(line)
            elif line.upper().startswith(BENCHFILE_LINE_OUTPUT):
                self.process_output_info(line)
            else:  # it must be a line with node info
                self.process_node_info(line)

    def process_input_info(self, line: str):
        ok, node_num = ret_node_number(line)
        if not ok:
            raise UnexpectedInputStringFormat(node_num)
        self.input_pins[str(node_num)] = f"INPUT-{node_num}"

    def process_output_info(self, line: str):
        ok, node_num = ret_node_number(line)
        if not ok:
            raise UnexpectedInputStringFormat(node_num)
        self.output_pins[str(node_num)] = f"OUTPUT-{node_num}"

    def process_node_info(self, line: str):
        node_info = NodeInfo(line, do_validation=True)
        gate = Gate(
            gate_type=node_info.gate_name,
            output_wire=node_info.output_node_num,
            input_wires=node_info.input_node_list,
        )
        self.gates[gate.name] = gate
        self.wire_to_gate[gate.output_wire] = gate.name
        self.gate_type_counts[gate.gate_type] += 1

    def build_connectivity(self):
        for gate in self.gates.values():
            fanin_nodes = []
            for inp_wire in gate.input_wires:
                if inp_wire in self.wire_to_gate:
                    fanin_nodes.append(self.wire_to_gate[inp_wire])
                else:
                    fanin_nodes.append(f"INPUT-{inp_wire}")
            gate.fanin = fanin_nodes

        for gate in self.gates.values():
            consumers = []
            gate_wire = gate.output_wire
            for other_gate in self.gates.values():
                if gate is other_gate:
                    continue
                if gate_wire in other_gate.input_wires:
                    consumers.append(other_gate.name)
            if gate_wire in self.output_pins:
                consumers.append(f"OUTPUT-{gate_wire}")
            gate.fanout = consumers

    def write_ckt_details(self, output_path="ckt_details.txt"):
        with open(output_path, "w", encoding=ENCODING_FORMAT_DEFAULT) as f:
            f.write(f"# {len(self.input_pins)} primary inputs\n")
            f.write(f"# {len(self.output_pins)} primary outputs\n")

            for gate_type in sorted(self.gate_type_counts.keys()):
                count = self.gate_type_counts[gate_type]
                f.write(f"{count} {gate_type} gates\n")

            f.write("\n")
            f.write("Fanout...\n")
            for gate_name, gate in self.gates.items():
                f.write(f"{gate_name}: {', '.join(gate.fanout)}\n")

            f.write("\n")
            f.write("Fanin...\n")
            for gate_name, gate in self.gates.items():
                f.write(f"{gate_name}: {', '.join(gate.fanin)}\n")





def main(file_name):
    # TODO:need to implement the argparser
    # todo: call the above functions to read the bench file and write the ckt details to a text file
    netlist = Netlist(file_name)
    netlist.write_ckt_details(F"ckt_details{file_name}.txt")

    pass


if __name__ == "__main__":
    file_name = "c17.bench"
    main(file_name)
