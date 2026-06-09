# PCIe 6.0 OS User Space Test Suite - Test Cases Reference

## Overview
This document defines 20 comprehensive test cases for PCIe 6.0 endpoint/device validation in OS user space (kernel + user-level tooling).

**Test Coverage:**
- Device Enumeration & Topology (PCIE6-US-001, 002)
- Link Negotiation & Stability (PCIE6-US-003 to 005)
- Configuration Space Access (PCIE6-US-006)
- Memory-Mapped I/O & BAR (PCIE6-US-007)
- Interrupt Handling (PCIE6-US-008)
- Bandwidth & Performance (PCIE6-US-009 to 012)
- Error Handling & RAS (PCIE6-US-013 to 015)
- Advanced Features (PCIE6-US-016 to 018)
- Telemetry & Reporting (PCIE6-US-019 to 020)

---

## Test Case Details

### Category 1: Enumeration & Topology

#### PCIE6-US-001: Device Enumeration and Topology Discovery
**Objective:** Verify all PCIe devices are correctly enumerated and present in the system topology.

**Prerequisites:**
- System boot completed
- All PCIe devices inserted and powered
- Linux kernel 6.1+ (recommended 6.6+) or Windows 10/11

**Test Steps:**
1. Run: `python scripts/pcie6_test_suite.py -t enum -v`
2. Capture lspci/Device Manager output
3. Cross-reference against hardware design topology
4. Check for "Unknown bridge" or "Unknown device" entries

**Expected Results:**
- All endpoints enumerated
- No Unknown devices
- BDF (Bus:Device.Function) matches physical layout
- Topology hierarchy consistent with BIOS/UEFI configuration

**Acceptance Criteria:**
- Device count: 100% match to known hardware
- Unknown device count: 0
- Enumeration time: < 2 seconds

---

#### PCIE6-US-002: PCIe Capability Register Readability
**Objective:** Ensure all PCIe capability registers are accessible from user space.

**Prerequisites:**
- At least one PCIe endpoint
- PCIE6-US-001 passed

**Test Steps (Linux):**
```bash
# Capture all capability offsets
lspci -s 0000:00:14.0 -vvv | grep -E "(Capabilities|Offset)" > cap_dump.txt

# Verify using setpci if available
setpci -s 0000:00:14.0 0x00.w  # Vendor/Device ID at offset 0x00
```

**Test Steps (Windows):**
1. Open Device Manager
2. Find target device, Properties → Details → Hardware IDs
3. Record Vendor ID and Device ID

**Expected Results:**
- All Capability offsets readable
- No timeout errors
- Consistent reads (back-to-back reads match)

**Acceptance Criteria:**
- Readable capability count: >= 95% of expected
- Read retry rate: < 0.1%

---

### Category 2: Link Negotiation

#### PCIE6-US-003: Link Speed and Width Negotiation
**Objective:** Verify correct PCIe link speed and width after power-up negotiation.

**Prerequisites:**
- PCIE6-US-001 passed
- Device design specification available (e.g., "x16 Gen 6" = 64 GT/s × 16 lanes)

**Test Steps:**
```bash
# Linux - Extract from lspci
python scripts/pcie6_test_suite.py -t link -v

# Or manually:
lspci -s <BDF> -vvv | grep -E "LnkCap:|LnkSta:"
```

**Example Output Interpretation:**
```
LnkCap: Port #0, Speed 64GT/s, Width x16, ASPM L0s L1 L1.1 L1.2 ARO
LnkSta: Speed 64GT/s (ok), Width x16 (ok)
```
- Speed negotiated: 64 GT/s (expected for Gen 6)
- Width negotiated: x16 (expected for full width)

**Expected Results:**
- Negotiated speed >= design speed (allow 1 generation fallback in early platforms)
- Negotiated width >= 0.75 × design width (allow for half-width fallback, but report)

**Acceptance Criteria:**
- Speed degradation: < 5% (< 1 generation)
- Width degradation: < 5% devices show degradation
- Minimum acceptable Gen 4 (16 GT/s) for Gen 5/6 capable devices

---

#### PCIE6-US-004: Link Retrain Stability
**Objective:** Verify link remains stable during forced retraining cycles.

**Prerequisites:**
- Root access (Linux) or admin (Windows)
- PCIE6-US-003 passed

**Test Steps:**
```bash
# Linux - Force retrain (if supported by driver/platform)
# Typically via sysfs (platform-dependent)
# Example (may not work on all platforms):
# echo 1 > /sys/bus/pci/devices/0000:00:14.0/link_retrain

# Safe alternative: check for historical retrains in dmesg
dmesg | grep -i "retrain\|training" | tail -20
```

**Expected Results:**
- Link remains active after retrain
- No correctable error storm (< 1 error per minute during retrain)
- Device re-enumerates if fully retrained

**Acceptance Criteria:**
- Retrain duration: < 50 ms
- Retrain event count per hour: < 5 (outside stress scenarios)

---

#### PCIE6-US-005: Configuration Space Read/Write Boundary Verification
**Objective:** Verify read-only fields cannot be altered; read-write fields work correctly.

**Prerequisites:**
- Root/admin access
- Target device datasheet available

**Test Steps:**
```bash
# Read current register value
OLD_VALUE=$(setpci -s 0000:00:14.0 COMMAND.w)  # Command register (offset 0x04)
echo "Old value: 0x$OLD_VALUE"

# Attempt to write new value
setpci -s 0000:00:14.0 COMMAND.w=0x0146  # Enable bus master, memory space, I/O space

# Read back
NEW_VALUE=$(setpci -s 0000:00:14.0 COMMAND.w)
echo "New value: 0x$NEW_VALUE"

# Restore
setpci -s 0000:00:14.0 COMMAND.w=0x$OLD_VALUE
```

**Expected Results:**
- Writable bits change as expected
- Read-only bits (RO) remain unchanged
- Device remains functional after read/write
- No timeouts or hangs

**Acceptance Criteria:**
- Write success rate: 100%
- Read-only field protection: 100%
- Bit-level accuracy: 100%

---

### Category 3: Memory & I/O Access

#### PCIE6-US-006: BAR Mapping and Access
**Objective:** Verify BAR addresses are valid, non-overlapping, and user-space accessible.

**Prerequisites:**
- PCIE6-US-002 passed

**Test Steps:**
```bash
# Linux - List BARs for device
lspci -s 0000:00:14.0 -vvv | grep -E "Memory at|I/O at"

# Check sysfs
cat /sys/bus/pci/devices/0000:00:14.0/resource

# User-space access (via VFIO or UIO driver)
# Requires driver setup; skip if not testing direct access
```

**Expected Results:**
- All BARs have valid (non-zero) addresses
- No address overlap between BARs
- Memory BARs are prefetchable if marked
- I/O BARs are below 64 KB (typically)

**Acceptance Criteria:**
- BAR overlap count: 0
- Invalid BAR count: 0
- User-space access: successful with driver support

---

#### PCIE6-US-007: MSI/MSI-X Interrupt Configuration
**Objective:** Verify interrupt configuration and generation.

**Prerequisites:**
- PCIE6-US-001 passed
- Target device supports MSI or MSI-X

**Test Steps:**
```bash
# Check MSI configuration
lspci -s 0000:00:14.0 -vvv | grep -E "MSI:|MSI-X:"

# Monitor interrupt rate under load
watch -n 1 'grep 0000:00:14.0 /proc/interrupts'

# Generate I/O load (device-specific)
# Example for NIC:
iperf3 -c <remote> -t 10

# Check interrupt count increased
grep 0000:00:14.0 /proc/interrupts
```

**Expected Results:**
- MSI/MSI-X enabled (Enable+ in lspci output)
- Interrupt count increases proportional to load
- No interrupt storm (< 1,000,000 interrupts/second unless expected)

**Acceptance Criteria:**
- Interrupt rate linearity: > 0.95 (proportional to load)
- Interrupt storm occurrences: 0
- Missing interrupt count: 0

---

### Category 4: Bandwidth & Performance

#### PCIE6-US-008: Single Device Bandwidth Baseline
**Objective:** Establish baseline throughput for individual PCIe device.

**Prerequisites:**
- PCIE6-US-001 passed
- Device type known (NVMe, NIC, accelerator)

**Test Steps:**
```bash
# NVMe example
fio --name=read --filename=/dev/nvme0n1 --direct=1 --rw=read \
    --bs=4k --iodepth=32 --numjobs=4 --runtime=60 --output=fio_baseline.txt

# NIC example (requires remote target)
iperf3 -c <remote_ip> -t 30 -R  # Reverse: pull from remote

# Accelerator (device-specific)
# Use vendor benchmark tool
```

**Expected Results:**
- Read bandwidth: >= 90% of PCIe gen capability
  - Gen 4 ×16: ~7.5 GB/s (0.5% overhead for PCIe protocol)
  - Gen 5 ×16: ~15 GB/s
  - Gen 6 ×16: ~30 GB/s
- Latency p99: within device specifications
- CPU utilization: reasonable for workload

**Acceptance Criteria:**
- Throughput: >= 80% of theoretical maximum
- Latency p50: < 1 ms (typical)
- Latency p99: < 10 ms (typical)
- CPU efficiency: > 50% throughput per 100% core

---

#### PCIE6-US-009: Multi-Device Concurrent Bandwidth
**Objective:** Verify fair bandwidth sharing between multiple PCIe devices.

**Prerequisites:**
- At least 2 PCIe devices
- PCIE6-US-008 passed for each device

**Test Steps:**
```bash
# Launch concurrent load on multiple devices
# Device 1
fio --name=dev1 --filename=/dev/nvme0n1 --direct=1 --rw=read --bs=4k \
    --iodepth=16 --numjobs=2 --runtime=60 --output=fio_dev1.txt &

# Device 2
fio --name=dev2 --filename=/dev/nvme1n1 --direct=1 --rw=read --bs=4k \
    --iodepth=16 --numjobs=2 --runtime=60 --output=fio_dev2.txt &

wait

# Compare throughputs
```

**Expected Results:**
- Total system throughput: >= single-device baseline × 0.9
- Per-device fairness: deviation < 20%
- No device starved (bandwidth > 0 consistently)

**Acceptance Criteria:**
- Starvation events: 0
- Fairness ratio (min/max throughput): > 0.8
- Total throughput drop: < 10%

---

#### PCIE6-US-010: NUMA Affinity Impact
**Objective:** Verify NUMA awareness and performance scaling.

**Prerequisites:**
- Multi-socket system (2+ NUMA nodes)
- PCIE6-US-008 passed

**Test Steps:**
```bash
# Identify PCIe device NUMA locality
numactl -H  # List NUMA topology

# Determine which socket device is connected to
cat /sys/bus/pci/devices/0000:00:14.0/numa_node  # e.g., 0

# Test with local (socket 0) memory
numactl --membind=0 fio --name=local --filename=/dev/nvme0n1 \
    --direct=1 --rw=read --bs=4k --iodepth=32 --runtime=60 --output=fio_local.txt

# Test with remote (socket 1) memory
numactl --membind=1 fio --name=remote --filename=/dev/nvme0n1 \
    --direct=1 --rw=read --bs=4k --iodepth=32 --runtime=60 --output=fio_remote.txt

# Compare latency
```

**Expected Results:**
- Local throughput: baseline (e.g., 7.5 GB/s for Gen 4)
- Remote throughput: 80-95% of local (typical NUMA penalty: 5-20%)
- Remote latency: +5-15 µs vs. local

**Acceptance Criteria:**
- NUMA awareness: detected correctly
- Remote penalty: < 20%
- Latency variance: < 30%

---

### Category 5: Error Handling & RAS

#### PCIE6-US-011: AER Correctable Error Detection and Recovery
**Objective:** Verify correctable errors are reported and device remains operational.

**Prerequisites:**
- AER (Advanced Error Reporting) capable device
- Root access
- PCIE6-US-001 passed

**Test Steps:**
```bash
# Check AER support
lspci -s 0000:00:14.0 -vvv | grep "AER"

# Enable AER logging (if not already)
# Check dmesg for AER messages
dmesg | grep -i "AER\|Correctable\|Uncorrectable" | tail -20

# Inject correctable error (platform/driver dependent; may not be available)
# Typically requires debugfs and special tools
```

**Expected Results:**
- AER Capability present
- Correctable errors logged to dmesg/rasdaemon
- Device remains accessible after correctable error
- Error counter increments

**Acceptance Criteria:**
- AER support: detected or N/A
- Recovery success rate: 100%
- Error storm: < 1000 errors/minute

---

#### PCIE6-US-012: AER Uncorrectable Non-Fatal Error Recovery
**Objective:** Verify device can recover from uncorrectable non-fatal errors.

**Prerequisites:**
- AER capable device
- PCIE6-US-011 passed
- Root access

**Test Steps:**
```bash
# Monitor AER counters before/after
cat /sys/kernel/debug/aer/*/aer/  # Read AER stats (debugfs)

# Trigger non-fatal error (requires FLR or device-specific trigger)
# Example: Reset link
# echo 1 > /sys/bus/pci/devices/0000:00:14.0/reset

# Verify device recovers
lspci -s 0000:00:14.0  # Should still appear
```

**Expected Results:**
- Device recovers (FLR or link reset succeeds)
- I/O operations resume after recovery
- No data corruption

**Acceptance Criteria:**
- Recovery time: < 1 second
- Data integrity: 100%
- Subsequent operations: successful

---

#### PCIE6-US-013: Link Failure and Surprise Down Handling
**Objective:** Verify graceful degradation or recovery on link loss.

**Prerequisites:**
- PCIE6-US-003 passed
- Test environment supports link simulation

**Test Steps:**
1. Establish steady-state I/O load
2. Simulate link loss (experimental environment only)
3. Observe application behavior
4. Monitor recovery

**Expected Results:**
- Application detects link failure
- Retry logic engages
- Link retrains and stabilizes (if supported)
- Application resumes operation

**Acceptance Criteria:**
- Failure detection time: < 10 seconds
- Data loss: none (with proper buffering)
- Stale data served: 0 instances

---

### Category 6: Advanced Features

#### PCIE6-US-014: Hot-Plug / Surprise Removal
**Objective:** Verify device can be safely added/removed without system crash.

**Prerequisites:**
- Hot-swap capable device
- PCIE6-US-001 passed

**Test Steps:**
```bash
# Scenario 1: Insert device while powered (cold)
1. System powered on
2. Device inserted
3. Monitor dmesg for enumeration
4. Verify new BDF appears

# Scenario 2: Remove device while idle
1. Unbind driver (if bound)
   echo 0000:00:14.0 > /sys/bus/pci/drivers/<driver>/unbind
2. Physically remove device
3. Monitor for errors
4. Verify no hung threads

# Scenario 3: Remove device under I/O load
1. Sustained I/O to device
2. Physically remove
3. Verify graceful error handling
```

**Expected Results:**
- Hot insertion recognized, enumerated
- Hot removal handled gracefully
- No kernel panic
- No hung I/O operations

**Acceptance Criteria:**
- Enumeration success: 100%
- Kernel oops count: 0
- Stale references: 0

---

#### PCIE6-US-015: SR-IOV Virtual Function Lifecycle
**Objective:** Verify SR-IOV VF creation, assignment, and cleanup.

**Prerequisites:**
- SR-IOV capable device
- IOMMU enabled (for isolation)

**Test Steps:**
```bash
# Check SR-IOV support
lspci -s 0000:00:14.0 -vvv | grep "SR-IOV"

# Enable VFs
echo 4 > /sys/bus/pci/devices/0000:00:14.0/sriov_numvfs

# Verify VFs created
lspci | grep "Virtual Function"

# Test VF isolation/bandwidth
# (Bind VF to vfio-pci or driver)

# Disable VFs
echo 0 > /sys/bus/pci/devices/0000:00:14.0/sriov_numvfs
```

**Expected Results:**
- VF count matches requested
- Each VF has unique BDF
- VF I/O isolation functional
- Clean cleanup

**Acceptance Criteria:**
- VF creation success: 100%
- VF count match: 100%
- Isolation: verified
- Cleanup leaks: 0

---

#### PCIE6-US-016: IOMMU/VFIO User-Space Direct Access
**Objective:** Verify user-space I/O with IOMMU protection.

**Prerequisites:**
- IOMMU enabled (VT-d on Intel)
- VFIO support in kernel
- PCIE6-US-015 or VF available

**Test Steps:**
```bash
# Bind device to vfio-pci
modprobe vfio-pci
echo 8086 0000 > /sys/bus/pci/drivers/vfio-pci/new_id  # Vendor:Device

# Or use script:
echo 0000:00:14.0 > /sys/bus/pci/drivers/<old-driver>/unbind
echo 0000:00:14.0 > /sys/bus/pci/drivers/vfio-pci/bind

# User-space application accesses device via VFIO
# (Requires VFIO library or DPDK/SPDK)
dpdk-testpmd -l 0-3 -w 0000:00:14.0 -- --portmask=0x1
```

**Expected Results:**
- Device bind to vfio-pci successful
- User-space DMA functional
- No IOMMU faults
- Performance comparable to kernel driver

**Acceptance Criteria:**
- Bind success: 100%
- IOMMU fault count: 0
- Throughput > 90% of kernel driver

---

### Category 7: Power & Stability

#### PCIE6-US-017: Link Power Management (ASPM) Functionality
**Objective:** Verify ASPM correctly transitions link to low-power states.

**Prerequisites:**
- ASPM capable device
- PCIE6-US-003 passed

**Test Steps:**
```bash
# Check ASPM support
lspci -s 0000:00:14.0 -vvv | grep "ASPM"

# Example output:
# LnkCap: Port #0, ... ASPM L0s L1 L1.1 L1.2 ARO

# Measure power consumption at idle
# (Requires power meter or RAPL counters)
turbostat --interval 5  # Intel CPUs

# Enable maximum ASPM
echo "deep" > /sys/module/pcie_aspm/parameters/policy

# Measure again
turbostat --interval 5

# Check link state
cat /sys/bus/pci/devices/0000:00:14.0/current_link_speed
```

**Expected Results:**
- ASPM supported (L0s, L1, L1.1, L1.2)
- Idle power reduced with ASPM enabled
- Link transitions to lower speed/state when idle
- Performance impact minimal under load

**Acceptance Criteria:**
- Idle power reduction: > 30%
- Load performance impact: < 5%
- State transition latency: < 100 µs

---

#### PCIE6-US-018: Long-Term Stability (Longevity Test)
**Objective:** Verify device and platform stability over extended runtime.

**Prerequisites:**
- All previous tests passed
- Test environment isolated/monitored

**Test Parameters:**
- **Duration:** 24-72 hours
- **Load profile:** Mixed (read/write, sequential/random)
- **Monitoring:** Throughput, latency, errors, temperature

**Test Steps:**
```bash
# Automated longevity script
python scripts/pcie6_test_suite.py -t longevity -d 86400 -v

# Or manual fio script
fio --name=longevity --filename=/dev/nvme0n1 --direct=1 --rw=randrw \
    --bs=4k --iodepth=32 --numjobs=8 --runtime=86400 \
    --output=fio_longevity.txt --log_avg_msec=5000
```

**Monitoring During Test:**
```bash
# Terminal 1: Monitor throughput
while true; do
  iostat -x 1 | grep nvme
done

# Terminal 2: Monitor errors
dmesg -w | grep -i "error\|fail\|aer"

# Terminal 3: Monitor temperatures
watch -n 5 'cat /sys/class/thermal/thermal_zone*/temp'
```

**Expected Results:**
- **Throughput stability:** < 10% peak-to-peak variation
- **Latency tail (p99):** consistent over duration
- **Errors:** < 0.1% of operations (none critical)
- **Temperature:** stable, no throttling
- **Crashes:** 0

**Acceptance Criteria:**
- MTBF: > 1000 hours equivalent
- Throughput degradation: < 5% over duration
- Correctable errors: < 1 per hour
- Uncorrectable errors: 0

---

### Category 8: Telemetry & Validation

#### PCIE6-US-019: Telemetry Source Consistency Verification
**Objective:** Cross-validate telemetry from multiple monitoring sources.

**Prerequisites:**
- All test infrastructure running
- rasdaemon installed (Linux)

**Test Steps:**
```bash
# Collect from multiple sources
# Source 1: lspci
lspci -s 0000:00:14.0 -vvv > telemetry_lspci.txt

# Source 2: sysfs
find /sys/bus/pci/devices/0000:00:14.0 -name "*.bin" -o -name "*.txt" > telemetry_sysfs.txt

# Source 3: rasdaemon
journalctl | grep -i "AER\|RAS" > telemetry_rasdaemon.txt

# Source 4: perf/PMU counters
perf stat -e pcie_read_txn,pcie_write_txn -- sleep 10 > telemetry_perf.txt

# Cross-check
python scripts/validate_telemetry.py --sources lspci sysfs rasdaemon perf
```

**Expected Results:**
- Timestamp correlation: events match across sources (within 1 sec)
- Counter consistency: error counts match or explainable difference
- No missing events
- Monotonic counter increase

**Acceptance Criteria:**
- Source agreement: > 95%
- Counter deviation: < 2%
- Timestamp skew: < 1 second

---

#### PCIE6-US-020: Automated Regression Test Suite
**Objective:** Standardize and automate all tests for CI/CD integration.

**Prerequisites:**
- All individual tests defined
- Test environment documented

**Test Steps:**
```bash
# Run full regression suite
python scripts/pcie6_test_suite.py -a --output json --file results.json

# Parse results
python scripts/parse_results.py results.json --output html > results.html

# Compare with baseline (if available)
python scripts/compare_results.py baseline.json results.json --threshold 0.05
```

**Expected Output:**
- JUnit XML report (for Jenkins/GitLab)
- JSON machine-readable format
- HTML human-readable dashboard
- CSV for data analysis

**Acceptance Criteria:**
- Test execution success: 100%
- Report generation: < 5 seconds
- All tests accounted for: 100%

---

## Verification Matrix

| Test ID | Category | Linux | Windows | Hardware Required | Priority |
|---------|----------|-------|---------|-------------------|----------|
| PCIE6-US-001 | Enumeration | ✓ | ✓ | Any PCIe device | P0 |
| PCIE6-US-002 | Enumeration | ✓ | ✓ | Any PCIe device | P0 |
| PCIE6-US-003 | Link | ✓ | ◐ | Any PCIe device | P0 |
| PCIE6-US-004 | Link | ✓ | ✗ | Root port w/ retrain | P1 |
| PCIE6-US-005 | Config Space | ✓ | ◐ | Any PCIe device | P1 |
| PCIE6-US-006 | BAR | ✓ | ✓ | BAR-capable device | P1 |
| PCIE6-US-007 | Interrupts | ✓ | ◐ | MSI/MSI-X device | P1 |
| PCIE6-US-008 | Bandwidth | ✓ | ✓ | I/O device (NVMe/NIC) | P0 |
| PCIE6-US-009 | Bandwidth | ✓ | ◐ | 2+ I/O devices | P1 |
| PCIE6-US-010 | NUMA | ✓ | ✗ | 2-socket system | P2 |
| PCIE6-US-011 | RAS/AER | ✓ | ◐ | AER-capable device | P1 |
| PCIE6-US-012 | RAS/AER | ✓ | ✗ | AER-capable device | P2 |
| PCIE6-US-013 | RAS/AER | ✓ | ✗ | Lab simulation | P2 |
| PCIE6-US-014 | Hot-Plug | ✓ | ✓ | Hot-plug capable slot | P1 |
| PCIE6-US-015 | SR-IOV | ✓ | ◐ | SR-IOV capable NIC/Disk | P2 |
| PCIE6-US-016 | VFIO/IOMMU | ✓ | ✗ | IOMMU + VFIO | P2 |
| PCIE6-US-017 | Power | ✓ | ◐ | ASPM capable device | P2 |
| PCIE6-US-018 | Longevity | ✓ | ✓ | 72h test window | P0 |
| PCIE6-US-019 | Telemetry | ✓ | ◐ | Monitoring tools | P1 |
| PCIE6-US-020 | Automation | ✓ | ✓ | CI/CD infrastructure | P1 |

**Legend:** ✓ = Fully supported | ◐ = Partially supported | ✗ = Not supported

---

## Acceptance Thresholds

### Overall Pass Criteria
- **P0 Tests:** 100% must PASS
- **P1 Tests:** ≥95% must PASS or SKIP
- **P2 Tests:** ≥80% must PASS or SKIP (if applicable)

### Numeric Metrics
| Metric | Threshold |
|--------|-----------|
| Device discovery success | 100% |
| Link negotiation correct | ≥95% devices |
| Bandwidth efficiency | ≥80% of theoretical max |
| Error-free uptime | ≥99.9% |
| Latency p99 | Within spec or baseline |
| Correctable error rate | <1 per device-hour |
| Uncorrectable errors | 0 (non-fatal acceptable with recovery) |

---

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt
# Linux: sudo apt-get install pciutils dmidecode

# 2. Run full test suite
python scripts/pcie6_test_suite.py -a -v -o json -f test_results.json

# 3. Review report
cat test_results.json | python -m json.tool
```

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "lspci not found" | Install pciutils: `apt-get install pciutils` |
| Permission denied | Run with sudo or configure udev rules |
| AER counters not accessible | Mount debugfs: `mount -t debugfs none /sys/kernel/debug` |
| Device not enumerated | Check BIOS PCIe settings, reseat device |

---

**Document Version:** 1.0  
**Last Updated:** 2026-01-21  
**Maintainer:** PCIe Platform Team
