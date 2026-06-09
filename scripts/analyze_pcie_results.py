#!/usr/bin/env python3
"""
Helper script to validate and analyze PCIe 6.0 test results
"""

import argparse
import json
import sys
from pathlib import Path
from typing import List, Dict, Any
import csv


def load_results(filepath: str) -> Dict[str, Any]:
    """Load JSON test results"""
    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading results: {e}")
        sys.exit(1)


def generate_html_report(results: Dict[str, Any], output_file: str = "results.html") -> None:
    """Generate HTML dashboard from results"""
    
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>PCIe 6.0 Test Results</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; }
            h1 { color: #333; }
            .summary { margin: 20px 0; }
            .summary-box { padding: 10px; margin: 5px; border-radius: 5px; display: inline-block; }
            .pass { background-color: #d4edda; color: #155724; }
            .fail { background-color: #f8d7da; color: #721c24; }
            .warn { background-color: #fff3cd; color: #856404; }
            .skip { background-color: #e2e3e5; color: #383d41; }
            table { width: 100%; border-collapse: collapse; margin-top: 20px; }
            th, td { border: 1px solid #ddd; padding: 10px; text-align: left; }
            th { background-color: #f0f0f0; }
            tr:nth-child(even) { background-color: #f9f9f9; }
        </style>
    </head>
    <body>
        <h1>PCIe 6.0 Test Suite - Results Report</h1>
    """
    
    # Add timestamp
    if "timestamp" in results:
        html_content += f"<p><strong>Timestamp:</strong> {results['timestamp']}</p>"
    
    # Add platform info
    if "platform" in results:
        html_content += f"<p><strong>Platform:</strong> {results['platform']}</p>"
    
    # Calculate summary
    test_results = results.get("results", [])
    pass_count = sum(1 for r in test_results if r.get("status") == "PASS")
    fail_count = sum(1 for r in test_results if r.get("status") == "FAIL")
    warn_count = sum(1 for r in test_results if r.get("status") == "WARN")
    skip_count = sum(1 for r in test_results if r.get("status") == "SKIP")
    
    html_content += f"""
    <div class="summary">
        <div class="summary-box pass">{pass_count} PASS</div>
        <div class="summary-box fail">{fail_count} FAIL</div>
        <div class="summary-box warn">{warn_count} WARN</div>
        <div class="summary-box skip">{skip_count} SKIP</div>
    </div>
    
    <table>
        <tr>
            <th>Test ID</th>
            <th>Title</th>
            <th>Status</th>
            <th>Summary</th>
            <th>Metrics</th>
        </tr>
    """
    
    for result in test_results:
        status_class = result.get("status", "SKIP").lower()
        metrics_str = json.dumps(result.get("metrics", {}), indent=2)
        
        html_content += f"""
        <tr>
            <td>{result.get("test_id", "")}</td>
            <td>{result.get("title", "")}</td>
            <td class="{status_class}">{result.get("status", "")}</td>
            <td>{result.get("summary", "")}</td>
            <td><pre>{metrics_str}</pre></td>
        </tr>
        """
    
    html_content += """
    </table>
    </body>
    </html>
    """
    
    with open(output_file, 'w') as f:
        f.write(html_content)
    
    print(f"HTML report generated: {output_file}")


def compare_results(baseline_file: str, current_file: str, threshold: float = 0.05) -> None:
    """Compare current results against baseline"""
    
    baseline = load_results(baseline_file)
    current = load_results(current_file)
    
    baseline_results = {r["test_id"]: r for r in baseline.get("results", [])}
    current_results = {r["test_id"]: r for r in current.get("results", [])}
    
    print("\n=== Regression Analysis ===")
    
    regressions = []
    improvements = []
    
    for test_id, baseline_result in baseline_results.items():
        if test_id not in current_results:
            print(f"Missing test: {test_id}")
            continue
        
        current_result = current_results[test_id]
        
        # Check status regression
        baseline_status = baseline_result.get("status")
        current_status = current_result.get("status")
        
        if baseline_status == "PASS" and current_status in ["FAIL", "WARN"]:
            regressions.append(f"{test_id}: {baseline_status} -> {current_status}")
        
        if baseline_status in ["FAIL", "WARN"] and current_status == "PASS":
            improvements.append(f"{test_id}: {baseline_status} -> {current_status}")
        
        # Check metric regression
        baseline_metrics = baseline_result.get("metrics", {})
        current_metrics = current_result.get("metrics", {})
        
        for metric_key, baseline_val in baseline_metrics.items():
            if not isinstance(baseline_val, (int, float)):
                continue
            
            if metric_key not in current_metrics:
                continue
            
            current_val = current_metrics[metric_key]
            if not isinstance(current_val, (int, float)):
                continue
            
            # Check relative change
            if baseline_val != 0:
                change = (current_val - baseline_val) / baseline_val
                if abs(change) > threshold:
                    if change < 0:
                        regressions.append(
                            f"{test_id}.{metric_key}: "
                            f"{baseline_val:.2f} -> {current_val:.2f} ({change*100:.1f}%)"
                        )
                    else:
                        improvements.append(
                            f"{test_id}.{metric_key}: "
                            f"{baseline_val:.2f} -> {current_val:.2f} ({change*100:.1f}%)"
                        )
    
    if regressions:
        print(f"\n❌ Regressions ({len(regressions)}):")
        for r in regressions:
            print(f"  - {r}")
    else:
        print("\n✓ No regressions detected")
    
    if improvements:
        print(f"\n✓ Improvements ({len(improvements)}):")
        for i in improvements:
            print(f"  + {i}")
    
    print()


def export_csv(results_file: str, output_file: str = "results.csv") -> None:
    """Export results to CSV"""
    
    results = load_results(results_file)
    test_results = results.get("results", [])
    
    with open(output_file, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=["test_id", "title", "status", "summary", "metrics"])
        writer.writeheader()
        
        for result in test_results:
            writer.writerow({
                "test_id": result.get("test_id"),
                "title": result.get("title"),
                "status": result.get("status"),
                "summary": result.get("summary"),
                "metrics": json.dumps(result.get("metrics", {}))
            })
    
    print(f"CSV export completed: {output_file}")


def print_summary(results_file: str) -> None:
    """Print text summary"""
    
    results = load_results(results_file)
    test_results = results.get("results", [])
    
    pass_count = sum(1 for r in test_results if r.get("status") == "PASS")
    fail_count = sum(1 for r in test_results if r.get("status") == "FAIL")
    warn_count = sum(1 for r in test_results if r.get("status") == "WARN")
    skip_count = sum(1 for r in test_results if r.get("status") == "SKIP")
    
    print(f"\n{'='*70}")
    print("PCIe 6.0 Test Suite - Summary Report")
    print(f"{'='*70}")
    print(f"Timestamp: {results.get('timestamp', 'N/A')}")
    print(f"Platform:  {results.get('platform', 'N/A')}")
    print(f"\nResult Summary:")
    print(f"  ✓ PASS:  {pass_count}")
    print(f"  ✗ FAIL:  {fail_count}")
    print(f"  ! WARN:  {warn_count}")
    print(f"  - SKIP:  {skip_count}")
    print(f"  ─────────────────")
    print(f"  TOTAL:   {len(test_results)}")
    print(f"\nPass Rate: {100*pass_count/len(test_results):.1f}%\n")


def main():
    parser = argparse.ArgumentParser(
        description="PCIe 6.0 Test Results Analyzer"
    )
    parser.add_argument("input", help="Input results JSON file")
    parser.add_argument("--output", default="results.html", help="Output report file")
    parser.add_argument("--format", choices=["html", "csv", "summary"], default="html",
                        help="Output format")
    parser.add_argument("--baseline", help="Baseline JSON for regression analysis")
    parser.add_argument("--threshold", type=float, default=0.05,
                        help="Threshold for regression detection (%% change)")
    
    args = parser.parse_args()
    
    if args.format == "html":
        results = load_results(args.input)
        generate_html_report(results, args.output)
    
    elif args.format == "csv":
        export_csv(args.input, args.output)
    
    elif args.format == "summary":
        print_summary(args.input)
    
    if args.baseline:
        compare_results(args.baseline, args.input, args.threshold)


if __name__ == "__main__":
    main()
