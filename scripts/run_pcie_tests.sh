#!/bin/bash
# PCIe 6.0 Test Suite - Linux Automated Runner
# Usage: ./run_pcie_tests.sh [OPTIONS]
# Options:
#   --duration SECS      Test duration (default: 60)
#   --output DIR         Output directory (default: ./pcie_results)
#   --verbose            Verbose output
#   --all                Run all tests (default)
#   --category {enum|link|caps|intr|telemetry|longevity}
#                        Specific test category
#   --help               Show this help

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT_DIR="${SCRIPT_DIR}/../pcie_results"
DURATION=60
VERBOSE=false
TEST_CATEGORY="all"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_usage() {
    echo "PCIe 6.0 Test Suite - Linux Automated Runner"
    echo ""
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --duration SECS      Test duration in seconds (default: 60)"
    echo "  --output DIR         Output directory (default: ./pcie_results)"
    echo "  --verbose            Enable verbose output"
    echo "  --all                Run all tests (default)"
    echo "  --category CAT       Run specific category (enum|link|caps|intr|telemetry|longevity)"
    echo "  --help               Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                              # Run all tests, 60s duration"
    echo "  $0 --duration 300 --verbose    # Run all tests, 300s duration, verbose"
    echo "  $0 --category enum              # Run only device enumeration"
    echo ""
}

check_requirements() {
    log_info "Checking system requirements..."
    
    # Check if running as root
    if [[ $EUID -ne 0 ]]; then
        log_warn "Not running as root; some tests may fail or produce incomplete results"
        log_warn "Recommended: run with 'sudo'"
    fi
    
    # Check required commands
    local missing_cmds=()
    
    for cmd in python3 lspci; do
        if ! command -v $cmd &> /dev/null; then
            missing_cmds+=("$cmd")
        fi
    done
    
    if [ ${#missing_cmds[@]} -gt 0 ]; then
        log_error "Missing required commands: ${missing_cmds[*]}"
        log_info "On Ubuntu/Debian, run: sudo apt-get install pciutils python3"
        exit 1
    fi
    
    log_info "✓ All requirements met"
}

setup_environment() {
    log_info "Setting up test environment..."
    
    # Create output directory
    mkdir -p "$OUTPUT_DIR/$TIMESTAMP"
    
    # Create Python virtual environment if needed
    if [ ! -d "${SCRIPT_DIR}/../venv" ]; then
        log_info "Creating Python virtual environment..."
        python3 -m venv "${SCRIPT_DIR}/../venv"
        source "${SCRIPT_DIR}/../venv/bin/activate"
        pip install --quiet -r "${SCRIPT_DIR}/../requirements.txt" 2>/dev/null || true
    else
        source "${SCRIPT_DIR}/../venv/bin/activate"
    fi
    
    log_info "✓ Environment ready: $OUTPUT_DIR/$TIMESTAMP"
}

run_tests() {
    log_info "Starting PCIe 6.0 test suite..."
    log_info "Test category: $TEST_CATEGORY"
    log_info "Duration: $DURATION seconds"
    
    local cmd="${SCRIPT_DIR}/pcie6_test_suite.py"
    local output_file="${OUTPUT_DIR}/${TIMESTAMP}/results.json"
    
    if [ ! -f "$cmd" ]; then
        log_error "Test script not found: $cmd"
        exit 1
    fi
    
    # Build command
    local python_cmd="python3 $cmd"
    
    if [ "$TEST_CATEGORY" = "all" ]; then
        python_cmd="$python_cmd -a"
    else
        python_cmd="$python_cmd -t $TEST_CATEGORY"
    fi
    
    python_cmd="$python_cmd -d $DURATION"
    python_cmd="$python_cmd -o json"
    python_cmd="$python_cmd -f $output_file"
    
    if [ "$VERBOSE" = true ]; then
        python_cmd="$python_cmd -v"
    fi
    
    # Run with timing
    log_info "Executing: $python_cmd"
    local start_time=$(date +%s)
    
    if [ "$VERBOSE" = true ]; then
        eval $python_cmd
    else
        eval $python_cmd > /dev/null 2>&1
    fi
    
    local exit_code=$?
    local end_time=$(date +%s)
    local elapsed=$((end_time - start_time))
    
    if [ $exit_code -eq 0 ]; then
        log_info "✓ Tests completed successfully (${elapsed}s)"
        log_info "Results saved to: $output_file"
        return 0
    else
        log_error "Tests failed with exit code: $exit_code"
        return 1
    fi
}

analyze_results() {
    log_info "Analyzing test results..."
    
    local results_file="${OUTPUT_DIR}/${TIMESTAMP}/results.json"
    
    if [ ! -f "$results_file" ]; then
        log_error "Results file not found: $results_file"
        return 1
    fi
    
    # Generate HTML report
    local html_file="${OUTPUT_DIR}/${TIMESTAMP}/report.html"
    python3 "${SCRIPT_DIR}/analyze_pcie_results.py" "$results_file" \
        --format html --output "$html_file" 2>/dev/null || true
    
    if [ -f "$html_file" ]; then
        log_info "✓ HTML report generated: $html_file"
    fi
    
    # Generate CSV export
    local csv_file="${OUTPUT_DIR}/${TIMESTAMP}/results.csv"
    python3 "${SCRIPT_DIR}/analyze_pcie_results.py" "$results_file" \
        --format csv --output "$csv_file" 2>/dev/null || true
    
    if [ -f "$csv_file" ]; then
        log_info "✓ CSV export generated: $csv_file"
    fi
    
    # Print summary
    log_info "Summary:"
    python3 "${SCRIPT_DIR}/analyze_pcie_results.py" "$results_file" \
        --format summary 2>/dev/null || true
}

generate_log() {
    log_info "Generating diagnostic log..."
    
    local logfile="${OUTPUT_DIR}/${TIMESTAMP}/diagnostics.log"
    
    {
        echo "=== PCIe Test Suite - Diagnostic Log ==="
        echo "Timestamp: $(date)"
        echo "Hostname: $(hostname)"
        echo "Kernel: $(uname -r)"
        echo ""
        
        echo "=== lspci Output ==="
        lspci -vvv 2>/dev/null || echo "lspci not available"
        echo ""
        
        echo "=== DMI Info ==="
        dmidecode 2>/dev/null | head -50 || echo "dmidecode not available"
        echo ""
        
        echo "=== /proc/meminfo ==="
        cat /proc/meminfo
        echo ""
        
        echo "=== dmesg (last 100 lines) ==="
        dmesg | tail -100
        
    } > "$logfile"
    
    log_info "✓ Diagnostic log saved: $logfile"
}

cleanup() {
    log_info "Cleanup..."
    
    # Optionally save baseline for regression testing
    if [ -f "${OUTPUT_DIR}/${TIMESTAMP}/results.json" ]; then
        # Note: Don't overwrite baseline automatically; user should do it manually
        log_info "To use this as a baseline for future regression testing:"
        log_info "  cp ${OUTPUT_DIR}/${TIMESTAMP}/results.json baseline.json"
    fi
}

main() {
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --duration)
                DURATION="$2"
                shift 2
                ;;
            --output)
                OUTPUT_DIR="$2"
                shift 2
                ;;
            --verbose)
                VERBOSE=true
                shift
                ;;
            --category)
                TEST_CATEGORY="$2"
                shift 2
                ;;
            --help)
                print_usage
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                print_usage
                exit 1
                ;;
        esac
    done
    
    # Main execution
    log_info "PCIe 6.0 Test Suite - Linux Runner"
    log_info "=========================================="
    
    check_requirements
    setup_environment
    run_tests
    local test_result=$?
    
    analyze_results
    generate_log
    cleanup
    
    # Summary
    echo ""
    log_info "=========================================="
    log_info "Test Results:"
    log_info "  Output Directory: $OUTPUT_DIR/$TIMESTAMP"
    log_info "  Results JSON: ${OUTPUT_DIR}/${TIMESTAMP}/results.json"
    log_info "  HTML Report: ${OUTPUT_DIR}/${TIMESTAMP}/report.html"
    log_info "  CSV Export: ${OUTPUT_DIR}/${TIMESTAMP}/results.csv"
    log_info "  Diagnostics: ${OUTPUT_DIR}/${TIMESTAMP}/diagnostics.log"
    echo ""
    
    if [ $test_result -eq 0 ]; then
        log_info "✓ All tests completed successfully"
        exit 0
    else
        log_error "✗ Some tests failed; check results for details"
        exit 1
    fi
}

# Run main function
main "$@"
