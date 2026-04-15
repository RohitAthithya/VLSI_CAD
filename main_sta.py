# imports
from argparse import ArgumentParser
from collections import deque
from pathlib import Path

import math, random

# custom imports
from parser import Netlist, NLDM, CellNLDM
from proj_utils import ENCODING_FORMAT_DEFAULT, lut_lookup_2d, fmt_ps


#CONSTANTS
PI_ARRIVAL_NS = 0.0
PI_SLEW_PS = 2.0
PI_SLEW_NS = PI_SLEW_PS / 1000.0  # LUT time unit is ns


def _normalize_gate_type(gate_type):
    """Normalize gate type strings to canonical forms (e.g., INV, BUF).

    Args:
        gate_type: original gate type string from the netlist (e.g., "NOT", "INV").

    Returns:
        The normalized gate type string (e.g., "INV" or "BUF").
    """
    gt = gate_type.upper().strip()
    if gt in {"NOT", "INV", "INVERTER"}:
        return "INV"
    if gt in {"BUFF", "BUF", "BUFFER"}:
        return "BUF"
    return gt


class CellLibrary:
    """
        Cell library abstraction for STA, built from NLDM data. 
        Provides methods to pick cells and query delay/slew.
    """

    def __init__(self, nldm):
        self.cells_by_name = {}
        self.cells_by_sig = {}
        self.cells_by_logic = {}

        for name, cell in nldm.cells.items():
            self.cells_by_name[name] = cell
            logic = cell.logic_type  
            nin = len(cell.tau_in_vals) 

            if logic not in self.cells_by_logic:
                self.cells_by_logic[logic] = []
            self.cells_by_logic[logic].append(cell)
            key = (logic, nin)
            if key not in self.cells_by_sig:
                self.cells_by_sig[key] = cell

        self.inv_cell = self._pick_inverter()

    def _pick_inverter(self):
        inv_list = self.cells_by_logic.get("INV", [])
        if inv_list:
            return inv_list[0]
        for name, c in self.cells_by_name.items():
            if name.upper().startswith("INV"):
                return c
        return None

    def pick_cell_for_gate(self, gate_type, n_inputs):
        logic = _normalize_gate_type(gate_type)

        if logic == "INV":
            if self.inv_cell is None:
                raise KeyError("No inverter cell found in NLDM (needed for loads).")
            return self.inv_cell

        # Prefer 2-input version
        if (logic, 2) in self.cells_by_sig:
            return self.cells_by_sig[(logic, 2)]
        if (logic, 1) in self.cells_by_sig:
            return self.cells_by_sig[(logic, 1)]

        lst = self.cells_by_logic.get(logic, [])
        if lst:
            return lst[0]

        raise KeyError(f"No NLDM cell found for gate type '{gate_type}' (normalized '{logic}').")

    def input_cap_ff_for_gate(self, gate_type, n_inputs):
        cell = self.pick_cell_for_gate(gate_type, n_inputs)
        if cell.capacitance is None:
            raise ValueError(f"Cell '{cell.name}' missing capacitance.")
        return float(cell.capacitance)

    def inv_cap_ff(self):
        if self.inv_cell is None or self.inv_cell.capacitance is None:
            raise ValueError("Inverter capacitance missing; needed for PO load.")
        return float(self.inv_cell.capacitance)

    def delay_ns(self, gate_type, n_inputs, tau_in_ns, cload_ff):
        cell = self.pick_cell_for_gate(gate_type, n_inputs)
        if not cell.tau_in_vals or not cell.c_load_vals or not cell.delay_table:
            raise ValueError(f"Cell '{cell.name}' missing delay LUT data.")
        base = lut_lookup_2d(
            cell.tau_in_vals, cell.c_load_vals, cell.delay_table, tau_in_ns, cload_ff
        )
        if n_inputs > 2:
            base *= (float(n_inputs) / 2.0)
        return base

    def slew_ns(self, gate_type, n_inputs, tau_in_ns, cload_ff):
        cell = self.pick_cell_for_gate(gate_type, n_inputs)
        if not cell.tau_in_vals or not cell.c_load_vals or not cell.slew_table:
            raise ValueError(f"Cell '{cell.name}' missing slew LUT data.")
        base = lut_lookup_2d(
            cell.tau_in_vals, cell.c_load_vals, cell.slew_table, tau_in_ns, cload_ff
        )
        if n_inputs > 2:
            base *= (float(n_inputs) / 2.0)
        return base

class GateNode:
    """
    Represents a gate in the circuit for STA purposes, with connectivity and timing info.
        - out_net: the net driven by this gate (also its unique identifier)
        - gate_type: logic type (e.g., NAND, NOR, INV)
        - input_nets: list of nets driving this gate
        - fanin: list of printable descriptors for fanin (e.g., "INPUT-1", "NAND-5")
        - fanout: list of printable descriptors for fanout (e.g., "NOR-3", "OUTPUT-22")
        - cload_ff: load capacitance in fF
        - arrival_out_ns: arrival time at output in ns
        - tau_out_ns: output slew in ns
        - req_out_ns: required time at output in ns
        - slack_ns: slack at output in ns

    """

    def __init__(self, out_net, gate_type, input_nets):
        """Initialize a GateNode with its output net, gate type, and input nets.

        Args:
            out_net: net driven by this gate (unique identifier).
            gate_type: logic type of the gate (e.g., NAND, NOR, INV).
            input_nets: list of nets that drive this gate.
        """
        self.out_net = out_net
        self.gate_type = gate_type
        self.input_nets = input_nets

        self.fanin = []
        self.fanout = []

        self.cload_ff = 0.0
        self.arrival_out_ns = 0.0
        self.tau_out_ns = PI_SLEW_NS
        self.req_out_ns = float("inf")
        self.slack_ns = float("inf")
        self.path_delays_ns = []
        self.path_slews_ns = []
        self.max_input_idx = 0

    @property
    def desc(self):
        return f"{self.gate_type}-{self.out_net}"


def netlist_to_gate_nodes(netlist):
    """Convert the parsed netlist into GateNode objects plus primary input/output lists.

    Args:
        netlist: parsed Netlist object containing gates, inputs, and outputs.

    Returns:
        A tuple (primary_inputs, primary_outputs, gates).
    """
    primary_inputs = list(netlist.input_pins.keys())
    primary_outputs = list(netlist.output_pins.keys())

    gates = []
    for gate_name, gate in netlist.gates.items():
        gnode = GateNode(out_net=gate.output_wire, gate_type=gate.gate_type, input_nets=gate.input_wires)
        gates.append(gnode)

    return primary_inputs, primary_outputs, gates


def build_connectivity(primary_inputs, primary_outputs, gates):
    """ 
        Build the fanin and fanout lists for each gate, as well as the primary input and output connections.
        This function populates the 'fanin' and 'fanout' attributes of each GateNode based on the input and output nets,
        as well as the primary inputs and outputs. The fanin list for a gate will have entries like "INPUT-1" for primary inputs and "NAND-5" for gates, while the fanout list will have entries like "NOR-3" for gates and "OUTPUT-22" for primary outputs.

    Args:        
        primary_inputs (list[str]): 
            - A list of primary input net names.
        primary_outputs (list[str]): 
            - A list of primary output net names.
        gates (list[GateNode]): 
            - A list of GateNode objects representing the gates in the circuit, with their output nets, gate types, and input nets populated. The 'fanin' and 'fanout' attributes of these GateNode objects will be populated by this function based on the connectivity of the circuit.

    """
    pi_set = set(primary_inputs)
    po_set = set(primary_outputs)

    gate_by_net = {g.out_net: g for g in gates}


    for gate in gates:
        inputs_first = []
        gates_second = []

        for in_net in gate.input_nets:
            if in_net in pi_set:
                inputs_first.append(f"INPUT-{in_net}")
            elif in_net in gate_by_net:
                gates_second.append(gate_by_net[in_net].desc)
        gate.fanin = inputs_first + gates_second

    # fanout
    for gate in gates:
        gate.fanout = []

    for sink in gates:
        sink_desc = sink.desc
        for in_net in sink.input_nets:
            driver = gate_by_net.get(in_net)
            if driver is not None:
                driver.fanout.append(sink_desc)

    for gate in gates:
        if gate.out_net in po_set:
            gate.fanout.append(f"OUTPUT-{gate.out_net}")


def build_graph(primary_inputs, primary_outputs, gates):
    gate_by_net = {g.out_net: g for g in gates}

    adj = {}
    indeg = {g.out_net: 0 for g in gates}

    for sink in gates:
        for in_net in sink.input_nets:
            driver = gate_by_net.get(in_net)
            if driver is None:
                continue
            if driver.out_net not in adj:
                adj[driver.out_net] = []
            adj[driver.out_net].append(sink)
            indeg[sink.out_net] += 1

    for gate in gates:
        if gate.out_net not in adj:
            adj[gate.out_net] = []

    return gate_by_net, adj, indeg


def topological_order(gates, adj, indeg):
    queue = deque()
    for gate in gates:
        if indeg.get(gate.out_net, 0) == 0:
            queue.append(gate)

    topo = []
    while queue:
        cur = queue.popleft()
        topo.append(cur)
        for sink in adj.get(cur.out_net, []):
            indeg[sink.out_net] -= 1
            if indeg[sink.out_net] == 0:
                queue.append(sink)

    if len(topo) != len(gates):
        raise ValueError("Topo sort failed (cycle or malformed netlist).")
    return topo


def compute_load_caps(primary_outputs, gates, gate_by_net, lib):
    for g in gates:
        g.cload_ff = 0.0

    has_gate_fanout = {g.out_net: False for g in gates}

    # Sum gate input caps
    for sink in gates:
        cap_in_ff = lib.input_cap_ff_for_gate(sink.gate_type, len(sink.input_nets))
        for in_net in sink.input_nets:
            driver = gate_by_net.get(in_net)
            if driver is not None:
                driver.cload_ff += cap_in_ff
                has_gate_fanout[driver.out_net] = True

    # Add PO load only to final-stage gates (no other gate fanout)
    po_set = set(primary_outputs)
    extra = 4.0 * lib.inv_cap_ff()
    for g in gates:
        if g.out_net in po_set and not has_gate_fanout.get(g.out_net, False):
            g.cload_ff += extra


def forward_sta(primary_inputs, primary_outputs, topo, gate_by_net, lib):
    pi_set = set(primary_inputs)

    for gate in topo:
        n_in = len(gate.input_nets)
        gate.path_delays_ns = []
        gate.path_slews_ns = []

        best_arr = -1.0
        best_idx = 0
        best_tau = PI_SLEW_NS

        for i, in_net in enumerate(gate.input_nets):
            if in_net in pi_set:
                a_in = PI_ARRIVAL_NS
                tau_in = PI_SLEW_NS
            else:
                drv = gate_by_net.get(in_net)
                if drv is None:
                    a_in = PI_ARRIVAL_NS
                    tau_in = PI_SLEW_NS
                else:
                    a_in = drv.arrival_out_ns
                    tau_in = drv.tau_out_ns

            d_ns = lib.delay_ns(gate.gate_type, n_in, tau_in, gate.cload_ff)
            s_ns = lib.slew_ns(gate.gate_type, n_in, tau_in, gate.cload_ff)

            gate.path_delays_ns.append(d_ns)
            gate.path_slews_ns.append(s_ns)

            cand = a_in + d_ns
            if cand > best_arr:
                best_arr = cand
                best_idx = i
                best_tau = s_ns

        if best_arr < 0.0:
            best_arr = 0.0

        gate.arrival_out_ns = best_arr
        gate.tau_out_ns = best_tau
        gate.max_input_idx = best_idx

    arrival_po_ns = {}
    ckt_delay_ns = 0.0
    for primary_output in primary_outputs:
        drv = gate_by_net.get(primary_output)
        a = drv.arrival_out_ns if drv is not None else 0.0
        arrival_po_ns[primary_output] = a
        if a > ckt_delay_ns:
            ckt_delay_ns = a

    return arrival_po_ns, ckt_delay_ns


def backward_sta(primary_inputs, primary_outputs, topo, gate_by_net, arrival_po_ns, circuit_delay_ns):
    import math

    pi_set = set(primary_inputs)
    required_po_ns = 1.1 * circuit_delay_ns

    req_pi_ns = {pi: float("inf") for pi in primary_inputs}

    for g in topo:
        g.req_out_ns = float("inf")

    po_set = set(primary_outputs)
    for po in primary_outputs:
        if po in pi_set:
            req_pi_ns[po] = min(req_pi_ns[po], required_po_ns)

    for g in topo:
        if g.out_net in po_set:
            g.req_out_ns = min(g.req_out_ns, required_po_ns)

    for g in reversed(topo):
        if math.isinf(g.req_out_ns):
            continue
        for i, in_net in enumerate(g.input_nets):
            d_ns = g.path_delays_ns[i] if i < len(g.path_delays_ns) else 0.0
            req_at_driver = g.req_out_ns - d_ns
            if in_net in pi_set:
                req_pi_ns[in_net] = min(req_pi_ns[in_net], req_at_driver)
            else:
                drv = gate_by_net.get(in_net)
                if drv is not None:
                    drv.req_out_ns = min(drv.req_out_ns, req_at_driver)

    slack_po_ns = {}
    for po in primary_outputs:
        slack_po_ns[po] = required_po_ns - arrival_po_ns.get(po, 0.0)

    for g in topo:
        if math.isinf(g.req_out_ns):
            g.slack_ns = float("inf")
        else:
            g.slack_ns = g.req_out_ns - g.arrival_out_ns

    return req_pi_ns, slack_po_ns, required_po_ns





def find_critical_path(primary_inputs, primary_outputs, gate_by_net, req_pi_ns, slack_po_ns, seed=0):
    

    rng = random.Random(seed)
    pi_set = set(primary_inputs)

    # slack lookup
    slack_desc = {}
    for pi in primary_inputs:
        req = req_pi_ns.get(pi, float("inf"))
        slack_desc[f"INPUT-{pi}"] = (req - 0.0) if (not math.isinf(req)) else float("inf")
    for g in gate_by_net.values():
        slack_desc[g.desc] = g.slack_ns

    # choose PO with minimum slack
    best_slack = float("inf")
    ties = []
    for po in primary_outputs:
        s = slack_po_ns.get(po, float("inf"))
        if s < best_slack:
            best_slack = s
            ties = [po]
        elif s == best_slack:
            ties.append(po)

    if not ties:
        return []

    start_po = rng.choice(ties)
    path_back = [f"OUTPUT-{start_po}"]

    cur = gate_by_net.get(start_po)
    if cur is None:
        if start_po in pi_set:
            path_back.append(f"INPUT-{start_po}")
        return list(reversed(path_back))

    path_back.append(cur.desc)

    while True:
        best_pred_desc = None
        best_pred_gate = None
        best_pred_slack = float("inf")

        for in_net in cur.input_nets:
            if in_net in pi_set:
                d = f"INPUT-{in_net}"
                s = slack_desc.get(d, float("inf"))
                if s < best_pred_slack:
                    best_pred_slack = s
                    best_pred_desc = d
                    best_pred_gate = None
            else:
                pred = gate_by_net.get(in_net)
                if pred is not None:
                    d = pred.desc
                    s = slack_desc.get(d, float("inf"))
                    if s < best_pred_slack:
                        best_pred_slack = s
                        best_pred_desc = d
                        best_pred_gate = pred

        if best_pred_desc is None:
            break

        path_back.append(best_pred_desc)

        if best_pred_gate is None:
            break

        cur = best_pred_gate

    return list(reversed(path_back))


def write_ckt_traversal(out_path, primary_inputs, primary_outputs, gate_print_order, req_pi_ns, slack_po_ns, circuit_delay_ns, critical_path):
    import math

    with out_path.open("w", encoding=ENCODING_FORMAT_DEFAULT) as w:
        w.write(f"Circuit delay: {fmt_ps(circuit_delay_ns)} ps\n\n")
        w.write("Gate slacks:\n")

        for pi in primary_inputs:
            req = req_pi_ns.get(pi, float("inf"))
            slack_ns = (req - 0.0) if (not math.isinf(req)) else float("inf")
            w.write(f"INPUT-{pi}: {fmt_ps(slack_ns)} ps\n")

        for po in primary_outputs:
            w.write(f"OUTPUT-{po}: {fmt_ps(slack_po_ns.get(po, float('inf')))} ps\n")

        for g in gate_print_order:
            w.write(f"{g.desc}: {fmt_ps(g.slack_ns)} ps\n")

        w.write("\nCritical path:\n")
        if critical_path:
            w.write(",".join(critical_path) + "\n")
        else:
            w.write("None\n")


def build_arg_parser():
    p = ArgumentParser(description="Phase-2 STA using Netlist + NLDM")
    p.add_argument("--read_ckt", type=str, required=True, help="Path to .bench file")
    p.add_argument("--read_nldm", type=str, required=True, help="Path to .lib file")
    p.add_argument("--seed", type=int, default=0, help="Seed for critical path PO tie-break")
    return p


def main():
    """ Main business logic - organises the high level execution of the code

    """    
    
    args = build_arg_parser().parse_args()

    bench_path = Path(args.read_ckt)
    lib_path = Path(args.read_nldm)

    netlist = Netlist(bench_path)
    nldm = NLDM()
    nldm.parse_file(lib_path)

    # convert to GateNode world
    pis, pos, gates = netlist_to_gate_nodes(netlist)
    build_connectivity(pis, pos, gates)

    lib = CellLibrary(nldm)

    gate_by_net, adj, indeg = build_graph(pis, pos, gates)
    topo = topological_order(gates, adj, indeg)

    compute_load_caps(pos, gates, gate_by_net, lib)
    arrival_po_ns, ckt_delay_ns = forward_sta(pis, pos, topo, gate_by_net, lib)
    req_pi_ns, slack_po_ns, _ = backward_sta(pis, pos, topo, gate_by_net, arrival_po_ns, ckt_delay_ns)

    crit_path = find_critical_path(
        primary_inputs=pis,
        primary_outputs=pos,
        gate_by_net=gate_by_net,
        req_pi_ns=req_pi_ns,
        slack_po_ns=slack_po_ns,
        seed=args.seed,
    )
    stem = bench_path.stem
    out_path = Path(f"ckt_traversal_{stem}.txt")
    write_ckt_traversal(
        out_path=out_path,
        primary_inputs=pis,
        primary_outputs=pos,
        gate_print_order=topo,
        req_pi_ns=req_pi_ns,
        slack_po_ns=slack_po_ns,
        circuit_delay_ns=ckt_delay_ns,
        critical_path=crit_path,
    )


if __name__ == "__main__":
    main()
