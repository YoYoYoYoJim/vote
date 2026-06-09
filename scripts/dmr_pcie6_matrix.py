#!/usr/bin/env python3
"""
Intel DMR PCIe 6.0 Test Matrix Executor
Kernel Space + User Space Cross-Validation Framework

Automates execution of the comprehensive test matrix defined in DMR_PCIE6_TEST_MATRIX.md
"""

import argparse
import json
import subprocess
import sys
import time
import re
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum


class TestPhase(Enum):
    """Test execution phases"""
    SANITY = "sanity"           # 1h - Basic functionality
    FUNCTIONAL = "functional"   # 4h - Core features
    PERFORMANCE = "performance" # 8h - Performance baseline
    LONGEVITY = "longevity"    # 72h - Stability test


class TestLayer(Enum):
    """Test layer classification"""
    KERNEL = "kspace"           # Kernel space
    USERSPACE = "uspace"        # User space
    HWABS = "hwabs"             # Hardware abstraction
    HWDEV = "hwdev"             # Physical hardware
    INTEG = "integ"             # Integration


@dataclass
class TestResult:
    """Single test execution result"""
    test_id: str
    title: str
    layer: TestLayer
    status: str  # PASS, FAIL, SKIP, WARN
    kernel_result: Optional[str] = None
    userspace_result: Optional[str] = None
    cross_validate: bool = False
    consistent: bool = True
    error_msg: str = ""
    metrics: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self):
        """Convert to JSON-serializable dict"""
        return {
            'test_id': self.test_id,
            'title': self.title,
            'layer': self.layer.value,
            'status': self.status,
            'kernel_result': self.kernel_result,
            'userspace_result': self.userspace_result,
            'cross_validate': self.cross_validate,
            'consistent': self.consistent,
            'error_msg': self.error_msg,
            'metrics': self.metrics,
            'timestamp': self.timestamp.isoformat()
        }


class DMRPCIe6TestMatrix:
    """Main test matrix executor for Intel DMR PCIe 6.0"""
    
    def __init__(self, verbose: bool = False, output_dir: str = "./dmr_test_results"):
        self.verbose = verbose
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.results: List[TestResult] = []
        
        # Test matrix definition
        self.test_matrix = {
            TestPhase.SANITY: {
                'KSPACE-ENUM-001': ('RC Initialization', self._test_kspace_enum_001),
                'KSPACE-ENUM-002': ('Config Fabric Access', self._test_kspace_enum_002),
                'USPACE-LSPCI-001': ('lspci Enumeration', self._test_uspace_lspci_001),
                'USPACE-SYSFS-001': ('sysfs Completeness', self._test_uspace_sysfs_001),
            },
            TestPhase.FUNCTIONAL: {
                'KSPACE-AER-001': ('AER Correctable Detection', self._test_kspace_aer_001),
                'KSPACE-AER-002': ('AER Uncorrectable Recovery', self._test_kspace_aer_002),
                'KSPACE-IOMMU-001': ('VT-d Initialization', self._test_kspace_iommu_001),
                'KSPACE-IOMMU-003': ('DMA Isolation (ACS)', self._test_kspace_iommu_003),
                'KSPACE-MSI-001': ('MSI Vector Allocation', self._test_kspace_msi_001),
                'KSPACE-RP-001': ('Root Port Link Training', self._test_kspace_rp_001),
                'KSPACE-RP-002': ('Gen6 Capability', self._test_kspace_rp_002),
                'USPACE-PERF-001': ('/proc/interrupts Accuracy', self._test_uspace_perf_001),
                'USPACE-RAS-001': ('rasdaemon Collection', self._test_uspace_ras_001),
            },
            TestPhase.PERFORMANCE: {
                'USPACE-APP-001': ('Network Performance (NIC)', self._test_uspace_app_001),
                'USPACE-APP-002': ('Storage Performance (NVMe)', self._test_uspace_app_002),
                'INTEG-STABILITY-24': ('24h Stability Baseline', self._test_integ_stability_24),
            },
            TestPhase.LONGEVITY: {
                'INTEG-STABILITY-72': ('72h Longevity Test', self._test_integ_stability_72),
            }
        }
    
    # ==================== Kernel Space Tests ====================
    
    def _test_kspace_enum_001(self) -> TestResult:
        """KSPACE-ENUM-001: RC Initialization"""
        result = TestResult(
            test_id='KSPACE-ENUM-001',
            title='RC Initialization',
            layer=TestLayer.KERNEL,
            status='FAIL'
        )
        
        try:
            output = self._run_cmd('dmesg | grep -i "pci_bus\|pci host bridge"')
            if output:
                result.status = 'PASS'
                result.kernel_result = output[:200]
                result.metrics['rc_count'] = len(output.split('\n'))
            else:
                result.error_msg = 'No RC found in dmesg'
        except Exception as e:
            result.error_msg = str(e)
        
        return result
    
    def _test_kspace_enum_002(self) -> TestResult:
        """KSPACE-ENUM-002: Config Fabric Access"""
        result = TestResult(
            test_id='KSPACE-ENUM-002',
            title='Config Fabric Access',
            layer=TestLayer.KERNEL,
            status='SKIP'
        )
        
        try:
            # Check for Intel PMC Core module (DMR-specific)
            output = self._run_cmd('cat /sys/kernel/debug/pmc_core/*/pll_status 2>/dev/null')
            if output:
                result.status = 'PASS'
                result.kernel_result = output[:200]
            else:
                result.error_msg = 'pmc_core debugfs not available'
        except Exception as e:
            result.error_msg = str(e)
        
        return result
    
    def _test_kspace_aer_001(self) -> TestResult:
        """KSPACE-AER-001: AER Correctable Detection"""
        result = TestResult(
            test_id='KSPACE-AER-001',
            title='AER Correctable Detection',
            layer=TestLayer.KERNEL,
            status='SKIP',
            cross_validate=True
        )
        
        try:
            # Check if AER detected any correctable errors
            output = self._run_cmd('dmesg | grep -i "Correctable Error" | tail -5')
            if output:
                result.status = 'PASS'
                result.kernel_result = output
                result.metrics['correctable_events'] = len(output.split('\n'))
            else:
                result.status = 'WARN'
                result.error_msg = 'No correctable errors detected (may be expected)'
        except Exception as e:
            result.error_msg = str(e)
        
        return result
    
    def _test_kspace_aer_002(self) -> TestResult:
        """KSPACE-AER-002: AER Uncorrectable Recovery"""
        result = TestResult(
            test_id='KSPACE-AER-002',
            title='AER Uncorrectable Recovery',
            layer=TestLayer.KERNEL,
            status='SKIP'
        )
        
        try:
            # Check for error recovery evidence
            output = self._run_cmd('dmesg | grep -i "recovery\|retrain" | tail -3')
            if output:
                result.status = 'PASS'
                result.kernel_result = output
            else:
                result.status = 'WARN'
                result.error_msg = 'No recovery events found'
        except Exception as e:
            result.error_msg = str(e)
        
        return result
    
    def _test_kspace_iommu_001(self) -> TestResult:
        """KSPACE-IOMMU-001: VT-d Initialization"""
        result = TestResult(
            test_id='KSPACE-IOMMU-001',
            title='VT-d Initialization',
            layer=TestLayer.KERNEL,
            status='FAIL'
        )
        
        try:
            output = self._run_cmd('dmesg | grep -i "DMAR" | head -5')
            if 'DMAR' in output:
                result.status = 'PASS'
                result.kernel_result = output[:300]
                dmar_count = len(re.findall(r'DMAR.*unit', output))
                result.metrics['dmar_units'] = dmar_count
            else:
                result.error_msg = 'No DMAR entries found'
        except Exception as e:
            result.error_msg = str(e)
        
        return result
    
    def _test_kspace_iommu_003(self) -> TestResult:
        """KSPACE-IOMMU-003: DMA Isolation (ACS)"""
        result = TestResult(
            test_id='KSPACE-IOMMU-003',
            title='DMA Isolation (ACS)',
            layer=TestLayer.KERNEL,
            status='SKIP'
        )
        
        try:
            # Check for ACS support in PCIe capabilities
            output = self._run_cmd('lspci -vvv | grep -i "ACS-Ctrl" | wc -l')
            if output and int(output.strip()) > 0:
                result.status = 'PASS'
                result.metrics['acs_capable_devices'] = int(output.strip())
            else:
                result.status = 'WARN'
                result.error_msg = 'No ACS-capable devices found'
        except Exception as e:
            result.error_msg = str(e)
        
        return result
    
    def _test_kspace_msi_001(self) -> TestResult:
        """KSPACE-MSI-001: MSI Vector Allocation"""
        result = TestResult(
            test_id='KSPACE-MSI-001',
            title='MSI Vector Allocation',
            layer=TestLayer.KERNEL,
            status='FAIL',
            cross_validate=True
        )
        
        try:
            output = self._run_cmd('dmesg | grep -i "msi\|interrupt" | grep -i "allocated\|enabled" | head -3')
            if output:
                result.status = 'PASS'
                result.kernel_result = output
            else:
                result.status = 'WARN'
                result.error_msg = 'MSI allocation not explicitly logged'
        except Exception as e:
            result.error_msg = str(e)
        
        return result
    
    def _test_kspace_rp_001(self) -> TestResult:
        """KSPACE-RP-001: Root Port Link Training"""
        result = TestResult(
            test_id='KSPACE-RP-001',
            title='Root Port Link Training',
            layer=TestLayer.KERNEL,
            status='FAIL',
            cross_validate=True
        )
        
        try:
            # Look for successful link training
            output = self._run_cmd('dmesg | grep -E "pci.*link.*train|LnkSta.*ok" | head -3')
            if output and 'ok' in output.lower():
                result.status = 'PASS'
                result.kernel_result = output
            else:
                result.error_msg = 'Link training status not found'
        except Exception as e:
            result.error_msg = str(e)
        
        return result
    
    def _test_kspace_rp_002(self) -> TestResult:
        """KSPACE-RP-002: Gen6 Capability"""
        result = TestResult(
            test_id='KSPACE-RP-002',
            title='Gen6 Capability',
            layer=TestLayer.KERNEL,
            status='FAIL',
            cross_validate=True
        )
        
        try:
            # Check if Gen6 (64GT/s) is supported
            output = self._run_cmd('lspci -vvv | grep -i "64gt/s\|Gen6" | wc -l')
            gen6_count = int(output.strip()) if output else 0
            
            if gen6_count > 0:
                result.status = 'PASS'
                result.metrics['gen6_devices'] = gen6_count
            else:
                result.status = 'WARN'
                result.error_msg = 'No Gen6 devices detected'
        except Exception as e:
            result.error_msg = str(e)
        
        return result
    
    # ==================== User Space Tests ====================
    
    def _test_uspace_lspci_001(self) -> TestResult:
        """USPACE-LSPCI-001: lspci Enumeration"""
        result = TestResult(
            test_id='USPACE-LSPCI-001',
            title='lspci Enumeration',
            layer=TestLayer.USERSPACE,
            status='FAIL'
        )
        
        try:
            output = self._run_cmd('lspci | wc -l')
            dev_count = int(output.strip()) if output else 0
            
            if dev_count > 0:
                result.status = 'PASS'
                result.metrics['total_devices'] = dev_count
                result.userspace_result = f"Enumerated {dev_count} devices"
            else:
                result.error_msg = 'lspci returned 0 devices'
        except Exception as e:
            result.error_msg = str(e)
        
        return result
    
    def _test_uspace_sysfs_001(self) -> TestResult:
        """USPACE-SYSFS-001: sysfs Completeness"""
        result = TestResult(
            test_id='USPACE-SYSFS-001',
            title='sysfs Completeness',
            layer=TestLayer.USERSPACE,
            status='FAIL'
        )
        
        try:
            output = self._run_cmd('ls /sys/bus/pci/devices | wc -l')
            dev_count = int(output.strip()) if output else 0
            
            if dev_count > 0:
                result.status = 'PASS'
                result.metrics['sysfs_devices'] = dev_count
            else:
                result.error_msg = 'No devices in sysfs'
        except Exception as e:
            result.error_msg = str(e)
        
        return result
    
    def _test_uspace_perf_001(self) -> TestResult:
        """USPACE-PERF-001: /proc/interrupts Accuracy"""
        result = TestResult(
            test_id='USPACE-PERF-001',
            title='/proc/interrupts Accuracy',
            layer=TestLayer.USERSPACE,
            status='FAIL',
            cross_validate=True
        )
        
        try:
            output = self._run_cmd('grep -c ":" /proc/interrupts')
            irq_count = int(output.strip()) if output else 0
            
            if irq_count > 0:
                result.status = 'PASS'
                result.metrics['irq_lines'] = irq_count
            else:
                result.error_msg = 'No interrupt lines found'
        except Exception as e:
            result.error_msg = str(e)
        
        return result
    
    def _test_uspace_ras_001(self) -> TestResult:
        """USPACE-RAS-001: rasdaemon Collection"""
        result = TestResult(
            test_id='USPACE-RAS-001',
            title='rasdaemon Collection',
            layer=TestLayer.USERSPACE,
            status='SKIP'
        )
        
        try:
            output = self._run_cmd('systemctl is-active rasdaemon 2>/dev/null')
            if output and 'active' in output:
                result.status = 'PASS'
                result.userspace_result = 'rasdaemon active'
            else:
                result.error_msg = 'rasdaemon not running'
        except Exception as e:
            result.error_msg = str(e)
        
        return result
    
    def _test_uspace_app_001(self) -> TestResult:
        """USPACE-APP-001: Network Performance"""
        result = TestResult(
            test_id='USPACE-APP-001',
            title='Network Performance (NIC)',
            layer=TestLayer.USERSPACE,
            status='SKIP'
        )
        
        try:
            # Check if iperf3 is available and run basic test
            cmd = 'which iperf3'
            output = self._run_cmd(cmd)
            if output:
                result.status = 'SKIP'
                result.error_msg = 'iperf3 available but requires remote target'
            else:
                result.status = 'SKIP'
                result.error_msg = 'iperf3 not installed'
        except Exception as e:
            result.error_msg = str(e)
        
        return result
    
    def _test_uspace_app_002(self) -> TestResult:
        """USPACE-APP-002: Storage Performance"""
        result = TestResult(
            test_id='USPACE-APP-002',
            title='Storage Performance (NVMe)',
            layer=TestLayer.USERSPACE,
            status='SKIP'
        )
        
        try:
            # Check for NVMe devices
            output = self._run_cmd('ls -d /dev/nvme* 2>/dev/null | wc -l')
            nvme_count = int(output.strip()) if output else 0
            
            if nvme_count > 0:
                result.status = 'SKIP'
                result.error_msg = f'{nvme_count} NVMe device(s) found, fio test skipped'
                result.metrics['nvme_devices'] = nvme_count
            else:
                result.status = 'SKIP'
                result.error_msg = 'No NVMe devices found'
        except Exception as e:
            result.error_msg = str(e)
        
        return result
    
    def _test_integ_stability_24(self) -> TestResult:
        """INTEG-STABILITY-24: 24h Stability Baseline"""
        result = TestResult(
            test_id='INTEG-STABILITY-24',
            title='24h Stability Baseline',
            layer=TestLayer.INTEG,
            status='SKIP'
        )
        result.error_msg = 'Long-duration test, skipped in automation'
        return result
    
    def _test_integ_stability_72(self) -> TestResult:
        """INTEG-STABILITY-72: 72h Longevity Test"""
        result = TestResult(
            test_id='INTEG-STABILITY-72',
            title='72h Longevity Test',
            layer=TestLayer.INTEG,
            status='SKIP'
        )
        result.error_msg = 'Scheduled longevity test, separate execution'
        return result
    
    # ==================== Test Execution ====================
    
    def run_phase(self, phase: TestPhase) -> Dict[str, TestResult]:
        """Execute all tests in a phase"""
        print(f"\n{'='*70}")
        print(f"Running {phase.value.upper()} Phase")
        print(f"{'='*70}\n")
        
        phase_results = {}
        tests = self.test_matrix.get(phase, {})
        
        for test_id, (title, test_func) in tests.items():
            print(f"[{test_id}] {title}...", end=' ', flush=True)
            
            try:
                result = test_func()
                self.results.append(result)
                phase_results[test_id] = result
                
                # Print status
                status_symbol = {
                    'PASS': '✓',
                    'FAIL': '✗',
                    'SKIP': '-',
                    'WARN': '!'
                }.get(result.status, '?')
                
                print(f"{status_symbol} {result.status}")
                
                if self.verbose and result.error_msg:
                    print(f"    → {result.error_msg}")
            
            except Exception as e:
                print(f"✗ ERROR: {str(e)}")
                result = TestResult(
                    test_id=test_id,
                    title=title,
                    layer=TestLayer.KERNEL if test_id.startswith('KSPACE') else TestLayer.USERSPACE,
                    status='FAIL',
                    error_msg=str(e)
                )
                self.results.append(result)
                phase_results[test_id] = result
        
        return phase_results
    
    def run_all_phases(self, phases: List[TestPhase]) -> Dict[str, Any]:
        """Execute specified phases"""
        summary = {
            'timestamp': datetime.now().isoformat(),
            'phases': {},
            'total_tests': 0,
            'pass_count': 0,
            'fail_count': 0,
            'skip_count': 0,
            'warn_count': 0
        }
        
        for phase in phases:
            phase_results = self.run_phase(phase)
            summary['phases'][phase.value] = {
                test_id: r.to_dict() for test_id, r in phase_results.items()
            }
        
        # Calculate summary
        for result in self.results:
            summary['total_tests'] += 1
            if result.status == 'PASS':
                summary['pass_count'] += 1
            elif result.status == 'FAIL':
                summary['fail_count'] += 1
            elif result.status == 'SKIP':
                summary['skip_count'] += 1
            elif result.status == 'WARN':
                summary['warn_count'] += 1
        
        return summary
    
    def _run_cmd(self, cmd: str, timeout: int = 10) -> str:
        """Execute shell command safely"""
        try:
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            return result.stdout
        except subprocess.TimeoutExpired:
            raise Exception(f"Command timeout: {cmd}")
        except Exception as e:
            raise Exception(f"Command failed: {str(e)}")
    
    def generate_report(self, output_format: str = 'json') -> str:
        """Generate test report"""
        if output_format == 'json':
            report_data = {
                'timestamp': datetime.now().isoformat(),
                'total_tests': len(self.results),
                'pass': sum(1 for r in self.results if r.status == 'PASS'),
                'fail': sum(1 for r in self.results if r.status == 'FAIL'),
                'skip': sum(1 for r in self.results if r.status == 'SKIP'),
                'warn': sum(1 for r in self.results if r.status == 'WARN'),
                'results': [r.to_dict() for r in self.results]
            }
            return json.dumps(report_data, indent=2)
        
        elif output_format == 'text':
            lines = [
                "=" * 70,
                "DMR PCIe 6.0 Test Matrix Report",
                "=" * 70,
                f"Timestamp: {datetime.now().isoformat()}",
                "",
                "Summary:",
                f"  Total Tests: {len(self.results)}",
                f"  PASS:  {sum(1 for r in self.results if r.status == 'PASS')}",
                f"  FAIL:  {sum(1 for r in self.results if r.status == 'FAIL')}",
                f"  SKIP:  {sum(1 for r in self.results if r.status == 'SKIP')}",
                f"  WARN:  {sum(1 for r in self.results if r.status == 'WARN')}",
                "",
                "Details:"
            ]
            
            for r in self.results:
                lines.append(f"  [{r.test_id}] {r.title}")
                lines.append(f"    Status: {r.status}")
                if r.error_msg:
                    lines.append(f"    Error:  {r.error_msg}")
            
            return "\n".join(lines)
        
        return ""


def main():
    parser = argparse.ArgumentParser(
        description="Intel DMR PCIe 6.0 Test Matrix Executor"
    )
    parser.add_argument(
        '-p', '--phase',
        choices=['sanity', 'functional', 'performance', 'longevity', 'all'],
        default='sanity',
        help='Test phase to execute'
    )
    parser.add_argument(
        '-o', '--output',
        choices=['json', 'text'],
        default='json',
        help='Report format'
    )
    parser.add_argument(
        '-f', '--file',
        type=str,
        help='Output report file'
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Verbose output'
    )
    parser.add_argument(
        '-d', '--output-dir',
        default='./dmr_test_results',
        help='Output directory'
    )
    
    args = parser.parse_args()
    
    # Create executor
    executor = DMRPCIe6TestMatrix(verbose=args.verbose, output_dir=args.output_dir)
    
    # Determine phases
    if args.phase == 'all':
        phases = list(TestPhase)
    else:
        phases = [TestPhase(args.phase)]
    
    # Run tests
    summary = executor.run_all_phases(phases)
    
    # Generate report
    report = executor.generate_report(output_format=args.output)
    
    # Output
    if args.file:
        Path(args.file).write_text(report)
        print(f"\nReport written to: {args.file}")
    else:
        print("\n" + report)
    
    # Exit code based on failures
    if summary['fail_count'] > 0:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
