# PCIe 6.0 OS User Space Test Suite - Quick Start Guide

## Overview

This test suite validates PCIe 6.0 device functionality in OS user space across Linux and Windows platforms. It includes automated test execution, result analysis, and reporting.

## Prerequisites

### Linux (Recommended for Full Coverage)

```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install -y \
    pciutils \
    dmidecode \
    python3 \
    python3-pip \
    linux-headers-$(uname -r) \
    git

# RHEL/CentOS
sudo yum install -y \
    pciutils \
    dmidecode \
    python3 \
    python3-pip \
    kernel-devel
```

### Windows

1. Windows 10/11 with Admin privileges
2. Python 3.9+
3. Optional: Windows Kits (for DevCon.exe)

### Both Platforms

```bash
# Install Python dependencies
pip install -r requirements.txt
```

## Installation

### 1. Clone or Download

```bash
# If using git
git clone <repository-url>
cd random-number-ui-app

# Or copy scripts to local directory
```

### 2. Setup Python Environment

```bash
# Create virtual environment (optional but recommended)
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt
```

## Quick Start

### Run Full Test Suite

```bash
# Linux - all tests
sudo python3 scripts/pcie6_test_suite.py -a -v -o json -f test_results.json

# Windows - all tests (run as Administrator)
python scripts/pcie6_test_suite.py -a -v -o json -f test_results.json
```

### Run Specific Test Category

```bash
# Device enumeration only
python scripts/pcie6_test_suite.py -t enum -v

# Link status check
python scripts/pcie6_test_suite.py -t link -v

# Interrupt configuration
python scripts/pcie6_test_suite.py -t intr -v

# Capability registers
python scripts/pcie6_test_suite.py -t caps -v

# Telemetry consistency
python scripts/pcie6_test_suite.py -t telemetry -v

# Long-term stability (60 seconds default)
python scripts/pcie6_test_suite.py -t longevity -v -d 60
```

### Generate Reports

```bash
# HTML dashboard
python scripts/analyze_pcie_results.py test_results.json --format html --output report.html

# CSV export for analysis
python scripts/analyze_pcie_results.py test_results.json --format csv --output results.csv

# Text summary
python scripts/analyze_pcie_results.py test_results.json --format summary

# Regression analysis against baseline
python scripts/analyze_pcie_results.py test_results.json \
    --format summary \
    --baseline baseline_results.json \
    --threshold 0.05
```

## Usage Examples

### Example 1: Basic Enumeration Check

```bash
$ python scripts/pcie6_test_suite.py -t enum -v

[✓] PCIE6-US-001: PCIe Device Enumeration & Topology Discovery
    Status: PASS
    Summary: Discovered 8 PCIe device(s)
    Metrics: {"device_count": 8}
    - [0000:00:00.0] 8086:0000 - Host bridge (driver: N/A)
    - [0000:00:14.0] 8086:1234 - USB controller (driver: xhci_pci)
    - [0000:01:00.0] 1234:5678 - Network controller (driver: ixgbe)
```

### Example 2: Comprehensive Testing with Report

```bash
# Run all tests with verbose output
$ sudo python scripts/pcie6_test_suite.py -a -v -o json -f results.json

# Generate HTML report
$ python scripts/analyze_pcie_results.py results.json --format html --output report.html
# Open report.html in browser

# View summary
$ python scripts/analyze_pcie_results.py results.json --format summary
```

### Example 3: Regression Testing

```bash
# First run - establish baseline
$ python scripts/pcie6_test_suite.py -a -o json -f baseline.json

# After code/config changes - compare
$ python scripts/pcie6_test_suite.py -a -o json -f current.json

# Analyze regression
$ python scripts/analyze_pcie_results.py current.json \
    --baseline baseline.json \
    --threshold 0.05
```

## Linux-Specific: Automated Batch Testing

### Using Provided Shell Script

```bash
# Make script executable
chmod +x scripts/run_pcie_tests.sh

# Run with default settings
./scripts/run_pcie_tests.sh

# Run with custom options
./scripts/run_pcie_tests.sh --duration 3600 --output /tmp/pcie_results --verbose
```

### Manual Batch Test

```bash
#!/bin/bash
# Run multiple test iterations with logging

TEST_DIR="/tmp/pcie_tests"
mkdir -p $TEST_DIR

for i in {1..5}; do
  echo "=== Run $i ===" | tee -a $TEST_DIR/batch.log
  
  sudo python3 scripts/pcie6_test_suite.py -a \
    -o json -f $TEST_DIR/run_$i.json 2>&1 | tee -a $TEST_DIR/batch.log
  
  # Analyze
  python3 scripts/analyze_pcie_results.py $TEST_DIR/run_$i.json --format summary
  
  # Wait between runs
  sleep 30
done

# Aggregate results
echo "Aggregating results..."
for i in {1..5}; do
  echo "Run $i:"
  python3 scripts/analyze_pcie_results.py $TEST_DIR/run_$i.json --format summary
done
```

## Command Reference

### Main Test Suite

```bash
python scripts/pcie6_test_suite.py [OPTIONS]

Options:
  -a, --all              Run all tests
  -t, --test {enum|link|caps|intr|longevity|telemetry}
                         Run specific test category
  -o, --output {text|json|csv}
                         Output format (default: text)
  -f, --file FILE        Write report to file
  -v, --verbose          Verbose output
  -d, --duration SECS    Longevity test duration (default: 60)
  -h, --help             Show help
```

### Result Analyzer

```bash
python scripts/analyze_pcie_results.py INPUT [OPTIONS]

Options:
  --output FILE          Output filename
  --format {html|csv|summary}
                         Format (default: html)
  --baseline FILE        Baseline JSON for regression
  --threshold PCT        Regression threshold (default: 0.05)
```

## Interpreting Results

### Status Codes

| Status | Meaning |
|--------|---------|
| ✓ PASS | Test completed successfully, all checks passed |
| ✗ FAIL | Test failed, critical issue detected |
| ! WARN | Test completed but with warnings or degradation |
| - SKIP | Test skipped (unsupported platform/hardware) |

### Metrics Examples

```json
{
  "test_id": "PCIE6-US-001",
  "status": "PASS",
  "metrics": {
    "device_count": 8,
    "unknown_devices": 0
  }
}
```

### Common Issues

| Issue | Solution |
|-------|----------|
| "Permission denied" | Use `sudo` on Linux or Admin mode on Windows |
| "lspci not found" | Install pciutils: `sudo apt-get install pciutils` |
| "No devices found" | Check BIOS settings, reseat devices, verify drivers |
| AER counters not accessible | Mount debugfs: `sudo mount -t debugfs none /sys/kernel/debug` |

## Output Files

After running tests, the following files are generated:

```
test_results.json          # Raw results (JSON format)
report.html               # HTML dashboard
results.csv              # Data for spreadsheet analysis
baseline.json            # Baseline for regression testing
```

## CI/CD Integration

### GitHub Actions Example

```yaml
name: PCIe Test

on: [push, pull_request]

jobs:
  pcie_test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Install dependencies
        run: |
          sudo apt-get install pciutils
          pip install -r requirements.txt
      - name: Run PCIe tests
        run: python scripts/pcie6_test_suite.py -a -o json -f results.json
      - name: Generate report
        run: python scripts/analyze_pcie_results.py results.json --format html
      - name: Upload artifact
        uses: actions/upload-artifact@v2
        with:
          name: pcie-report
          path: report.html
```

### GitLab CI Example

```yaml
pcie_test:
  stage: test
  script:
    - apt-get update && apt-get install -y pciutils
    - pip install -r requirements.txt
    - python scripts/pcie6_test_suite.py -a -o json -f results.json
    - python scripts/analyze_pcie_results.py results.json --format html
  artifacts:
    paths:
      - report.html
      - results.json
```

## Advanced Usage

### Custom Test Sequencing

```python
# Create custom test script
import sys
sys.path.insert(0, 'scripts')
from pcie6_test_suite import PCIeTestSuite, generate_report

suite = PCIeTestSuite(verbose=True)

# Run specific tests in order
suite.discover_devices()
suite.check_capabilities()
suite.check_link_status()
suite.check_interrupt_config()

# Generate report
report = generate_report(suite.results, output_format='json')
print(report)
```

### Extending Test Cases

```python
# Add custom test to suite
class PCIeTestSuite:
    def custom_bandwidth_test(self):
        result = PCIeTestResult(
            test_id="CUSTOM-001",
            title="Custom Bandwidth Test",
            status="PASS",
            summary="Custom metric collection"
        )
        # Your custom logic here
        self.results.append(result)
```

## Performance Benchmarks

Expected results for reference platforms:

| Metric | Gen 4 x16 | Gen 5 x16 | Gen 6 x16 |
|--------|-----------|-----------|-----------|
| Theoretical BW | 7.5 GB/s | 15 GB/s | 30 GB/s |
| Practical BW | ~7.0 GB/s | ~14 GB/s | ~28 GB/s |
| Efficiency | ~93% | ~93% | ~93% |
| Latency p99 | <1 ms | <1 ms | <1 ms |

## Troubleshooting

### Full Diagnostics

```bash
# Collect system information
./scripts/collect_diagnostics.sh  # if available

# Or manually:
echo "=== PCIe Devices ===" > diag.txt
lspci -vvv >> diag.txt

echo "=== DMI Info ===" >> diag.txt
sudo dmidecode | grep -A 20 "System" >> diag.txt

echo "=== Kernel Version ===" >> diag.txt
uname -a >> diag.txt

# Share diag.txt with support team
```

## Getting Help

1. Check [PCIE6_TEST_CASES.md](docs/PCIE6_TEST_CASES.md) for detailed test documentation
2. Review test results JSON for specific error messages
3. Enable verbose output: `-v` flag
4. Check system logs: `dmesg | tail -50` (Linux)

## Support & Feedback

- **Issues:** Report bugs via issue tracker
- **Documentation:** See `docs/PCIE6_TEST_CASES.md`
- **Examples:** Check `scripts/` directory for helper scripts

---

**Version:** 1.0  
**Last Updated:** 2026-01-21  
**Target Platforms:** Linux (Ubuntu 22.04+, RHEL 9+), Windows 10/11
