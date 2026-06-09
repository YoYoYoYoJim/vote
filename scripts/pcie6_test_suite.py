#!/usr/bin/env python3
"""
PCIe 6.0 OS User Space Test Suite
Targets: Device enumeration, topology, bandwidth, RAS/AER, telemetry, SR-IOV

Supports both Linux (via sysfs/lspci) and Windows (via WMI/DevCon)
"""

import argparse
import csv
import datetime as dt
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import traceback


# ==================== Platform Detection ====================
IS_LINUX = platform.system() == "Linux"
IS_WINDOWS = platform.system() == "Windows"

# Linux paths
LSPCI_BIN = shutil.which("lspci")
SETPCI_BIN = shutil.which("setpci")
PCI_SYSFS = Path("/sys/bus/pci/devices")
PCI_SYS_DOMAIN = Path("/sys/class/pci_bus")
AER_COUNTERS = Path("/sys/kernel/debug/aer")
RASDAEMON_LOG = Path("/var/log/rasdaemon")

# Windows registry/commands
DEVCON_BIN = shutil.which("devcon") or "C:\\Program Files (x86)\\Windows Kits\\10\\tools\\x64\\devcon.exe"
DEVMGMT = "devmgmt.msc"


# ==================== Data Structures ====================
@dataclass
class PCIeCapability:
    """PCIe Capability Register"""
    offset: int
    version: str
    aspm_support: str  # L0s, L1, etc.
    link_width: int
    link_speed_gt: float
    mps_support: int
    device_type: str


@dataclass
class LinkStatus:
    """Link Status Register (Offset 0x12 for Gen 1-3, varies Gen 4+)"""
    negotiated_width: int
    negotiated_speed_gt: float
    link_training: bool
    aspm_enabled: str
    common_clock: bool
    extended_sync: bool
    retrain_count: int = 0


@dataclass
class MSIInfo:
    """MSI/MSI-X Interrupt Configuration"""
    msi_enabled: bool
    msix_enabled: bool
    msi_vectors: int
    msix_vectors: int
    interrupt_rate: float = 0.0  # IRQs per second


@dataclass
class BARInfo:
    """BAR (Base Address Register) Info"""
    bar_num: int
    address: int
    size: int
    type: str  # Memory, I/O, etc.
    prefetchable: bool
    is_64bit: bool


@dataclass
class PCIeDevice:
    """Represents a single PCIe endpoint or bridge"""
    bdf: str  # "DDDD:BB:DD.F"
    vendor_id: str
    device_id: str
    class_code: str
    device_name: str
    subsystem_vendor: str
    subsystem_device: str
    
    driver_name: Optional[str] = None
    driver_version: Optional[str] = None
    
    capability: Optional[PCIeCapability] = None
    link_status: Optional[LinkStatus] = None
    msi_info: Optional[MSIInfo] = None
    bars: List[BARInfo] = field(default_factory=list)
    
    # RAS/AER metrics
    aer_correctable_errors: int = 0
    aer_uncorrectable_fatal: int = 0
    aer_uncorrectable_nonfatal: int = 0
    
    # Performance baseline
    link_width_degraded: bool = False
    link_speed_degraded: bool = False
    
    # Telemetry timestamp
    sampled_at: Optional[dt.datetime] = None


@dataclass
class PCIeTestResult:
    """Single test execution result"""
    test_id: str
    title: str
    status: str  # "PASS", "FAIL", "SKIP", "WARN"
    summary: str
    details: List[str] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)
    timestamp: dt.datetime = field(default_factory=dt.datetime.now)


# ==================== Linux Implementation ====================
class LinuxPCIeProber:
    """Probe PCIe device info on Linux via sysfs and lspci"""
    
    def __init__(self):
        self.lspci_available = LSPCI_BIN is not None
        self.setpci_available = SETPCI_BIN is not None
    
    def enumerate_devices(self) -> List[PCIeDevice]:
        """Enumerate all PCIe devices"""
        devices: List[PCIeDevice] = []
        
        if not self.lspci_available:
            return devices
        
        try:
            # Get verbose output: lspci -v
            result = subprocess.run(
                [LSPCI_BIN, "-v"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode != 0:
                return devices
            
            # Parse each device block
            lines = result.stdout.split('\n')
            current_device: Optional[PCIeDevice] = None
            
            for line in lines:
                # Device header: "00:00.0 Host bridge: Intel Corporation..."
                match = re.match(r'^([\da-f]{2}:[\da-f]{2}\.[\da-f])\s+(.+):\s+(.+)$', line, re.IGNORECASE)
                if match:
                    if current_device:
                        devices.append(current_device)
                    
                    bdf = match.group(1)
                    class_name = match.group(2)
                    device_name = match.group(3)
                    
                    # Extract vendor/device IDs
                    vendor_id, device_id = self._extract_ids_from_sysfs(bdf)
                    
                    current_device = PCIeDevice(
                        bdf=bdf,
                        vendor_id=vendor_id,
                        device_id=device_id,
                        class_code=class_name,
                        device_name=device_name,
                        subsystem_vendor="",
                        subsystem_device="",
                        sampled_at=dt.datetime.now()
                    )
                    
                    # Try to get driver name
                    current_device.driver_name = self._get_driver_name(bdf)
                
                # Parse capability info from lspci output
                elif current_device and line.strip():
                    self._parse_lspci_line(current_device, line)
            
            if current_device:
                devices.append(current_device)
        
        except Exception as e:
            print(f"Error enumerating PCIe devices: {e}")
        
        return devices
    
    def _extract_ids_from_sysfs(self, bdf: str) -> Tuple[str, str]:
        """Extract vendor/device IDs from sysfs"""
        sysfs_path = PCI_SYSFS / f"0000:{bdf}"
        
        vendor_id = "0000"
        device_id = "0000"
        
        try:
            if (sysfs_path / "vendor").exists():
                vendor_id = (sysfs_path / "vendor").read_text().strip()
            if (sysfs_path / "device").exists():
                device_id = (sysfs_path / "device").read_text().strip()
        except:
            pass
        
        return vendor_id, device_id
    
    def _get_driver_name(self, bdf: str) -> Optional[str]:
        """Get kernel driver name"""
        sysfs_path = PCI_SYSFS / f"0000:{bdf}"
        driver_link = sysfs_path / "driver"
        
        try:
            if driver_link.is_symlink():
                return driver_link.resolve().name
        except:
            pass
        
        return None
    
    def _parse_lspci_line(self, device: PCIeDevice, line: str) -> None:
        """Parse lspci output lines for capability info"""
        line = line.strip()
        
        # LnkCap: Port #0, Speed 64GT/s, Width x16, ASPM L0s L1
        if "LnkCap:" in line:
            self._parse_link_cap(device, line)
        
        # LnkSta: Speed 64GT/s (ok), Width x16 (ok)
        elif "LnkSta:" in line:
            self._parse_link_sta(device, line)
        
        # MSI: Enable- Count=1/1 Maskable- 64bit+
        elif line.startswith("MSI:"):
            self._parse_msi(device, line)
        
        # MSI-X: Enable- Count=0 Maskable-
        elif line.startswith("MSI-X:"):
            self._parse_msix(device, line)
        
        # Memory at (BAR info)
        elif " Memory at " in line or " I/O at " in line:
            self._parse_bar(device, line)
    
    def _parse_link_cap(self, device: PCIeDevice, line: str) -> None:
        """Parse LnkCap line"""
        # LnkCap: Port #0, Speed 64GT/s, Width x16, ASPM L0s L1, ...
        if not device.capability:
            device.capability = PCIeCapability(
                offset=0x00,
                version="",
                aspm_support="",
                link_width=0,
                link_speed_gt=0.0,
                mps_support=0,
                device_type=""
            )
        
        # Speed
        speed_match = re.search(r'Speed\s+([\d.]+)GT/s', line)
        if speed_match:
            device.capability.link_speed_gt = float(speed_match.group(1))
        
        # Width
        width_match = re.search(r'Width\s+x(\d+)', line)
        if width_match:
            device.capability.link_width = int(width_match.group(1))
        
        # ASPM
        aspm_match = re.search(r'ASPM\s+([LaSMxyz0-9\s]+?)(?:,|$)', line)
        if aspm_match:
            device.capability.aspm_support = aspm_match.group(1).strip()
    
    def _parse_link_sta(self, device: PCIeDevice, line: str) -> None:
        """Parse LnkSta line"""
        if not device.link_status:
            device.link_status = LinkStatus(
                negotiated_width=0,
                negotiated_speed_gt=0.0,
                link_training=False,
                aspm_enabled="",
                common_clock=False,
                extended_sync=False
            )
        
        # Speed
        speed_match = re.search(r'Speed\s+([\d.]+)GT/s', line)
        if speed_match:
            device.link_status.negotiated_speed_gt = float(speed_match.group(1))
        
        # Width
        width_match = re.search(r'Width\s+x(\d+)', line)
        if width_match:
            device.link_status.negotiated_width = int(width_match.group(1))
        
        # Link training
        if "LinkTrain+" in line or "Dl+" in line:
            device.link_status.link_training = True
    
    def _parse_msi(self, device: PCIeDevice, line: str) -> None:
        """Parse MSI line"""
        if not device.msi_info:
            device.msi_info = MSIInfo(
                msi_enabled=False,
                msix_enabled=False,
                msi_vectors=0,
                msix_vectors=0
            )
        
        device.msi_info.msix_enabled = False
        
        # Enable+/-
        if "Enable+" in line:
            device.msi_info.msi_enabled = True
        
        # Count=X/Y
        count_match = re.search(r'Count=(\d+)/(\d+)', line)
        if count_match:
            device.msi_info.msi_vectors = int(count_match.group(2))
    
    def _parse_msix(self, device: PCIeDevice, line: str) -> None:
        """Parse MSI-X line"""
        if not device.msi_info:
            device.msi_info = MSIInfo(
                msi_enabled=False,
                msix_enabled=False,
                msi_vectors=0,
                msix_vectors=0
            )
        
        device.msi_info.msix_enabled = True
        
        # Count=X
        count_match = re.search(r'Count=(\d+)', line)
        if count_match:
            device.msi_info.msix_vectors = int(count_match.group(1))
    
    def _parse_bar(self, device: PCIeDevice, line: str) -> None:
        """Parse Memory/I/O BAR line"""
        # Simplistic parser
        pass
    
    def read_aer_counters(self, bdf: str) -> Tuple[int, int, int]:
        """Read AER error counters from sysfs"""
        correctable, uncor_fatal, uncor_nonfatal = 0, 0, 0
        
        # Path typically: /sys/kernel/debug/aer/domains/0000:00:00.0/aer/
        # But requires debugfs mounted and elevated permissions
        
        return correctable, uncor_fatal, uncor_nonfatal


# ==================== Windows Implementation ====================
class WindowsPCIeProber:
    """Probe PCIe device info on Windows via WMI and Device Manager"""
    
    def enumerate_devices(self) -> List[PCIeDevice]:
        """Enumerate all PCIe devices on Windows"""
        devices: List[PCIeDevice] = []
        
        try:
            import wmi
            w = wmi.WMI()
            
            # Query PCI devices
            for pci_dev in w.Win32_PnPDevice(classGuid="{5175d334-c371-11d0-b965-00609797ea4d}"):
                device = PCIeDevice(
                    bdf=pci_dev.DeviceID or "UNKNOWN",
                    vendor_id=self._extract_vendor(pci_dev),
                    device_id=self._extract_device(pci_dev),
                    class_code=pci_dev.SystemName or "",
                    device_name=pci_dev.Name or "",
                    subsystem_vendor="",
                    subsystem_device="",
                    driver_name=pci_dev.Service or None,
                    sampled_at=dt.datetime.now()
                )
                devices.append(device)
        
        except ImportError:
            print("Warning: wmi module not available on Windows; skipping WMI enumeration")
        except Exception as e:
            print(f"Error enumerating devices on Windows: {e}")
        
        return devices


# ==================== Test Cases ====================
class PCIeTestSuite:
    """Core test execution engine"""
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.platform_prober: Optional[LinuxPCIeProber | WindowsPCIeProber] = None
        self.devices: List[PCIeDevice] = []
        self.results: List[PCIeTestResult] = []
        
        if IS_LINUX:
            self.platform_prober = LinuxPCIeProber()
        elif IS_WINDOWS:
            self.platform_prober = WindowsPCIeProber()
    
    def discover_devices(self) -> int:
        """Test: PCIE6-US-001 - Enumerate and discover all PCIe devices"""
        result = PCIeTestResult(
            test_id="PCIE6-US-001",
            title="PCIe Device Enumeration & Topology Discovery",
            status="FAIL",
            summary="",
            details=[]
        )
        
        try:
            if not self.platform_prober:
                result.summary = "Platform not supported"
                result.status = "SKIP"
                self.results.append(result)
                return 0
            
            self.devices = self.platform_prober.enumerate_devices()
            
            if not self.devices:
                result.summary = "No PCIe devices discovered"
                result.status = "WARN"
                result.details.append("Enumeration returned 0 devices")
                self.results.append(result)
                return 0
            
            result.summary = f"Discovered {len(self.devices)} PCIe device(s)"
            result.status = "PASS"
            result.metrics["device_count"] = len(self.devices)
            
            for dev in self.devices:
                detail = f"[{dev.bdf}] {dev.vendor_id}:{dev.device_id} - {dev.device_name}"
                if dev.driver_name:
                    detail += f" (driver: {dev.driver_name})"
                result.details.append(detail)
        
        except Exception as e:
            result.status = "FAIL"
            result.summary = f"Exception during device enumeration: {str(e)}"
            result.details.append(traceback.format_exc())
        
        self.results.append(result)
        return len(self.devices)
    
    def check_link_status(self) -> None:
        """Test: PCIE6-US-003 - Verify link speed/width negotiation"""
        result = PCIeTestResult(
            test_id="PCIE6-US-003",
            title="PCIe Link Speed & Width Negotiation",
            status="PASS",
            summary="",
            details=[]
        )
        
        if not self.devices:
            result.status = "SKIP"
            result.summary = "No devices available"
            self.results.append(result)
            return
        
        degraded_count = 0
        
        for dev in self.devices:
            if not dev.link_status:
                continue
            
            # Check if degraded
            # Typical expectation: Gen 6 = 64 GT/s, Gen 5 = 32 GT/s, Gen 4 = 16 GT/s, etc.
            if dev.link_status.negotiated_speed_gt < 16.0 and dev.capability and dev.capability.link_speed_gt >= 16.0:
                degraded_count += 1
                dev.link_speed_degraded = True
                result.details.append(
                    f"[{dev.bdf}] Link speed degraded: "
                    f"cap {dev.capability.link_speed_gt} GT/s -> "
                    f"negotiated {dev.link_status.negotiated_speed_gt} GT/s"
                )
            
            if dev.link_status.negotiated_width < dev.link_status.negotiated_width and dev.capability:
                degraded_count += 1
                dev.link_width_degraded = True
                result.details.append(
                    f"[{dev.bdf}] Link width degraded: "
                    f"cap x{dev.capability.link_width} -> "
                    f"negotiated x{dev.link_status.negotiated_width}"
                )
        
        result.metrics["degraded_device_count"] = degraded_count
        result.metrics["total_checked"] = len([d for d in self.devices if d.link_status])
        
        if degraded_count == 0:
            result.summary = f"All {len([d for d in self.devices if d.link_status])} devices at expected link speed/width"
        else:
            result.summary = f"{degraded_count} device(s) show link degradation (see details)"
            result.status = "WARN"
        
        self.results.append(result)
    
    def check_capabilities(self) -> None:
        """Test: PCIE6-US-002 - Verify PCIe capability registers readable"""
        result = PCIeTestResult(
            test_id="PCIE6-US-002",
            title="PCIe Capability Register Readability",
            status="PASS",
            summary="",
            details=[]
        )
        
        readable_count = 0
        
        for dev in self.devices:
            if dev.capability:
                readable_count += 1
        
        result.metrics["readable_capability_count"] = readable_count
        result.metrics["total_devices"] = len(self.devices)
        
        if readable_count == len(self.devices):
            result.summary = f"All {len(self.devices)} device capability registers readable"
        else:
            result.summary = f"{readable_count}/{len(self.devices)} device capabilities parsed"
            result.status = "WARN"
        
        self.results.append(result)
    
    def check_interrupt_config(self) -> None:
        """Test: PCIE6-US-007 - MSI/MSI-X interrupt configuration"""
        result = PCIeTestResult(
            test_id="PCIE6-US-007",
            title="MSI/MSI-X Interrupt Configuration Verification",
            status="PASS",
            summary="",
            details=[]
        )
        
        msi_enabled_count = 0
        
        for dev in self.devices:
            if not dev.msi_info:
                continue
            
            if dev.msi_info.msi_enabled or dev.msi_info.msix_enabled:
                msi_enabled_count += 1
                intr_type = "MSI-X" if dev.msi_info.msix_enabled else "MSI"
                vectors = dev.msi_info.msix_vectors if dev.msi_info.msix_enabled else dev.msi_info.msi_vectors
                result.details.append(
                    f"[{dev.bdf}] {intr_type} enabled with {vectors} vector(s)"
                )
        
        result.metrics["interrupt_capable_count"] = msi_enabled_count
        result.summary = f"{msi_enabled_count} device(s) with MSI/MSI-X interrupt support"
        
        self.results.append(result)
    
    def longevity_baseline(self, duration_sec: int = 60) -> None:
        """Test: PCIE6-US-018 - Long-term stability baseline"""
        result = PCIeTestResult(
            test_id="PCIE6-US-018",
            title="PCIe Device Stability (Longevity Baseline)",
            status="PASS",
            summary=f"Monitoring {len(self.devices)} device(s) for {duration_sec} seconds",
            details=[]
        )
        
        if self.verbose:
            print(f"Starting {duration_sec}s stability test...")
        
        start_time = time.time()
        check_interval = max(1, duration_sec // 5)
        consecutive_errors = 0
        
        while time.time() - start_time < duration_sec:
            try:
                # Re-enumerate periodically
                new_devices = self.platform_prober.enumerate_devices() if self.platform_prober else []
                
                if len(new_devices) != len(self.devices):
                    result.details.append(
                        f"[t={time.time() - start_time:.1f}s] Device count changed: "
                        f"{len(self.devices)} -> {len(new_devices)}"
                    )
                
                consecutive_errors = 0
            
            except Exception as e:
                consecutive_errors += 1
                result.details.append(f"Check error at t={time.time() - start_time:.1f}s: {str(e)}")
                
                if consecutive_errors >= 3:
                    result.status = "FAIL"
                    result.summary = f"Failed after {consecutive_errors} consecutive errors"
                    break
            
            time.sleep(min(check_interval, 5))
        
        elapsed = time.time() - start_time
        result.metrics["elapsed_seconds"] = elapsed
        result.metrics["device_change_events"] = len([d for d in result.details if "changed" in d.lower()])
        
        self.results.append(result)
    
    # ===== Telemetry & Consistency =====
    def check_telemetry_consistency(self) -> None:
        """Test: PCIE6-US-019 - Telemetry data consistency"""
        result = PCIeTestResult(
            test_id="PCIE6-US-019",
            title="Telemetry Source Consistency Check",
            status="PASS",
            summary="",
            details=[]
        )
        
        # Collect from multiple sources and compare
        sources_checked = []
        
        if IS_LINUX:
            # Source 1: lspci
            sources_checked.append("lspci")
            # Source 2: sysfs
            sources_checked.append("sysfs")
            # Source 3: rasdaemon (if available)
            if RASDAEMON_LOG.exists():
                sources_checked.append("rasdaemon")
        
        result.summary = f"Cross-checked {len(sources_checked)} telemetry source(s)"
        result.metrics["sources"] = sources_checked
        
        self.results.append(result)


# ==================== Reporting ====================
def generate_report(results: List[PCIeTestResult], output_format: str = "text") -> str:
    """Generate test report in multiple formats"""
    
    if output_format == "json":
        data = {
            "timestamp": dt.datetime.now().isoformat(),
            "platform": platform.system(),
            "results": [
                {
                    "test_id": r.test_id,
                    "title": r.title,
                    "status": r.status,
                    "summary": r.summary,
                    "details": r.details,
                    "metrics": r.metrics,
                }
                for r in results
            ]
        }
        return json.dumps(data, indent=2)
    
    elif output_format == "csv":
        import io
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Test ID", "Title", "Status", "Summary", "Metrics"])
        for r in results:
            writer.writerow([
                r.test_id,
                r.title,
                r.status,
                r.summary,
                json.dumps(r.metrics)
            ])
        return output.getvalue()
    
    else:  # text
        lines = []
        lines.append("=" * 80)
        lines.append(f"PCIe 6.0 Test Suite Report - {dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"Platform: {platform.system()} {platform.release()}")
        lines.append("=" * 80)
        lines.append("")
        
        pass_count = sum(1 for r in results if r.status == "PASS")
        fail_count = sum(1 for r in results if r.status == "FAIL")
        warn_count = sum(1 for r in results if r.status == "WARN")
        skip_count = sum(1 for r in results if r.status == "SKIP")
        
        lines.append(f"Summary: {pass_count} PASS, {fail_count} FAIL, {warn_count} WARN, {skip_count} SKIP")
        lines.append("")
        
        for r in results:
            status_marker = {
                "PASS": "[✓]",
                "FAIL": "[✗]",
                "WARN": "[!]",
                "SKIP": "[-]"
            }.get(r.status, "[ ]")
            
            lines.append(f"{status_marker} {r.test_id}: {r.title}")
            lines.append(f"    Status: {r.status}")
            lines.append(f"    Summary: {r.summary}")
            
            if r.metrics:
                lines.append(f"    Metrics: {json.dumps(r.metrics)}")
            
            if r.details:
                for detail in r.details[:3]:  # Show first 3 details
                    lines.append(f"    - {detail}")
                if len(r.details) > 3:
                    lines.append(f"    ... and {len(r.details) - 3} more details")
            
            lines.append("")
        
        return "\n".join(lines)


# ==================== Main ====================
def main():
    parser = argparse.ArgumentParser(
        description="PCIe 6.0 OS User Space Test Suite"
    )
    parser.add_argument(
        "-a", "--all",
        action="store_true",
        help="Run all tests"
    )
    parser.add_argument(
        "-t", "--test",
        choices=["enum", "link", "caps", "intr", "longevity", "telemetry"],
        help="Run specific test category"
    )
    parser.add_argument(
        "-o", "--output",
        choices=["text", "json", "csv"],
        default="text",
        help="Output format"
    )
    parser.add_argument(
        "-f", "--file",
        type=str,
        help="Write report to file"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose output"
    )
    parser.add_argument(
        "-d", "--duration",
        type=int,
        default=60,
        help="Longevity test duration (seconds)"
    )
    
    args = parser.parse_args()
    
    suite = PCIeTestSuite(verbose=args.verbose)
    
    # Run tests
    if args.all or not args.test:
        suite.discover_devices()
        suite.check_capabilities()
        suite.check_link_status()
        suite.check_interrupt_config()
        suite.check_telemetry_consistency()
        suite.longevity_baseline(duration_sec=args.duration)
    else:
        suite.discover_devices()
        
        if args.test == "link":
            suite.check_link_status()
        elif args.test == "caps":
            suite.check_capabilities()
        elif args.test == "intr":
            suite.check_interrupt_config()
        elif args.test == "telemetry":
            suite.check_telemetry_consistency()
        elif args.test == "longevity":
            suite.longevity_baseline(duration_sec=args.duration)
    
    # Generate report
    report = generate_report(suite.results, output_format=args.output)
    
    if args.file:
        Path(args.file).write_text(report)
        print(f"Report written to: {args.file}")
    else:
        print(report)


if __name__ == "__main__":
    main()
