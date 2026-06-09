#!/usr/bin/env python3

import argparse
import datetime as dt
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple


CPU_SYSFS = Path("/sys/devices/system/cpu")
NODE_SYSFS = Path("/sys/devices/system/node")
ACPI_TABLES_SYSFS = Path("/sys/firmware/acpi/tables")
PROC_CPUINFO = Path("/proc/cpuinfo")
PROC_INTERRUPTS = Path("/proc/interrupts")


@dataclass
class CheckResult:
    check_id: str
    title: str
    status: str
    summary: str
    details: List[str]


def parse_cpu_list(cpu_list: str) -> List[int]:
    result: List[int] = []
    text = cpu_list.strip()
    if not text:
        return result
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start_text, end_text = part.split("-", 1)
            start = int(start_text)
            end = int(end_text)
            result.extend(range(start, end + 1))
        else:
            result.append(int(part))
    return sorted(set(result))


def run_command(command: List[str]) -> Tuple[int, str, str]:
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
        )
        return completed.returncode, completed.stdout, completed.stderr
    except FileNotFoundError:
        return 127, "", f"Command not found: {command[0]}"


def read_text(path: Path) -> Optional[str]:
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return None


def detect_virtualization() -> Dict[str, str]:
    result = {"kind": "none", "detail": "bare-metal or undetected"}
    for command in (["systemd-detect-virt"], ["virt-what"]):
        return_code, stdout, _stderr = run_command(command)
        if return_code == 0 and stdout.strip():
            result["kind"] = stdout.strip().splitlines()[0]
            result["detail"] = "detected by command"
            return result
    if Path("/sys/hypervisor").exists():
        result["kind"] = "guest"
        result["detail"] = "/sys/hypervisor exists"
    return result


def collect_sysfs_topology() -> Dict[int, Dict[str, object]]:
    topology: Dict[int, Dict[str, object]] = {}
    for cpu_path in sorted(CPU_SYSFS.glob("cpu[0-9]*")):
        match = re.fullmatch(r"cpu(\d+)", cpu_path.name)
        if not match:
            continue
        cpu_id = int(match.group(1))
        topo_dir = cpu_path / "topology"
        online_text = read_text(cpu_path / "online")
        topology[cpu_id] = {
            "online": online_text != "0",
            "physical_package_id": read_text(topo_dir / "physical_package_id"),
            "core_id": read_text(topo_dir / "core_id"),
            "thread_siblings_list": parse_cpu_list(read_text(topo_dir / "thread_siblings_list") or ""),
            "core_siblings_list": parse_cpu_list(read_text(topo_dir / "core_siblings_list") or ""),
        }
    return topology


def collect_node_map() -> Dict[int, List[int]]:
    nodes: Dict[int, List[int]] = {}
    for node_path in sorted(NODE_SYSFS.glob("node[0-9]*")):
        match = re.fullmatch(r"node(\d+)", node_path.name)
        if not match:
            continue
        node_id = int(match.group(1))
        cpulist = read_text(node_path / "cpulist") or ""
        nodes[node_id] = parse_cpu_list(cpulist)
    return nodes


def collect_node_distances() -> Dict[int, List[int]]:
    distances: Dict[int, List[int]] = {}
    for node_path in sorted(NODE_SYSFS.glob("node[0-9]*")):
        match = re.fullmatch(r"node(\d+)", node_path.name)
        if not match:
            continue
        node_id = int(match.group(1))
        raw = read_text(node_path / "distance")
        if raw:
            distances[node_id] = [int(item) for item in raw.split()]
    return distances


def collect_proc_cpuinfo() -> List[Dict[str, str]]:
    if not PROC_CPUINFO.exists():
        return []
    entries: List[Dict[str, str]] = []
    current: Dict[str, str] = {}
    for line in PROC_CPUINFO.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            if current:
                entries.append(current)
                current = {}
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        current[key.strip()] = value.strip()
    if current:
        entries.append(current)
    return entries


def collect_lscpu() -> Dict[str, str]:
    return_code, stdout, _stderr = run_command(["lscpu"])
    if return_code != 0:
        return {}
    result: Dict[str, str] = {}
    for line in stdout.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        result[key.strip()] = value.strip()
    return result


def collect_numactl() -> str:
    return_code, stdout, _stderr = run_command(["numactl", "-H"])
    if return_code != 0:
        return ""
    return stdout.strip()


def collect_irq_affinity(irq_ids: List[int]) -> Dict[int, str]:
    affinities: Dict[int, str] = {}
    for irq_id in irq_ids:
        affinity = read_text(Path(f"/proc/irq/{irq_id}/smp_affinity_list"))
        if affinity is not None:
            affinities[irq_id] = affinity
    return affinities


def collect_acpi_tables() -> List[str]:
    if not ACPI_TABLES_SYSFS.exists():
        return []
    return sorted(path.name for path in ACPI_TABLES_SYSFS.iterdir() if path.is_file())


def make_snapshot(irq_ids: List[int]) -> Dict[str, object]:
    return {
        "timestamp_utc": dt.datetime.utcnow().isoformat() + "Z",
        "hostname": platform.node(),
        "kernel": platform.release(),
        "platform": platform.platform(),
        "virtualization": detect_virtualization(),
        "sysfs_topology": collect_sysfs_topology(),
        "node_map": collect_node_map(),
        "node_distances": collect_node_distances(),
        "proc_cpuinfo": collect_proc_cpuinfo(),
        "lscpu": collect_lscpu(),
        "numactl": collect_numactl(),
        "acpi_tables": collect_acpi_tables(),
        "irq_affinity": collect_irq_affinity(irq_ids),
    }


class Auditor:
    def __init__(self, args: argparse.Namespace, snapshot: Dict[str, object]):
        self.args = args
        self.snapshot = snapshot
        self.results: List[CheckResult] = []

    def add(self, check_id: str, title: str, status: str, summary: str, details: Optional[List[str]] = None) -> None:
        self.results.append(CheckResult(check_id, title, status, summary, details or []))

    def run(self) -> List[CheckResult]:
        self.check_ct01_smt_consistency()
        self.check_ct02_mapping_consistency()
        self.check_ct03_node_mapping()
        self.check_ct04_acpi_tables()
        self.check_ct05_apic_mapping()
        self.check_ct06_irq_affinity()
        self.check_ct07_baseline_stability()
        self.check_ct08_virtualization_topology()
        self.check_ct09_numa_distance_sanity()
        self.check_ct10_delayed_recheck()
        return self.results

    def online_cpu_ids(self) -> List[int]:
        topology = self.snapshot["sysfs_topology"]
        return sorted(cpu_id for cpu_id, item in topology.items() if item["online"])

    def cpu_groups(self) -> Dict[Tuple[str, str], List[int]]:
        groups: Dict[Tuple[str, str], List[int]] = {}
        topology = self.snapshot["sysfs_topology"]
        for cpu_id, item in topology.items():
            if not item["online"]:
                continue
            key = (str(item["physical_package_id"]), str(item["core_id"]))
            groups.setdefault(key, []).append(cpu_id)
        return {key: sorted(value) for key, value in groups.items()}

    def check_ct01_smt_consistency(self) -> None:
        expected = self.args.expected_threads_per_core
        bad_groups: List[str] = []
        for key, cpus in self.cpu_groups().items():
            if len(cpus) != expected:
                bad_groups.append(f"package={key[0]} core={key[1]} online_threads={cpus}")
        if bad_groups:
            self.add(
                "CT-01",
                "SMT-2 consistency",
                "FAIL",
                f"Expected {expected} online threads per core, found {len(bad_groups)} mismatched core groups.",
                bad_groups[:20],
            )
            return
        self.add(
            "CT-01",
            "SMT-2 consistency",
            "PASS",
            f"All online cores expose exactly {expected} thread(s).",
        )

    def check_ct02_mapping_consistency(self) -> None:
        topology = self.snapshot["sysfs_topology"]
        package_members: Dict[str, List[int]] = {}
        failures: List[str] = []
        for cpu_id, item in topology.items():
            package_members.setdefault(str(item["physical_package_id"]), []).append(cpu_id)
        for package, members in package_members.items():
            package_members[package] = sorted(members)
        for cpu_id, item in topology.items():
            package = str(item["physical_package_id"])
            expected_core_siblings = package_members.get(package, [])
            actual_core_siblings = item["core_siblings_list"]
            if actual_core_siblings and actual_core_siblings != expected_core_siblings:
                failures.append(
                    f"cpu={cpu_id} core_siblings={actual_core_siblings} expected={expected_core_siblings}"
                )
            thread_key = (str(item["physical_package_id"]), str(item["core_id"]))
            expected_threads = self.cpu_groups().get(thread_key, [])
            actual_threads = sorted(cpu for cpu in item["thread_siblings_list"] if topology.get(cpu, {}).get("online", False))
            if item["online"] and actual_threads and actual_threads != expected_threads:
                failures.append(
                    f"cpu={cpu_id} thread_siblings_online={actual_threads} expected={expected_threads}"
                )
        if failures:
            self.add(
                "CT-02",
                "Socket/core/thread mapping consistency",
                "FAIL",
                f"Found {len(failures)} sibling mapping inconsistencies.",
                failures[:20],
            )
            return
        self.add(
            "CT-02",
            "Socket/core/thread mapping consistency",
            "PASS",
            "Thread sibling and package sibling relationships are internally consistent.",
        )

    def check_ct03_node_mapping(self) -> None:
        online = set(self.online_cpu_ids())
        node_map = self.snapshot["node_map"]
        if not node_map:
            self.add(
                "CT-03",
                "NUMA node to CPU mapping",
                "SKIP",
                "No NUMA node sysfs data was found.",
            )
            return
        membership: Dict[int, int] = {cpu_id: 0 for cpu_id in online}
        for cpus in node_map.values():
            for cpu_id in cpus:
                if cpu_id in membership:
                    membership[cpu_id] += 1
        bad = [cpu_id for cpu_id, count in sorted(membership.items()) if count != 1]
        details = [f"cpu={cpu_id} node_membership_count={membership[cpu_id]}" for cpu_id in bad]
        if self.args.expected_numa_nodes is not None and len(node_map) != self.args.expected_numa_nodes:
            details.append(
                f"expected_numa_nodes={self.args.expected_numa_nodes} observed_numa_nodes={len(node_map)}"
            )
            bad.append(-1)
        if bad:
            self.add(
                "CT-03",
                "NUMA node to CPU mapping",
                "FAIL",
                "Online CPUs are not mapped one-to-one onto NUMA nodes, or the expected node count mismatched.",
                details[:20],
            )
            return
        self.add(
            "CT-03",
            "NUMA node to CPU mapping",
            "PASS",
            f"All {len(online)} online CPUs map cleanly across {len(node_map)} NUMA node(s).",
        )

    def check_ct04_acpi_tables(self) -> None:
        tables = set(self.snapshot["acpi_tables"])
        required = [name.strip() for name in self.args.required_acpi_tables.split(",") if name.strip()]
        missing = [table for table in required if table not in tables]
        if missing:
            self.add(
                "CT-04",
                "ACPI topology table presence",
                "FAIL",
                "One or more required ACPI tables are missing.",
                [f"missing={table}" for table in missing],
            )
            return
        present_optional = [table for table in ["PPTT", "SLIT"] if table in tables]
        self.add(
            "CT-04",
            "ACPI topology table presence",
            "PASS",
            f"All required ACPI tables are present. Optional tables detected: {present_optional or ['none']}",
        )

    def check_ct05_apic_mapping(self) -> None:
        cpuinfo = self.snapshot["proc_cpuinfo"]
        if not cpuinfo:
            self.add("CT-05", "APIC mapping sanity", "SKIP", "/proc/cpuinfo is unavailable.")
            return
        apic_ids: Dict[int, int] = {}
        failures: List[str] = []
        topo = self.snapshot["sysfs_topology"]
        for entry in cpuinfo:
            if "processor" not in entry:
                continue
            cpu_id = int(entry["processor"])
            apic_text = entry.get("apicid")
            if apic_text is None:
                continue
            apic_id = int(apic_text)
            if apic_id in apic_ids.values():
                failures.append(f"duplicate_apicid={apic_id} cpu={cpu_id}")
            apic_ids[cpu_id] = apic_id
            physical_id = entry.get("physical id")
            core_id = entry.get("core id")
            if physical_id is not None and str(topo.get(cpu_id, {}).get("physical_package_id")) != physical_id:
                failures.append(
                    f"cpu={cpu_id} physical_id_cpuinfo={physical_id} physical_id_sysfs={topo.get(cpu_id, {}).get('physical_package_id')}"
                )
            if core_id is not None and str(topo.get(cpu_id, {}).get("core_id")) != core_id:
                failures.append(
                    f"cpu={cpu_id} core_id_cpuinfo={core_id} core_id_sysfs={topo.get(cpu_id, {}).get('core_id')}"
                )
        if not apic_ids:
            self.add(
                "CT-05",
                "APIC mapping sanity",
                "SKIP",
                "No apicid fields were found in /proc/cpuinfo.",
            )
            return
        if failures:
            self.add(
                "CT-05",
                "APIC mapping sanity",
                "FAIL",
                f"APIC ID or CPU mapping inconsistencies detected: {len(failures)} issue(s).",
                failures[:20],
            )
            return
        self.add(
            "CT-05",
            "APIC mapping sanity",
            "PASS",
            f"APIC IDs are unique across {len(apic_ids)} CPU record(s) and match sysfs topology fields.",
        )

    def check_ct06_irq_affinity(self) -> None:
        irq_ids = self.args.irq
        if not irq_ids:
            self.add(
                "CT-06",
                "IRQ affinity topology check",
                "SKIP",
                "No IRQ IDs were provided. Re-run with --irq <id> to enable this check.",
            )
            return
        online = set(self.online_cpu_ids())
        failures: List[str] = []
        irq_affinity = self.snapshot["irq_affinity"]
        for irq_id in irq_ids:
            affinity_text = irq_affinity.get(irq_id)
            if not affinity_text:
                failures.append(f"irq={irq_id} affinity_file_missing")
                continue
            target_cpus = set(parse_cpu_list(affinity_text))
            if not target_cpus:
                failures.append(f"irq={irq_id} empty_affinity")
                continue
            if not target_cpus.issubset(online):
                failures.append(f"irq={irq_id} target_cpus_outside_online={sorted(target_cpus - online)}")
        if failures:
            self.add(
                "CT-06",
                "IRQ affinity topology check",
                "FAIL",
                f"IRQ affinity validation failed for {len(failures)} item(s).",
                failures,
            )
            return
        self.add(
            "CT-06",
            "IRQ affinity topology check",
            "PASS",
            f"All requested IRQ affinities map to online CPUs: {irq_ids}",
        )

    def check_ct07_baseline_stability(self) -> None:
        baseline_path = self.args.baseline
        if not baseline_path:
            self.add(
                "CT-07",
                "Reboot-to-reboot topology stability",
                "SKIP",
                "No baseline snapshot was supplied. Re-run with --baseline <snapshot.json> to compare.",
            )
            return
        path = Path(baseline_path)
        if not path.exists():
            self.add(
                "CT-07",
                "Reboot-to-reboot topology stability",
                "SKIP",
                f"Baseline snapshot does not exist yet: {path}",
            )
            return
        baseline = json.loads(path.read_text(encoding="utf-8"))
        current = self.snapshot["sysfs_topology"]
        if baseline.get("sysfs_topology") != current or baseline.get("node_map") != self.snapshot["node_map"]:
            self.add(
                "CT-07",
                "Reboot-to-reboot topology stability",
                "FAIL",
                "Current topology differs from the supplied baseline snapshot.",
                ["Compare snapshot JSON files for exact field deltas."],
            )
            return
        self.add(
            "CT-07",
            "Reboot-to-reboot topology stability",
            "PASS",
            "Current topology matches the supplied baseline snapshot.",
        )

    def check_ct08_virtualization_topology(self) -> None:
        virtualization = self.snapshot["virtualization"]
        if virtualization["kind"] == "none" and not self.args.force_guest_checks:
            self.add(
                "CT-08",
                "Guest topology sanity",
                "SKIP",
                "Virtualization was not detected. Use --force-guest-checks to run this check anyway.",
            )
            return
        lscpu = self.snapshot["lscpu"]
        threads = lscpu.get("Thread(s) per core")
        sockets = lscpu.get("Socket(s)")
        cpus = lscpu.get("CPU(s)")
        if not (threads and sockets and cpus):
            self.add(
                "CT-08",
                "Guest topology sanity",
                "FAIL",
                "Virtualized environment detected, but lscpu output is incomplete.",
            )
            return
        self.add(
            "CT-08",
            "Guest topology sanity",
            "PASS",
            f"Guest topology is reportable: CPUs={cpus}, sockets={sockets}, threads_per_core={threads}.",
            [f"virtualization={virtualization['kind']}", f"detail={virtualization['detail']}"],
        )

    def check_ct09_numa_distance_sanity(self) -> None:
        distances = self.snapshot["node_distances"]
        if not distances:
            self.add(
                "CT-09",
                "NUMA distance matrix sanity",
                "SKIP",
                "No NUMA distance files were found under /sys/devices/system/node.",
            )
            return
        failures: List[str] = []
        for node_id, matrix in sorted(distances.items()):
            if node_id >= len(matrix):
                failures.append(f"node={node_id} matrix_length={len(matrix)}")
                continue
            local_distance = matrix[node_id]
            remote_distances = [distance for index, distance in enumerate(matrix) if index != node_id]
            if remote_distances and any(distance < local_distance for distance in remote_distances):
                failures.append(
                    f"node={node_id} local_distance={local_distance} remote_distances={remote_distances}"
                )
        if failures:
            self.add(
                "CT-09",
                "NUMA distance matrix sanity",
                "FAIL",
                "NUMA distance matrix violates local <= remote expectation.",
                failures,
            )
            return
        self.add(
            "CT-09",
            "NUMA distance matrix sanity",
            "PASS",
            f"NUMA distance matrices are internally sane across {len(distances)} node(s).",
        )

    def check_ct10_delayed_recheck(self) -> None:
        if self.args.recheck_seconds <= 0:
            self.add(
                "CT-10",
                "Delayed topology recheck",
                "SKIP",
                "No delayed recheck requested. Use --recheck-seconds <n> to enable this stability check.",
            )
            return
        time.sleep(self.args.recheck_seconds)
        later = make_snapshot(self.args.irq)
        if later["sysfs_topology"] != self.snapshot["sysfs_topology"] or later["node_map"] != self.snapshot["node_map"]:
            self.add(
                "CT-10",
                "Delayed topology recheck",
                "FAIL",
                f"Topology changed after {self.args.recheck_seconds} second(s).",
            )
            return
        self.add(
            "CT-10",
            "Delayed topology recheck",
            "PASS",
            f"Topology remained stable across a {self.args.recheck_seconds}-second recheck window.",
        )


def render_report(results: List[CheckResult]) -> str:
    lines = []
    counts: Dict[str, int] = {"PASS": 0, "FAIL": 0, "SKIP": 0}
    for result in results:
        counts[result.status] = counts.get(result.status, 0) + 1
    lines.append("CPU Topology Audit Report")
    lines.append("=" * 80)
    lines.append(f"PASS={counts.get('PASS', 0)} FAIL={counts.get('FAIL', 0)} SKIP={counts.get('SKIP', 0)}")
    lines.append("")
    for result in results:
        lines.append(f"[{result.status}] {result.check_id} {result.title}")
        lines.append(f"  {result.summary}")
        for detail in result.details:
            lines.append(f"  - {detail}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Audit Linux CPU topology and emit PASS/FAIL/SKIP results.",
    )
    parser.add_argument("--output-dir", default="cpu_topology_audit_out", help="Directory for reports and snapshots.")
    parser.add_argument("--baseline", help="Path to a prior snapshot.json for reboot-to-reboot comparison.")
    parser.add_argument("--expected-threads-per-core", type=int, default=2)
    parser.add_argument("--expected-numa-nodes", type=int)
    parser.add_argument("--required-acpi-tables", default="MADT,SRAT")
    parser.add_argument("--irq", type=int, action="append", default=[], help="IRQ ID to validate via smp_affinity_list.")
    parser.add_argument("--recheck-seconds", type=int, default=0, help="Optional delayed recheck window.")
    parser.add_argument("--force-guest-checks", action="store_true", help="Run guest checks even if virtualization is not detected.")
    return parser


def main() -> int:
    if os.name != "posix":
        print("This audit framework is intended to run on Linux targets.", file=sys.stderr)
        return 2
    args = build_arg_parser().parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    snapshot = make_snapshot(args.irq)
    auditor = Auditor(args, snapshot)
    results = auditor.run()

    summary = {
        "generated_at_utc": dt.datetime.utcnow().isoformat() + "Z",
        "results": [asdict(result) for result in results],
        "snapshot": snapshot,
    }
    snapshot_path = output_dir / "snapshot.json"
    report_path = output_dir / "report.txt"
    summary_path = output_dir / "summary.json"

    snapshot_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    report_text = render_report(results)
    report_path.write_text(report_text, encoding="utf-8")
    print(report_text)

    has_failures = any(result.status == "FAIL" for result in results)
    return 1 if has_failures else 0


if __name__ == "__main__":
    sys.exit(main())