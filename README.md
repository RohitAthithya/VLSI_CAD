# VLSI_CAD
Code base for the VLSI Design Automation mini-projects (parsing .bench/netlist and NLDM-based STA).

## Prerequisites
- Python 3.6+ 
- Create and activate a virtual environment (recommended)

Windows (PowerShell):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Unix / macOS:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Usage

Parser (netlist / NLDM utilities)

- Parse a `.bench` netlist and write circuit details:

```bash
python parser.py --read_ckt c17.bench
# generates: ckt_details_c17.txt
```

- Parse a `.lib` NLDM file and write delay/slew LUTs:

```bash
python parser.py --read_nldm sample_NLDM.lib --delays --slews
# generates: delay_LUT_sample_NLDM.txt and slew_LUT_sample_NLDM.txt
```

Static Timing Analysis (Phase-2) runner

- Run STA using a `.bench` netlist and `.lib` NLDM file:

```bash
python main_sta.py --read_ckt c17.bench --read_nldm sample_NLDM.lib
# generates: ckt_traversal_c17.txt (timing report and critical path)
```

Options:
- `--seed <int>` : optional seed used for deterministic tie-breaking when selecting critical paths.

## Tests

- Run the test suite (pytest):

```bash
python -m pytest -q
```

- You can also run the file-level runner added to `test_proj_utils.py`:

```bash
python test_proj_utils.py
```

## Outputs
- `ckt_details_*.txt`: circuit connectivity and counts produced by the parser
- `delay_LUT_*.txt`, `slew_LUT_*.txt`: LUT exports produced from NLDM
- `ckt_traversal_*.txt`: STA traversal, per-node timing, and critical path from `main_sta.py`

