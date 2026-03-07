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
    """ Gate class to represent a logic gate in the netlist.
    Attributes:
        gate_type (str): The type of the gate (e.g., AND, OR, NOT).
        output_wire (str): The output wire of the gate. also known as fanout(s).
        input_wires (list[str]): The list of input wires to the gate. also known as fanin(s).

        fanin (list[str]): The list of gates that feed into this gate. (updated based on connectivity)
        fanout (list[str]): The list of gates that this gate feeds into. (updated based on connectivity)
    """    
    def __init__(self, gate_type: str, output_wire: str, input_wires: list[str]):
        """ Initialize a gate with its type, output wire, and input wires.

        Args:
            gate_type (str): _description_
            output_wire (str): _description_
            input_wires (list[str]): _description_
        """        
        self.gate_type: str = gate_type.upper()
        self.output_wire: str = str(output_wire)
        self.name: str = f"{self.gate_type}-{self.output_wire}"
        self.input_wires: list[str] = [str(x) for x in input_wires]
        self.fanin: list[str] = []
        self.fanout: list[str] = []


class Netlist:
    """ ## Netlist class to represent the netlist of a circuit parsed from a .bench file.
    Note: A input to output traversal on the netlist provides the topological order of the gates in the circuit.
    An output to input traversal provides the slack calculation order for static timing analysis.

    ### Attributes:
        inp_file_path (Path):
            - The path to the input .bench file.
        input_pins (OrderedDict):
            - A mapping of input node numbers to their names. (fanins)
        output_pins (OrderedDict):
            - A mapping of output node numbers to their names. (fanouts)
        gates (OrderedDict):
            - A mapping of gate names to their Gate objects.
        wire_to_gate (dict):
            - A mapping of wire numbers to the gate that produces them.
        gate_type_counts (defaultdict):
            - A count of each type of gate in the netlist.
    
    ### Methods:
        __init__(self, bench_file_path: FilePath, verify=False): 
            - Initializes the Netlist object by processing the .bench file and building connectivity.
        process_bench_file(self, verify=False): 
            - Reads the .bench file line by line, verifies the format, and builds the adjacency list.
        process_input_info(self, line: str): 
            - Processes a line that defines an input pin and updates the input_pins mapping.
        process_output_info(self, line: str): 
            - Processes a line that defines an output pin and updates the output_pins mapping.
        process_node_info(self, line: str): 
            - Processes a line that defines a gate and updates the gates mapping and wire_to_gate mapping.
        build_connectivity(self): 
            - Builds the fanin and fanout lists for each gate based on the input wires and output wires.
        write_ckt_details(self, output_path:str|FilePath): 
            - Writes details of the circuit to a specified output file, including counts of inputs, outputs, gate types, and connectivity information.
    
    ### Exceptions:
        FileNotFoundError: 
            Raised when the provided .bench file path is invalid.
        UnexpectedInputStringFormat: 
            Raised when a line in the .bench file does not conform to expected formats for input, output, or gate definitions.

    ### example usage:
        netlist = Netlist("c17.bench")
        netlist.write_ckt_details("c17_details.txt")

    """    
    
    def __init__(self, bench_file_path: FilePath, verify:bool=False) -> None:
        """ Initialize the Netlist object by processing the .bench file and building connectivity.

        Args:
            bench_file_path (FilePath): The path to the .bench file to be processed.
            verify (bool, optional): Whether to verify the format of each line. Defaults to False.

        Raises:
            FileNotFoundError: Raised when the provided .bench file path is invalid or does not follow the expected format.
        """        
        ok, msg = verify_file_path(bench_file_path)
        if not ok:
            raise FileNotFoundError(msg)

        self.inp_file_path: Path = Path(bench_file_path)
        self.input_pins: OrderedDict[str, str] = OrderedDict()
        self.output_pins: OrderedDict[str, str] = OrderedDict()
        self.gates: OrderedDict[str, Gate] = OrderedDict()
        self.wire_to_gate: dict[str, str] = {}
        self.gate_type_counts: defaultdict[str, int] = defaultdict(int)
        # self.warning_list: list[str] = list() # can be used to store warnings - instead of raising exceptions

        self.process_bench_file(verify=verify)
        self.build_connectivity()

    def process_bench_file(self, verify=False) -> None:
        """Read the bench file line by line, verify the format and build the adjacency list!

        Args:
            verify (bool, optional): 
                - if True, verify the format of each line. Defaults to False.
                - if False, assume format is okay, start processing as such
        Raises:
            UnexpectedInputStringFormat: 
                - Raised when a line in the .bench file does not conform to expected formats for input, output, or gate definitions.

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

    def process_input_info(self, line: str) -> None:
        """ ## Processes a line that defines an input pin and updates the input_pins mapping.

        ### Args:
            line (str): 
                - line from bench file: 
                - Expected format: 'INPUT(<node_num>)'

        ### Raises:
            UnexpectedInputStringFormat: if line is of unexpected format
        """        
        ok, node_num = ret_node_number(line)
        if not ok:
            raise UnexpectedInputStringFormat(node_num)
        self.input_pins[str(node_num)] = f"INPUT-{node_num}"

    def process_output_info(self, line: str) -> None:
        
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

    def write_ckt_details(self, output_path:str|FilePath):
        with open(output_path, "w", encoding=ENCODING_FORMAT_DEFAULT) as f:
            f.write(f"{len(self.input_pins)} primary inputs\n")
            f.write(f"{len(self.output_pins)} primary outputs\n")

            line_to_print = []
            for gate_type in sorted(self.gate_type_counts.keys()):
                count = self.gate_type_counts[gate_type]
                line_to_print.append(f"{count} {gate_type}")
            f.write(f"{', '.join(line_to_print)} gates\n")

            f.write("\n")
            f.write("Fanout...\n")
            for gate_name, gate in self.gates.items():
                f.write(f"{gate_name}: {', '.join(gate.fanout)}\n")

            f.write("\n")
            f.write("Fanin...\n")
            for gate_name, gate in self.gates.items():
                f.write(f"{gate_name}: {', '.join(gate.fanin)}\n")


#TODO: implement the NLDM parser and related classes and functions
class CellNLDM:
    pass





def build_arg_parser() -> ArgumentParser:
    """Define the args in command line to run this parser.

    Returns:
        ArgumentParser: _description_
    """    
    parser = ArgumentParser(description="Netlist/NLDM parser")
    parser.add_argument("--read_ckt", type=str, help="Path to .bench file")
    parser.add_argument("--read_nldm", type=str, help="Path to .lib file")
    parser.add_argument("--delays", action="store_true", help="Print delay LUTs")
    parser.add_argument("--slews", action="store_true", help="Print slew LUTs")
    return parser



def main(file_name=""):

    parser = build_arg_parser()
    args = parser.parse_args()

    if args.read_ckt:
        netlist = Netlist(args.read_ckt)
        output_file_name = ''.join(("ckt_details_", Path(args.read_ckt).stem, ".txt"))
        netlist.write_ckt_details(output_file_name)
        return

    if args.read_nldm:
        raise NotImplementedError("read_nldm is not implemented yet.")

    parser.error("Provide --read_ckt <benchfile> or --read_nldm <libfile>.")

    netlist = Netlist(file_name)

    pass


if __name__ == "__main__":
    # file_name = "c17.bench"
    main()