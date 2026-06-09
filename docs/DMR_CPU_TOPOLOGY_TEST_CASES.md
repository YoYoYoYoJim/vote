# Intel DMR CPU Topology Test Cases

## Overview
This document summarizes 10 executable CPU topology validation cases for Intel DMR platforms. The structure matches the existing Excel-oriented test case format used in this workspace.

**Test Coverage:**
- SMT and core/thread consistency (CPUTOPO-001, 002)
- NUMA and ACPI topology exposure (CPUTOPO-003, 004)
- APIC and interrupt affinity sanity (CPUTOPO-005, 006)
- Reboot and virtualization stability (CPUTOPO-007, 008)
- NUMA distance and delayed stability checks (CPUTOPO-009, 010)

---

## Test Case Details

### Category 1: Core and Thread Topology

#### CPUTOPO-001: SMT Thread Pairing Consistency
**Objective:** Verify that each online core exposes the expected number of sibling threads and that DMR SMT-2 assumptions are reflected consistently in OS-visible topology.

**Prerequisites:**
- Linux target booted successfully
- Access to `/sys/devices/system/cpu`
- Expected threads-per-core value is known for the SKU under test

**Test Steps:**
1. Run: `python3 scripts/cpu_topology_audit.py --output-dir cpu_topology_audit_out --expected-threads-per-core 2`
2. Review `CT-01` in `cpu_topology_audit_out/report.txt`
3. If needed, cross-check with `lscpu -e=cpu,socket,core,online`
4. Confirm each `(physical_package_id, core_id)` group has exactly two online logical CPUs

**Expected Results:**
- Every online core resolves to exactly two online thread siblings
- No single-thread orphan cores appear unless explicitly defeatured by platform policy
- Audit output marks `CT-01` as PASS

**Acceptance Criteria:**
- Mismatched core groups: 0
- Missing sibling count: 0
- Report status for `CT-01`: PASS

---

#### CPUTOPO-002: Socket/Core/Thread Mapping Consistency
**Objective:** Verify that `thread_siblings_list` and `core_siblings_list` are internally consistent with sysfs package and core identifiers.

**Prerequisites:**
- CPUTOPO-001 passed
- Access to CPU topology sysfs nodes

**Test Steps:**
1. Run: `python3 scripts/cpu_topology_audit.py --output-dir cpu_topology_audit_out`
2. Inspect `CT-02` in the generated report
3. Optionally review raw fields under `/sys/devices/system/cpu/cpu*/topology/`
4. Compare package-wide sibling masks against all CPUs in the same package

**Expected Results:**
- Every CPU reports a valid package-wide `core_siblings_list`
- Online thread siblings for a core match the CPUs grouped by package/core ID
- No conflicting sibling masks are detected

**Acceptance Criteria:**
- Sibling mapping inconsistencies: 0
- Package sibling mask mismatches: 0
- Report status for `CT-02`: PASS

---

### Category 2: NUMA and ACPI Exposure

#### CPUTOPO-003: NUMA Node to CPU Mapping
**Objective:** Verify that each online CPU belongs to exactly one NUMA node and that the observed node count matches platform expectations.

**Prerequisites:**
- Linux NUMA support enabled
- Access to `/sys/devices/system/node`
- Expected NUMA node count known for the platform configuration

**Test Steps:**
1. Run: `python3 scripts/cpu_topology_audit.py --output-dir cpu_topology_audit_out --expected-numa-nodes <N>`
2. Review `CT-03` in the report
3. Cross-check with `numactl -H`
4. Verify that no online CPU appears in more than one node `cpulist`

**Expected Results:**
- All online CPUs map one-to-one onto NUMA nodes
- Observed NUMA node count matches the supplied expected value
- No unassigned online CPUs exist

**Acceptance Criteria:**
- Duplicate NUMA membership count: 0
- Unassigned online CPUs: 0
- NUMA node count delta: 0

---

#### CPUTOPO-004: ACPI Topology Table Presence
**Objective:** Verify that required ACPI topology-related tables are present on the target, including at minimum MADT and SRAT, with optional PPTT when provided by firmware.

**Prerequisites:**
- Linux target booted with ACPI enabled
- Access to `/sys/firmware/acpi/tables`
- Required ACPI table list defined for the test run

**Test Steps:**
1. Run: `python3 scripts/cpu_topology_audit.py --output-dir cpu_topology_audit_out --required-acpi-tables MADT,SRAT,PPTT`
2. Review `CT-04` in the report
3. If a table is missing, confirm with `ls /sys/firmware/acpi/tables`
4. Optionally export ACPI data with `acpidump > acpi.out` for offline analysis

**Expected Results:**
- All required ACPI tables supplied in the command line are present
- Optional PPTT is reported when available
- Missing tables are explicitly identified in the report

**Acceptance Criteria:**
- Missing required ACPI tables: 0
- Report status for `CT-04`: PASS
- ACPI table directory readable: yes

---

### Category 3: APIC and Interrupt Affinity

#### CPUTOPO-005: APIC Mapping Sanity
**Objective:** Verify that APIC IDs are unique and that `/proc/cpuinfo` package/core identifiers remain consistent with sysfs topology data.

**Prerequisites:**
- Access to `/proc/cpuinfo`
- APIC fields exposed by the kernel on the target platform

**Test Steps:**
1. Run: `python3 scripts/cpu_topology_audit.py --output-dir cpu_topology_audit_out`
2. Review `CT-05` in the report
3. Check `/proc/cpuinfo` for `apicid`, `physical id`, and `core id`
4. Confirm no duplicate APIC IDs appear across processors

**Expected Results:**
- Every APIC ID is unique for visible processors
- `physical id` and `core id` align with sysfs values
- No APIC aliasing is reported

**Acceptance Criteria:**
- Duplicate APIC IDs: 0
- CPUinfo/sysfs topology mismatches: 0
- Report status for `CT-05`: PASS

---

#### CPUTOPO-006: IRQ Affinity Topology Check
**Objective:** Verify that selected IRQ affinity masks target only online CPUs and respect current topology visibility.

**Prerequisites:**
- One or more relevant IRQ IDs identified
- Access to `/proc/irq/<IRQ>/smp_affinity_list`
- CPUTOPO-005 passed

**Test Steps:**
1. Run: `python3 scripts/cpu_topology_audit.py --output-dir cpu_topology_audit_out --irq <IRQ1> --irq <IRQ2>`
2. Review `CT-06` in the report
3. Inspect `/proc/irq/<IRQ>/smp_affinity_list` manually if needed
4. Confirm each affinity mask points only to online CPUs

**Expected Results:**
- Every requested IRQ has a readable affinity mask
- Affinity masks are non-empty
- No mask targets an offline CPU

**Acceptance Criteria:**
- IRQ affinity read failures: 0
- Empty affinity masks: 0
- Offline CPU targets in affinity: 0

---

### Category 4: Stability and Environment

#### CPUTOPO-007: Reboot-to-Reboot Topology Stability
**Objective:** Verify that CPU and NUMA topology remain stable across reboots by comparing the current snapshot with a saved baseline.

**Prerequisites:**
- A previously captured baseline snapshot file
- Same platform and firmware settings as baseline run

**Test Steps:**
1. Capture a baseline: `python3 scripts/cpu_topology_audit.py --output-dir baseline_run`
2. Reboot the target
3. Run: `python3 scripts/cpu_topology_audit.py --output-dir current_run --baseline baseline_run/snapshot.json`
4. Review `CT-07` in `current_run/report.txt`

**Expected Results:**
- Current `sysfs_topology` matches the baseline snapshot
- Current `node_map` matches the baseline snapshot
- No unexpected CPU/package/core renumbering occurs

**Acceptance Criteria:**
- Snapshot topology delta: 0
- NUMA mapping delta: 0
- Report status for `CT-07`: PASS

---

#### CPUTOPO-008: Guest Topology Sanity
**Objective:** Verify that the platform can report coherent guest-visible topology information when running in a virtualized environment.

**Prerequisites:**
- System is running as a guest or guest checks are intentionally forced
- `lscpu` available in the guest environment

**Test Steps:**
1. Run in guest: `python3 scripts/cpu_topology_audit.py --output-dir cpu_topology_audit_out`
2. If virtualization is not auto-detected, rerun with `--force-guest-checks`
3. Review `CT-08` in the report
4. Confirm `lscpu` exposes CPU count, socket count, and thread count coherently

**Expected Results:**
- Virtualization state is correctly detected or explicitly forced
- Guest topology is reportable through `lscpu`
- No missing key topology fields in the guest report

**Acceptance Criteria:**
- Missing guest topology fields: 0
- Report status for `CT-08`: PASS when guest checks are enabled
- Virtualization detection ambiguity resolved: yes

---

#### CPUTOPO-009: NUMA Distance Matrix Sanity
**Objective:** Verify that each node's local NUMA distance is not worse than any of its remote distances.

**Prerequisites:**
- NUMA distance files exposed under `/sys/devices/system/node/node*/distance`
- CPUTOPO-003 passed

**Test Steps:**
1. Run: `python3 scripts/cpu_topology_audit.py --output-dir cpu_topology_audit_out`
2. Review `CT-09` in the report
3. Cross-check with `numactl -H` if necessary
4. Verify that each node's self-distance is less than or equal to remote distances

**Expected Results:**
- Local node distance is the minimum value in each row of the matrix
- Matrix dimensions align with node count
- No malformed distance rows are present

**Acceptance Criteria:**
- Distance matrix violations: 0
- Missing node distance files for online nodes: 0
- Report status for `CT-09`: PASS

---

#### CPUTOPO-010: Delayed Topology Recheck Stability
**Objective:** Verify that topology and NUMA mappings remain stable across a delayed sampling window without rebooting.

**Prerequisites:**
- A stable system state for the observation window
- Desired recheck interval known

**Test Steps:**
1. Run: `python3 scripts/cpu_topology_audit.py --output-dir cpu_topology_audit_out --recheck-seconds 30`
2. Wait for the delayed recheck to complete
3. Review `CT-10` in the report
4. Compare the initial and delayed snapshots for CPU and node map changes

**Expected Results:**
- No topology changes occur during the recheck interval
- CPU online state remains unchanged unless intentionally hotplugged
- Node assignments remain identical across both snapshots

**Acceptance Criteria:**
- Topology drift during recheck: 0
- Node map drift during recheck: 0
- Report status for `CT-10`: PASS

---

## Notes

- The companion audit script is [scripts/cpu_topology_audit.py](../scripts/cpu_topology_audit.py).
- This file is intended to be converted into Excel using [scripts/md_to_excel.py](../scripts/md_to_excel.py).
- For ACPI deep inspection beyond table presence, use `acpidump`, `acpixtract`, and `iasl` separately.