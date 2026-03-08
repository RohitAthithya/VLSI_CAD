# main_sta.py
# Phase-2 STA using Netlist + NLDM, modeled after reference.py

from argparse import ArgumentParser
from collections import deque
from pathlib import Path
from typing import Dict, List, Tuple, Optional

from parser import Netlist, NLDM, CellNLDM  # your Phase-1 code
from proj_utils import ENCODING_FORMAT_DEFAULT


# ---------------------------------------------------------------------------
# Global STA constants (match reference)
# ---------------------------------------------------------------------------

PI_ARRIVAL_NS: float = 0.0
PI_SLEW_PS: float = 2.0
PI_SLEW_NS: float = PI_SLEW_PS / 1000.0  # LUT time unit is ns


# ---------------------------------------------------------------------------
# Helper: 2D LUT interpolation (Appendix-3)
# ---------------------------------------------------------------------------

def _find_bounds(vals: List[float], x: float) -> Tuple[int, int]:
    """
    Return (lo, hi) such that vals[lo] <= x < vals[hi].
    Clamp at endpoints (lo==hi) if x outside range.
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


def lut_lookup_2d(
    idx1: List[float],
    idx2: List[float],
    table: List[List[float]],
    tau_ns: float,
    cap_ff: float,
) -> float:
    """
    Bilinear 2D interpolation on NLDM LUT.
    idx1 -> tau (ns), idx2 -> Cload (fF).
    """
    if not idx1 or not idx2 or not table:
        raise ValueError("Empty LUT indices/table")

    i1, i2 = _find_bounds(idx1, tau_ns)
    j1, j2 = _find_bounds(idx2, cap_ff)

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

    num = (
        v11 * (c2 - cap_ff) * (t2 - tau_ns)
        + v12 * (cap_ff - c1) * (t2 - tau_ns)
        + v21 * (c2 - cap_ff) * (tau_ns - t1)
        + v22 * (cap_ff - c1) * (tau_ns - t1)
    )
    den = (c2 - c1) * (t2 - t1)
    return num / den


# ---------------------------------------------------------------------------
# Cell library wrapper around NLDM
# ---------------------------------------------------------------------------

def _cell_signature(cell_name: str) -> Tuple[str, int]:
    """Extract (logic, nin) from liberty cell name, e.g. NAND2_X1 -> (NAND, 2)."""
    base = cell_name.strip()
    us = base.find("_")
    if us != -1:
        base = base[:us]

    # letters + optional digits at end
    import re
    m = re.match(r"^([A-Za-z]+)(\d*)$", base)
    if not m:
        return (cell_name.upper(), 1)

    logic = m.group(1).upper()
    d = m.group(2)
    if d:
        try:
            return (logic, int(d))
        except ValueError:
            return (logic, 1)
    return (logic, 1)


def _normalize_gate_type(gate_type: str) -> str:
    gt = gate_type.upper().strip()
    if gt in {"NOT", "INV", "INVERTER"}:
        return "INV"
    if gt in {"BUFF", "BUF", "BUFFER"}:
        return "BUF"
    return gt


class CellLibrary:
    """Adapts NLDM cells to provide delay/slew/cap in ns and fF."""

    def __init__(self, nldm: NLDM) -> None:
        self.cells_by_name: Dict[str, CellNLDM] = {}
        self.cells_by_sig: Dict[Tuple[str, int], CellNLDM] = {}
        self.cells_by_logic: Dict[str, List[CellNLDM]] = {}

        for name, cell in nldm.cells.items():
            self.cells_by_name[name] = cell
            logic, nin = _cell_signature(name)
            if logic not in self.cells_by_logic:
                self.cells_by_logic[logic] = []
            self.cells_by_logic[logic].append(cell)
            key = (logic, nin)
            if key not in self.cells_by_sig:
                self.cells_by_sig[key] = cell

        self.inv_cell: Optional[CellNLDM] = self._pick_inverter()

    def _pick_inverter(self) -> Optional[CellNLDM]:
        inv_list = self.cells_by_logic.get("INV", [])
        if inv_list:
            return inv_list[0]
        for name, c in self.cells_by_name.items():
            if name.upper().startswith("INV"):
                return c
        return None

    def pick_cell_for_gate(self, gate_type: str, n_inputs: int) -> CellNLDM:
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

    def input_cap_ff_for_gate(self, gate_type: str, n_inputs: int) -> float:
        cell = self.pick_cell_for_gate(gate_type, n_inputs)
        if cell.capacitance is None:
            raise ValueError(f"Cell '{cell.name}' missing capacitance.")
        return float(cell.capacitance)

    def inv_cap_ff(self) -> float:
        if self.inv_cell is None or self.inv_cell.capacitance is None:
            raise ValueError("Inverter capacitance missing; needed for PO load.")
        return float(self.inv_cell.capacitance)

    def delay_ns(self, gate_type: str, n_inputs: int, tau_in_ns: float, cload_ff: float) -> float:
        cell = self.pick_cell_for_gate(gate_type, n_inputs)
        if not cell.tau_in_vals or not cell.c_load_vals or not cell.delay_table:
            raise ValueError(f"Cell '{cell.name}' missing delay LUT data.")
        base = lut_lookup_2d(
            cell.tau_in_vals, cell.c_load_vals, cell.delay_table, tau_in_ns, cload_ff
        )
        if n_inputs > 2:
            base *= (float(n_inputs) / 2.0)
        return base

    def slew_ns(self, gate_type: str, n_inputs: int, tau_in_ns: float, cload_ff: float) -> float:
        cell = self.pick_cell_for_gate(gate_type, n_inputs)
        if not cell.tau_in_vals or not cell.c_load_vals or not cell.slew_table:
            raise ValueError(f"Cell '{cell.name}' missing slew LUT data.")
        base = lut_lookup_2d(
            cell.tau_in_vals, cell.c_load_vals, cell.slew_table, tau_in_ns, cload_ff
        )
        if n_inputs > 2:
            base *= (float(n_inputs) / 2.0)
        return base


# ---------------------------------------------------------------------------
# Gate timing node (similar to GateNode in reference)
# ---------------------------------------------------------------------------

class GateNode:
    """Per-gate STA info, mapped from your Netlist.gates entries."""

    __slots__ = (
        "out_net",
        "gate_type",
        "input_nets",
        "fanin",
        "fanout",
        "cload_ff",
        "arrival_out_ns",
        "tau_out_ns",
        "req_out_ns",
        "slack_ns",
        "path_delays_ns",
        "path_slews_ns",
        "max_input_idx",
    )

    def __init__(self, out_net: str, gate_type: str, input_nets: List[str]) -> None:
        self.out_net = out_net
        self.gate_type = gate_type  # normalized like NAND, NOR, etc.
        self.input_nets = input_nets

        self.fanin: List[str] = []   # printable descriptors (INPUT-x / TYPE-net)
        self.fanout: List[str] = []  # printable descriptors (TYPE-net / OUTPUT-x)

        self.cload_ff: float = 0.0
        self.arrival_out_ns: float = 0.0
        self.tau_out_ns: float = PI_SLEW_NS
        self.req_out_ns: float = float("inf")
        self.slack_ns: float = float("inf")
        self.path_delays_ns: List[float] = []
        self.path_slews_ns: List[float] = []
        self.max_input_idx: int = 0

    @property
    def desc(self) -> str:
        return f"{self.gate_type}-{self.out_net}"


# ---------------------------------------------------------------------------
# Build GateNodes from your Netlist
# ---------------------------------------------------------------------------

def netlist_to_gate_nodes(netlist: Netlist) -> Tuple[List[str], List[str], List[GateNode]]:
    """Convert Netlist into (primary_inputs, primary_outputs, list[GateNode])."""
    primary_inputs = list(netlist.input_pins.keys())   # nets: "1", "2", ...
    primary_outputs = list(netlist.output_pins.keys()) # nets: "22", "23", ...

    gates: List[GateNode] = []
    for gate_name, gate in netlist.gates.items():
        # gate.output_wire is the net name, gate.gate_type logic type, gate.input_wires
        gnode = GateNode(out_net=gate.output_wire, gate_type=gate.gate_type, input_nets=gate.input_wires)
        gates.append(gnode)

    return primary_inputs, primary_outputs, gates


def build_connectivity(
    primary_inputs: List[str],
    primary_outputs: List[str],
    gates: List[GateNode],
) -> None:
    """Fill g.fanin and g.fanout fields (printable descriptors)."""
    pi_set = set(primary_inputs)
    po_set = set(primary_outputs)

    gate_by_net: Dict[str, GateNode] = {g.out_net: g for g in gates}

    # fanin: INPUT-* first, then gate descriptors
    for g in gates:
        inputs_first: List[str] = []
        gates_second: List[str] = []

        for in_net in g.input_nets:
            if in_net in pi_set:
                inputs_first.append(f"INPUT-{in_net}")
            elif in_net in gate_by_net:
                gates_second.append(gate_by_net[in_net].desc)
        g.fanin = inputs_first + gates_second

    # fanout
    for g in gates:
        g.fanout = []

    for sink in gates:
        sink_desc = sink.desc
        for in_net in sink.input_nets:
            driver = gate_by_net.get(in_net)
            if driver is not None:
                driver.fanout.append(sink_desc)

    for g in gates:
        if g.out_net in po_set:
            g.fanout.append(f"OUTPUT-{g.out_net}")


# ---------------------------------------------------------------------------
# Build graph + topo order
# ---------------------------------------------------------------------------

def build_graph(
    primary_inputs: List[str],
    primary_outputs: List[str],
    gates: List[GateNode],
) -> Tuple[Dict[str, GateNode], Dict[str, List[GateNode]], Dict[str, int]]:
    gate_by_net: Dict[str, GateNode] = {g.out_net: g for g in gates}

    adj: Dict[str, List[GateNode]] = {}
    indeg: Dict[str, int] = {g.out_net: 0 for g in gates}

    for sink in gates:
        for in_net in sink.input_nets:
            driver = gate_by_net.get(in_net)
            if driver is None:
                continue
            if driver.out_net not in adj:
                adj[driver.out_net] = []
            adj[driver.out_net].append(sink)
            indeg[sink.out_net] += 1

    for g in gates:
        if g.out_net not in adj:
            adj[g.out_net] = []

    return gate_by_net, adj, indeg


def topological_order(gates: List[GateNode], adj: Dict[str, List[GateNode]], indeg: Dict[str, int]) -> List[GateNode]:
    q = deque()
    for g in gates:
        if indeg.get(g.out_net, 0) == 0:
            q.append(g)

    topo: List[GateNode] = []
    while q:
        cur = q.popleft()
        topo.append(cur)
        for sink in adj.get(cur.out_net, []):
            indeg[sink.out_net] -= 1
            if indeg[sink.out_net] == 0:
                q.append(sink)

    if len(topo) != len(gates):
        raise ValueError("Topo sort failed (cycle or malformed netlist).")
    return topo


# ---------------------------------------------------------------------------
# Load capacitances (exactly as reference)
# ---------------------------------------------------------------------------

def compute_load_caps(
    primary_outputs: List[str],
    gates: List[GateNode],
    gate_by_net: Dict[str, GateNode],
    lib: CellLibrary,
) -> None:
    for g in gates:
        g.cload_ff = 0.0

    has_gate_fanout: Dict[str, bool] = {g.out_net: False for g in gates}

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


# ---------------------------------------------------------------------------
# Forward STA (exact rules from reference)
# ---------------------------------------------------------------------------

def forward_sta(
    primary_inputs: List[str],
    primary_outputs: List[str],
    topo: List[GateNode],
    gate_by_net: Dict[str, GateNode],
    lib: CellLibrary,
) -> Tuple[Dict[str, float], float]:
    pi_set = set(primary_inputs)

    for g in topo:
        n_in = len(g.input_nets)
        g.path_delays_ns = []
        g.path_slews_ns = []

        best_arr = -1.0
        best_idx = 0
        best_tau = PI_SLEW_NS

        for i, in_net in enumerate(g.input_nets):
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

            d_ns = lib.delay_ns(g.gate_type, n_in, tau_in, g.cload_ff)
            s_ns = lib.slew_ns(g.gate_type, n_in, tau_in, g.cload_ff)

            g.path_delays_ns.append(d_ns)
            g.path_slews_ns.append(s_ns)

            cand = a_in + d_ns
            if cand > best_arr:
                best_arr = cand
                best_idx = i
                best_tau = s_ns

        if best_arr < 0.0:
            best_arr = 0.0

        g.arrival_out_ns = best_arr
        g.tau_out_ns = best_tau
        g.max_input_idx = best_idx

    arrival_po_ns: Dict[str, float] = {}
    ckt_delay_ns = 0.0
    for po in primary_outputs:
        drv = gate_by_net.get(po)
        a = drv.arrival_out_ns if drv is not None else 0.0
        arrival_po_ns[po] = a
        if a > ckt_delay_ns:
            ckt_delay_ns = a

    return arrival_po_ns, ckt_delay_ns


# ---------------------------------------------------------------------------
# Backward STA + slacks (exact rules)
# ---------------------------------------------------------------------------

def backward_sta(
    primary_inputs: List[str],
    primary_outputs: List[str],
    topo: List[GateNode],
    gate_by_net: Dict[str, GateNode],
    arrival_po_ns: Dict[str, float],
    circuit_delay_ns: float,
) -> Tuple[Dict[str, float], Dict[str, float], float]:
    import math

    pi_set = set(primary_inputs)
    required_po_ns = 1.1 * circuit_delay_ns

    req_pi_ns: Dict[str, float] = {pi: float("inf") for pi in primary_inputs}

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

    slack_po_ns: Dict[str, float] = {}
    for po in primary_outputs:
        slack_po_ns[po] = required_po_ns - arrival_po_ns.get(po, 0.0)

    for g in topo:
        if math.isinf(g.req_out_ns):
            g.slack_ns = float("inf")
        else:
            g.slack_ns = g.req_out_ns - g.arrival_out_ns

    return req_pi_ns, slack_po_ns, required_po_ns


# ---------------------------------------------------------------------------
# Critical path and output writer
# ---------------------------------------------------------------------------

def _fmt_ps(x_ns: float) -> str:
    import math
    if math.isinf(x_ns):
        return "inf"
    ps = x_ns * 1000.0
    s = f"{ps:.5f}"
    s = s.rstrip("0").rstrip(".")
    if s == "-0":
        s = "0"
    return s


def find_critical_path(
    primary_inputs: List[str],
    primary_outputs: List[str],
    gate_by_net: Dict[str, GateNode],
    req_pi_ns: Dict[str, float],
    slack_po_ns: Dict[str, float],
    seed: int = 0,
) -> List[str]:
    import math, random

    rng = random.Random(seed)
    pi_set = set(primary_inputs)

    # slack lookup
    slack_desc: Dict[str, float] = {}
    for pi in primary_inputs:
        req = req_pi_ns.get(pi, float("inf"))
        slack_desc[f"INPUT-{pi}"] = (req - 0.0) if (not math.isinf(req)) else float("inf")
    for g in gate_by_net.values():
        slack_desc[g.desc] = g.slack_ns

    # choose PO with minimum slack
    best_slack = float("inf")
    ties: List[str] = []
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
    path_back: List[str] = [f"OUTPUT-{start_po}"]

    cur = gate_by_net.get(start_po)
    if cur is None:
        if start_po in pi_set:
            path_back.append(f"INPUT-{start_po}")
        return list(reversed(path_back))

    path_back.append(cur.desc)

    while True:
        best_pred_desc: Optional[str] = None
        best_pred_gate: Optional[GateNode] = None
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


def write_ckt_traversal(
    out_path: Path,
    primary_inputs: List[str],
    primary_outputs: List[str],
    gate_print_order: List[GateNode],
    req_pi_ns: Dict[str, float],
    slack_po_ns: Dict[str, float],
    circuit_delay_ns: float,
    critical_path: List[str],
) -> None:
    import math

    with out_path.open("w", encoding=ENCODING_FORMAT_DEFAULT) as w:
        w.write(f"Circuit delay: {_fmt_ps(circuit_delay_ns)} ps\n\n")
        w.write("Gate slacks:\n")

        for pi in primary_inputs:
            req = req_pi_ns.get(pi, float("inf"))
            slack_ns = (req - 0.0) if (not math.isinf(req)) else float("inf")
            w.write(f"INPUT-{pi}: {_fmt_ps(slack_ns)} ps\n")

        for po in primary_outputs:
            w.write(f"OUTPUT-{po}: {_fmt_ps(slack_po_ns.get(po, float('inf')))} ps\n")

        for g in gate_print_order:
            w.write(f"{g.desc}: {_fmt_ps(g.slack_ns)} ps\n")

        w.write("\nCritical path:\n")
        if critical_path:
            w.write(",".join(critical_path) + "\n")
        else:
            w.write("None\n")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_arg_parser() -> ArgumentParser:
    p = ArgumentParser(description="Phase-2 STA using Netlist + NLDM")
    p.add_argument("--read_ckt", type=str, required=True, help="Path to .bench file")
    p.add_argument("--read_nldm", type=str, required=True, help="Path to .lib file")
    p.add_argument("--seed", type=int, default=0, help="Seed for critical path PO tie-break")
    return p


def main():
    """ Main business logic - organises the high level execution of the code

    Returns:
        _type_: _description_
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

    out_path = Path("ckt_traversal.txt")
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
    return 0


if __name__ == "__main__":
    main()
