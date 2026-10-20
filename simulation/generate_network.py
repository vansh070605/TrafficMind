"""Network generation utility for Traffic Chaos Simulator.

Builds a 4-way signalized intersection with configurable approaches,
lanes, connections, and traffic light phases using SUMO's netconvert.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Optional

from simulation.sumo_utils import get_netconvert_binary


def create_network_xml_files(output_dir: Path, arm_length: float = 250.0, num_lanes: int = 2) -> dict[str, Path]:
    """Generate node, edge, connection, and traffic light XML definition files."""
    output_dir.mkdir(parents=True, exist_ok=True)

    nod_file = output_dir / "intersection.nod.xml"
    edg_file = output_dir / "intersection.edg.xml"
    con_file = output_dir / "intersection.con.xml"
    tll_file = output_dir / "intersection.tll.xml"

    # 1. Nodes (Center junction J0 + 4 arms)
    nod_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<nodes xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://sumo.dlr.de/xsd/nodes_file.xsd">
    <node id="J0" x="0.0" y="0.0" type="traffic_light"/>
    <node id="N" x="0.0" y="{arm_length}" type="priority"/>
    <node id="S" x="0.0" y="{-arm_length}" type="priority"/>
    <node id="E" x="{arm_length}" y="0.0" type="priority"/>
    <node id="W" x="{-arm_length}" y="0.0" type="priority"/>
</nodes>
"""
    nod_file.write_text(nod_content, encoding="utf-8")

    # 2. Edges (Incoming and outgoing for each direction)
    speed = "13.89"  # 50 km/h in m/s
    edg_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<edges xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://sumo.dlr.de/xsd/edges_file.xsd">
    <edge id="N_to_J0" from="N" to="J0" priority="2" numLanes="{num_lanes}" speed="{speed}"/>
    <edge id="J0_to_N" from="J0" to="N" priority="2" numLanes="{num_lanes}" speed="{speed}"/>
    <edge id="S_to_J0" from="S" to="J0" priority="2" numLanes="{num_lanes}" speed="{speed}"/>
    <edge id="J0_to_S" from="J0" to="S" priority="2" numLanes="{num_lanes}" speed="{speed}"/>
    <edge id="E_to_J0" from="E" to="J0" priority="2" numLanes="{num_lanes}" speed="{speed}"/>
    <edge id="J0_to_E" from="J0" to="E" priority="2" numLanes="{num_lanes}" speed="{speed}"/>
    <edge id="W_to_J0" from="W" to="J0" priority="2" numLanes="{num_lanes}" speed="{speed}"/>
    <edge id="J0_to_W" from="J0" to="W" priority="2" numLanes="{num_lanes}" speed="{speed}"/>
</edges>
"""
    edg_file.write_text(edg_content, encoding="utf-8")

    # 3. Connections (Lane assignments: Lane 0 = Right + Straight, Lane 1 = Straight + Left)
    con_content = """<?xml version="1.0" encoding="UTF-8"?>
<connections xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://sumo.dlr.de/xsd/connections_file.xsd">
    <!-- North incoming -->
    <connection from="N_to_J0" to="J0_to_W" fromLane="0" toLane="0"/>
    <connection from="N_to_J0" to="J0_to_S" fromLane="0" toLane="0"/>
    <connection from="N_to_J0" to="J0_to_S" fromLane="1" toLane="1"/>
    <connection from="N_to_J0" to="J0_to_E" fromLane="1" toLane="1"/>

    <!-- South incoming -->
    <connection from="S_to_J0" to="J0_to_E" fromLane="0" toLane="0"/>
    <connection from="S_to_J0" to="J0_to_N" fromLane="0" toLane="0"/>
    <connection from="S_to_J0" to="J0_to_N" fromLane="1" toLane="1"/>
    <connection from="S_to_J0" to="J0_to_W" fromLane="1" toLane="1"/>

    <!-- East incoming -->
    <connection from="E_to_J0" to="J0_to_N" fromLane="0" toLane="0"/>
    <connection from="E_to_J0" to="J0_to_W" fromLane="0" toLane="0"/>
    <connection from="E_to_J0" to="J0_to_W" fromLane="1" toLane="1"/>
    <connection from="E_to_J0" to="J0_to_S" fromLane="1" toLane="1"/>

    <!-- West incoming -->
    <connection from="W_to_J0" to="J0_to_S" fromLane="0" toLane="0"/>
    <connection from="W_to_J0" to="J0_to_E" fromLane="0" toLane="0"/>
    <connection from="W_to_J0" to="J0_to_E" fromLane="1" toLane="1"/>
    <connection from="W_to_J0" to="J0_to_N" fromLane="1" toLane="1"/>
</connections>
"""
    con_file.write_text(con_content, encoding="utf-8")

    return {
        "nod": nod_file,
        "edg": edg_file,
        "con": con_file,
        "tll": tll_file,
    }


def generate_network(output_dir: Optional[Path] = None, arm_length: float = 250.0) -> Path:
    """Build the intersection network XML file using netconvert.

    Returns:
        Path to the compiled .net.xml file.
    """
    if output_dir is None:
        output_dir = Path(__file__).resolve().parent / "network"
    output_dir.mkdir(parents=True, exist_ok=True)

    files = create_network_xml_files(output_dir, arm_length=arm_length)
    net_file = output_dir / "intersection.net.xml"

    netconvert_bin = get_netconvert_binary()

    cmd = [
        netconvert_bin,
        f"--node-files={files['nod']}",
        f"--edge-files={files['edg']}",
        f"--connection-files={files['con']}",
        f"--output-file={net_file}",
        "--no-turnarounds=true",
        "--tls.default-type=static",
        "--junctions.join=false",
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(
            f"netconvert failed with code {result.returncode}:\n"
            f"Stdout: {result.stdout}\nStderr: {result.stderr}"
        )

    if not net_file.exists():
        raise FileNotFoundError(f"netconvert did not produce expected file: {net_file}")

    return net_file


if __name__ == "__main__":
    net = generate_network()
    print(f"Successfully generated network at: {net}")
