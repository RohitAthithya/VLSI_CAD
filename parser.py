#generic imports
from argparse import ArgumentParser
from collections import defaultdict, OrderedDict
from pathlib import Path

#custom imports
from proj_utils import *

BENCHFILE_LINE_COMMENT = "#"
BENCHFILE_LINE_INPUT = "INPUT"
BENCHFILE_LINE_OUTPUT = "OUTPUT"
NLDM_LINE_CELL = "cell "
NLDM_LINE_CELL_DELAY = "cell_delay("
NLDM_LINE_OUTPUT_SLEW = "output_slew("
NLDM_LINE_CAPACITANCE = "capacitance"
NLDM_LINE_INDEX_1 = "index_1"
NLDM_LINE_INDEX_2 = "index_2"
NLDM_LINE_VALUES = "values"
NLDM_LINE_VALUES_BLOCK_START = "("
NLDM_LINE_VALUES_BLOCK_END = ");"
NLDM_LINE_START_BLOCK = "{"
NLDM_LINE_END_BLOCK = "}"


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



class CellNLDM:
    """
        Class to hold the NLDM data for a single cell.

        Attributes:
            - name (str): The name of the cell (e.g., "NAND2_X1").
            - logic_type (str): The logic type of the cell (e.g., "NAND").
            - capacitance (float | None): The input capacitance of the cell, if specified.
            - tau_in_vals (list[float]): The list of input slew values (index_1).
            - c_load_vals (list[float]): The list of load capacitance values (index_2).
            - delay_table (list[list[float]]): The 2D list of delay values
                corresponding to the input slew and load capacitance indices.
            - slew_table (list[list[float]]): The 2D list of output slew values
                corresponding to the input slew and load capacitance indices.       
            - delay_unit (str): The unit of the delay values (e.g., "ns").
            - slew_unit (str): The unit of the slew values (e.g., "ns").
            - cap_unit (str): The unit of the capacitance values (e.g., "ff").
        
        Methods:
            __init__(self, name: str, logic_type: str): Initializes the CellNLDM object with its name and logic type.
            (Phase-2) find_interpolated_value(...): Method to find interpolated delay/slew values for given input slew and load cap.
            (Phase-2) delay(...): Method to get delay for specific input slew and load cap, using interpolation if necessary.
            (Phase-2) slew(...): Method to get output slew for specific input slew and load cap, using interpolation if necessary.

    """
    def __init__(self, name: str, logic_type: str):
        self.name: str = name              # e.g. NAND2_X1
        self.logic_type: str = logic_type  # e.g. NAND

        self.capacitance: float | None = None  # input capacitance

        self.tau_in_vals: list[float] = []     # index_1 (input slew)
        self.c_load_vals: list[float] = []     # index_2 (load cap)

        self.delay_table: list[list[float]] = []  # delays[i][j]
        self.slew_table: list[list[float]] = []   # slews[i][j]

        self.delay_unit: str = "ns"
        self.slew_unit: str = "ns"
        self.cap_unit: str = "ff"

    # Phase-2 methods will be added later:
    # def find_interpolated_value(...), delay(...), slew(...)


class NLDM:
    """
        Class to hold the entire NLDM library, with methods to parse from a liberty file and write out LUTs.

        Attributes:
            cells (dict[str, CellNLDM]): Mapping from cell names to their NLDM data.
            logic_to_cell_name (dict[str, str]): Mapping
                from logic types (e.g., "NAND") to a preferred cell name (e.g., "NAND2_X1") for that logic type.
        
        Methods:
            __init__(): Initializes the NLDM object with empty cell data.
            parse_file(lib_path): Parses a liberty NLDM file and populates the cells dictionary.
            write_delay_LUT(output_path): Writes delay LUTs to a specified output file.
            write_slew_LUT(output_path): Writes slew LUTs to a specified output file.

        

    """    
    def __init__(self):
        """
            Initialize the NLDM object with empty cell data.

        """        
        self.cells: dict[str, CellNLDM] = OrderedDict()
        self.logic_to_cell_name: dict[str, str] = {}


    def parse_file(self, lib_path: str | FilePath) -> None:
        """Parse a liberty NLDM file and populate the cells dictionary.

        Assumes the liberty file is well-formed.
        """
        lib_path = Path(lib_path)

        current_cell: CellNLDM | None = None
        in_cell_delay = False
        in_output_slew = False
        collecting_values = False
        value_lines: list[str] = []

        for raw_line in chunked_line_reader(lib_path):
            line = raw_line.strip()
            if not line:
                continue

            low = line.lower()

            # Start of a new cell
            if low.startswith(NLDM_LINE_CELL) and (NLDM_LINE_CELL_DELAY not in low):
                name, logic_type = ret_name_and_logic_type(line)
                current_cell = CellNLDM(name=name, logic_type=logic_type)
                self.cells[name] = current_cell
                if logic_type not in self.logic_to_cell_name:
                    self.logic_to_cell_name[logic_type] = name
                in_cell_delay = False
                in_output_slew = False
                collecting_values = False
                value_lines = []
                continue

            # If we are not inside any cell, skip
            if current_cell is None:
                continue

            # Capacitance line (outside timing blocks)
            if (NLDM_LINE_CAPACITANCE in low) and not in_cell_delay and not in_output_slew:
                current_cell.capacitance = ret_value_for_label(line)
                continue

            # Enter cell_delay block
            if low.startswith(NLDM_LINE_CELL_DELAY):
                in_cell_delay = True
                in_output_slew = False
                collecting_values = False
                value_lines = []
                continue

            # Enter output_slew block
            if low.startswith(NLDM_LINE_OUTPUT_SLEW):
                in_output_slew = True
                in_cell_delay = False
                collecting_values = False
                value_lines = []
                continue

            # Inside delay or slew block
            if in_cell_delay or in_output_slew:
                # index_1
                if low.startswith(NLDM_LINE_INDEX_1):
                    vals = ret_nums_in_str(line)
                    if not current_cell.tau_in_vals:
                        current_cell.tau_in_vals = vals
                    continue

                # index_2
                if low.startswith(NLDM_LINE_INDEX_2):
                    vals = ret_nums_in_str(line)
                    if not current_cell.c_load_vals:
                        current_cell.c_load_vals = vals
                    continue

                # values(...) start
                if NLDM_LINE_VALUES in low and NLDM_LINE_VALUES_BLOCK_START in line:
                    collecting_values = True
                    value_lines = [line]
                    if NLDM_LINE_VALUES_BLOCK_END in line:
                        table = ret_2d_list_from_str(value_lines)
                        if in_cell_delay:
                            current_cell.delay_table = table
                        elif in_output_slew:
                            current_cell.slew_table = table
                        collecting_values = False
                        value_lines = []
                    continue

                # values(...) continuation
                if collecting_values:
                    value_lines.append(line)
                    if NLDM_LINE_VALUES_BLOCK_END in line:
                        table = ret_2d_list_from_str(value_lines)
                        if in_cell_delay:
                            current_cell.delay_table = table
                        elif in_output_slew:
                            current_cell.slew_table = table
                        collecting_values = False
                        value_lines = []
                    continue

                # End of timing block
                if line == NLDM_LINE_END_BLOCK:
                    in_cell_delay = False
                    in_output_slew = False
                    collecting_values = False
                    value_lines = []
                    continue

            # End of cell block (a lone '}' when not inside delay/slew)
            if line == NLDM_LINE_END_BLOCK and not in_cell_delay and not in_output_slew:
                self._validate_cell(current_cell)
                current_cell = None
                in_cell_delay = False
                in_output_slew = False
                collecting_values = False
                value_lines = []
                continue

    def _validate_cell(self, cell: CellNLDM) -> None:
        """Sanity-check sizes of indices and tables for a single cell."""
        if cell is None:
            return
        # Only validate if both indices and tables are present
        if cell.tau_in_vals and cell.c_load_vals and cell.delay_table:
            n_rows = len(cell.delay_table)
            n_cols = len(cell.delay_table[0])
            if n_rows != len(cell.tau_in_vals) or n_cols != len(cell.c_load_vals):
                raise UnexpectedInputStringFormat(
                    f"Delay table shape mismatch for cell {cell.name}"
                )
        if cell.tau_in_vals and cell.c_load_vals and cell.slew_table:
            n_rows = len(cell.slew_table)
            n_cols = len(cell.slew_table[0])
            if n_rows != len(cell.tau_in_vals) or n_cols != len(cell.c_load_vals):
                raise UnexpectedInputStringFormat(
                    f"Slew table shape mismatch for cell {cell.name}"
                )
                

    def write_delay_LUT(self, output_path: str | Path) -> None:
        """Write delay LUTs to delay_LUT.txt-style file."""
        output_path = Path(output_path)
        with open(output_path, "w", encoding="utf-8") as f:
            first = True
            for cell in self.cells.values():
                if not first:
                    f.write("\n")
                first = False

                f.write(f"cell: {cell.name}\n")
                f.write(
                    "input  slews:  "
                    + ",".join(str(v) for v in cell.tau_in_vals)
                    + "\n"
                )
                f.write(
                    "load cap: "
                    + ",".join(str(v) for v in cell.c_load_vals)
                    + "\n\n"
                )
                f.write("delays:\n")
                for row in cell.delay_table:
                    f.write(",".join(str(v) for v in row) + ";\n")

    def write_slew_LUT(self, output_path: str | Path) -> None:
        """Write slew LUTs to slew_LUT.txt-style file."""
        output_path = Path(output_path)
        with open(output_path, "w", encoding="utf-8") as f:
            first = True
            for cell in self.cells.values():
                if not first:
                    f.write("\n")
                first = False

                f.write(f"cell: {cell.name}\n")
                f.write(
                    "input  slews:  "
                    + ",".join(f"{v}" for v in cell.tau_in_vals)
                    + "\n"
                )
                f.write(
                    "load cap: "
                    + ",".join(f"{v:.6f}" for v in cell.c_load_vals)
                    + "\n\n"
                )
                f.write("slews:\n")
                for row in cell.slew_table:
                    f.write(",".join(f"{v:.6f}" for v in row) + ";\n")

    def __str__(self) -> str:
        """
            Return a human-readable summary of the NLDM library.
        """
        lines: list[str] = []
        lines.append(f"NLDM library with {len(self.cells)} cells.\n")

        for cell in self.cells.values():
            lines.append(f"Cell: {cell.name} (logic_type={cell.logic_type})")
            cap_str = (
                f"{cell.capacitance} {cell.cap_unit}"
                if cell.capacitance is not None
                else "N/A"
            )
            lines.append(f"  Input capacitance: {cap_str}")

            # Indices info
            lines.append(
                f"  Tau_in points: {len(cell.tau_in_vals)} "
                f"({cell.delay_unit if cell.tau_in_vals else 'n/a'})"
            )
            lines.append(
                f"  C_load points: {len(cell.c_load_vals)} "
                f"({cell.cap_unit if cell.c_load_vals else 'n/a'})"
            )

            # Table shapes
            if cell.delay_table:
                lines.append(
                    f"  Delay table shape: "
                    f"{len(cell.delay_table)} x {len(cell.delay_table[0])} "
                    f"({cell.delay_unit})"
                )
            else:
                lines.append("  Delay table: not parsed")

            if cell.slew_table:
                lines.append(
                    f"  Slew table shape: "
                    f"{len(cell.slew_table)} x {len(cell.slew_table[0])} "
                    f"({cell.slew_unit})"
                )
            else:
                lines.append("  Slew table: not parsed")

            # Optionally print first/last index values as a quick sanity check
            if cell.tau_in_vals:
                lines.append(
                    f"  Tau_in range: {cell.tau_in_vals[0]} .. {cell.tau_in_vals[-1]}"
                )
            if cell.c_load_vals:
                lines.append(
                    f"  C_load range: {cell.c_load_vals[0]} .. {cell.c_load_vals[-1]}"
                )

            lines.append("")  # blank line between cells

        return "\n".join(lines)
        
        



def build_arg_parser() -> ArgumentParser:
    """ Define the args in command line to run this parser.

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
    if file_name=="":
        parser = build_arg_parser()
        args = parser.parse_args()

        if args.read_ckt:
            netlist = Netlist(args.read_ckt)
            output_file_name = ''.join(("ckt_details_", Path(args.read_ckt).stem, ".txt"))
            netlist.write_ckt_details(output_file_name)
            return

        if args.read_nldm:
            nldm = NLDM()
            nldm.parse_file(args.read_nldm)
            stem = Path(args.read_nldm).stem
            if args.delays:
                nldm.write_delay_LUT(f"delay_LUT_{stem}.txt")
            if args.slews:
                nldm.write_slew_LUT(f"slew_LUT_{stem}.txt")
            if not (args.delays or args.slews):
                parser.error("Use --delays and/or --slews with --read_nldm.")
            return

        parser.error("Provide --read_ckt <benchfile> or --read_nldm <libfile>.")
    else:
        nldm = NLDM()
        nldm.parse_file(file_name)
        stem = Path(file_name).stem
        nldm.write_delay_LUT(f"delay_LUT.txt")
        nldm.write_slew_LUT(f"slew_LUT.txt")
        print(nldm)

    pass


if __name__ == "__main__":
    file_name = "sample_NLDM.lib"
    main(file_name)
    # main()