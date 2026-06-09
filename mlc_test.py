"""
Intel MLC (Memory Latency Checker) Test Script
===============================================
运行 Intel MLC 各项内存性能测试，并解析、展示结果。

用法:
    python mlc_test.py [--mlc MLC_PATH] [--output OUTPUT_DIR]

示例:
    python mlc_test.py --mlc C:\\tools\\mlc\\mlc.exe
    python mlc_test.py --mlc ./mlc --output ./results
"""

import argparse
import datetime
import json
import os
import re
import subprocess
import sys


# ──────────────────────────────────────────────
# 配置
# ──────────────────────────────────────────────
DEFAULT_MLC_PATH = r"C:\tools\mlc\mlc.exe"   # 根据实际路径修改
RESULT_DIR = "mlc_results"


# ──────────────────────────────────────────────
# 工具函数
# ──────────────────────────────────────────────

def run_mlc(mlc_path: str, args: list[str], timeout: int = 300) -> tuple[int, str, str]:
    """执行 MLC 命令，返回 (returncode, stdout, stderr)。"""
    cmd = [mlc_path] + args
    print(f"  >> 命令: {' '.join(cmd)}")
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.returncode, result.stdout, result.stderr
    except FileNotFoundError:
        print(f"[错误] 找不到 MLC 可执行文件: {mlc_path}")
        print("       请通过 --mlc 参数指定正确路径，或从以下地址下载:")
        print("       https://www.intel.com/content/www/us/en/developer/articles/tool/intelr-memory-latency-checker.html")
        sys.exit(1)
    except subprocess.TimeoutExpired:
        print(f"[警告] 命令超时 ({timeout}s): {' '.join(cmd)}")
        return -1, "", "Timeout"


def save_raw(output_dir: str, name: str, text: str):
    """将原始输出保存到文件。"""
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, f"{name}.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"  >> 原始输出已保存: {path}")


def section(title: str):
    bar = "=" * 60
    print(f"\n{bar}")
    print(f"  {title}")
    print(bar)


# ──────────────────────────────────────────────
# 1. 空闲延迟 (Idle Latency)
# ──────────────────────────────────────────────

def parse_idle_latency(output: str) -> dict:
    """解析 --idle_latency 输出，提取每个 NUMA 节点的延迟(ns)。"""
    results = {}
    # 典型行: "		0	83.8"  或带表头后的数据行
    for line in output.splitlines():
        m = re.match(r"^\s*(\d+)\s+([\d.]+)\s*$", line)
        if m:
            node = int(m.group(1))
            latency_ns = float(m.group(2))
            results[f"node_{node}_ns"] = latency_ns
    return results


def test_idle_latency(mlc_path: str, output_dir: str) -> dict:
    section("1. 空闲延迟 (Idle Latency)")
    rc, stdout, stderr = run_mlc(mlc_path, ["--idle_latency"])
    save_raw(output_dir, "idle_latency", stdout + stderr)

    if rc != 0:
        print(f"  [警告] 退出码: {rc}")

    parsed = parse_idle_latency(stdout)
    if parsed:
        print("\n  解析结果:")
        for key, val in sorted(parsed.items()):
            print(f"    {key}: {val} ns")
    else:
        print("  (未能自动解析，请查看原始文件)")
        print(stdout[:500])

    return {"idle_latency": parsed, "raw": stdout}


# ──────────────────────────────────────────────
# 2. 峰值带宽 (Peak Bandwidth)
# ──────────────────────────────────────────────

def parse_peak_bandwidth(output: str) -> dict:
    """解析 --peak_bandwidth 输出，提取各访问模式的带宽(MB/s)。"""
    results = {}
    # 典型行: "ALL Reads        :  85432.3 MB/sec"
    pattern = re.compile(
        r"^(.*?)\s*:\s*([\d.]+)\s*MB/sec", re.IGNORECASE
    )
    for line in output.splitlines():
        m = pattern.match(line.strip())
        if m:
            label = m.group(1).strip().lower().replace(" ", "_")
            bw = float(m.group(2))
            results[f"{label}_MBs"] = bw
    return results


def test_peak_bandwidth(mlc_path: str, output_dir: str) -> dict:
    section("2. 峰值带宽 (Peak Bandwidth)")
    rc, stdout, stderr = run_mlc(mlc_path, ["--peak_bandwidth"])
    save_raw(output_dir, "peak_bandwidth", stdout + stderr)

    if rc != 0:
        print(f"  [警告] 退出码: {rc}")

    parsed = parse_peak_bandwidth(stdout)
    if parsed:
        print("\n  解析结果:")
        for key, val in sorted(parsed.items()):
            print(f"    {key}: {val:.1f} MB/s")
    else:
        print("  (未能自动解析，请查看原始文件)")
        print(stdout[:500])

    return {"peak_bandwidth": parsed, "raw": stdout}


# ──────────────────────────────────────────────
# 3. 带宽-延迟曲线 (Loaded Latency / Bandwidth-Latency Curve)
# ──────────────────────────────────────────────

def parse_loaded_latency(output: str) -> list[dict]:
    """解析 --loaded_latency 输出，返回 (注入延迟, 带宽, 延迟) 列表。"""
    results = []
    # 典型行: "00000	85234.5	 89.3"
    pattern = re.compile(r"(\d+)\s+([\d.]+)\s+([\d.]+)")
    in_data = False
    for line in output.splitlines():
        if re.search(r"Inject\s*Delay|MB/sec|Latency", line, re.IGNORECASE):
            in_data = True
            continue
        if in_data:
            m = pattern.match(line.strip())
            if m:
                results.append({
                    "inject_delay_ns": int(m.group(1)),
                    "bandwidth_MBs": float(m.group(2)),
                    "latency_ns": float(m.group(3)),
                })
    return results


def test_loaded_latency(mlc_path: str, output_dir: str) -> dict:
    section("3. 带宽-延迟曲线 (Loaded Latency)")
    rc, stdout, stderr = run_mlc(mlc_path, ["--loaded_latency"])
    save_raw(output_dir, "loaded_latency", stdout + stderr)

    if rc != 0:
        print(f"  [警告] 退出码: {rc}")

    parsed = parse_loaded_latency(stdout)
    if parsed:
        print(f"\n  解析到 {len(parsed)} 个数据点:")
        print(f"  {'注入延迟(ns)':>14}  {'带宽(MB/s)':>12}  {'访问延迟(ns)':>14}")
        print(f"  {'-'*14}  {'-'*12}  {'-'*14}")
        for row in parsed:
            print(
                f"  {row['inject_delay_ns']:>14}  "
                f"{row['bandwidth_MBs']:>12.1f}  "
                f"{row['latency_ns']:>14.1f}"
            )
    else:
        print("  (未能自动解析，请查看原始文件)")
        print(stdout[:500])

    return {"loaded_latency": parsed, "raw": stdout}


# ──────────────────────────────────────────────
# 4. 跨 NUMA 节点延迟矩阵 (Cross-NUMA Latency)
# ──────────────────────────────────────────────

def parse_latency_matrix(output: str) -> dict:
    """
    解析 --latency_matrix 输出。
    典型输出:
        Numa node
        Numa node	0	1
        0        	83.8	135.2
        1        	135.1	 84.0
    """
    results = {}
    lines = [l for l in output.splitlines() if l.strip()]
    header_idx = None
    header_nodes = []

    for i, line in enumerate(lines):
        # 找到列头行: "Numa node\t0\t1\t..."
        if re.match(r"Numa\s+node\s+\d", line, re.IGNORECASE):
            header_nodes = [int(x) for x in re.findall(r"\d+", line)]
            header_idx = i
            continue

        if header_idx is not None:
            # 数据行: "0\t83.8\t135.2"
            parts = line.strip().split()
            if parts and parts[0].isdigit():
                src = int(parts[0])
                for col_idx, val in enumerate(parts[1:]):
                    if col_idx < len(header_nodes):
                        dst = header_nodes[col_idx]
                        try:
                            results[f"node{src}->node{dst}_ns"] = float(val)
                        except ValueError:
                            pass

    return results


def test_latency_matrix(mlc_path: str, output_dir: str) -> dict:
    section("4. 跨 NUMA 节点延迟矩阵 (Cross-NUMA Latency)")
    rc, stdout, stderr = run_mlc(mlc_path, ["--latency_matrix"])
    save_raw(output_dir, "latency_matrix", stdout + stderr)

    if rc != 0:
        print(f"  [警告] 退出码: {rc}")

    parsed = parse_latency_matrix(stdout)
    if parsed:
        print("\n  解析结果 (ns):")
        for key, val in sorted(parsed.items()):
            print(f"    {key}: {val} ns")
    else:
        print("  (未能自动解析，请查看原始文件)")
        print(stdout[:500])

    return {"latency_matrix": parsed, "raw": stdout}


# ──────────────────────────────────────────────
# 汇总报告
# ──────────────────────────────────────────────

def save_summary(output_dir: str, all_results: dict):
    os.makedirs(output_dir, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    summary_path = os.path.join(output_dir, f"summary_{ts}.json")

    # 只保存结构化数据（去掉 raw 文本）
    clean = {}
    for test_name, data in all_results.items():
        clean[test_name] = {k: v for k, v in data.items() if k != "raw"}

    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(clean, f, indent=2, ensure_ascii=False)

    print(f"\n汇总 JSON 已保存: {summary_path}")


# ──────────────────────────────────────────────
# 主函数
# ──────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Intel MLC 内存性能测试脚本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--mlc",
        default=DEFAULT_MLC_PATH,
        help=f"MLC 可执行文件路径 (默认: {DEFAULT_MLC_PATH})",
    )
    parser.add_argument(
        "--output",
        default=RESULT_DIR,
        help=f"结果输出目录 (默认: {RESULT_DIR})",
    )
    parser.add_argument(
        "--tests",
        nargs="+",
        choices=["idle", "peak", "loaded", "numa"],
        default=["idle", "peak", "loaded", "numa"],
        help="选择运行的测试项目 (默认全部运行)",
    )
    args = parser.parse_args()

    mlc_path = args.mlc
    output_dir = args.output

    print("=" * 60)
    print("  Intel MLC 内存性能测试")
    print(f"  MLC 路径  : {mlc_path}")
    print(f"  输出目录  : {output_dir}")
    print(f"  测试项目  : {', '.join(args.tests)}")
    print(f"  开始时间  : {datetime.datetime.now():%Y-%m-%d %H:%M:%S}")
    print("=" * 60)

    if not os.path.isfile(mlc_path):
        print(f"\n[错误] MLC 可执行文件不存在: {mlc_path}")
        print("       请通过 --mlc 参数指定正确路径。")
        print("       下载地址: https://www.intel.com/content/www/us/en/developer/articles/tool/intelr-memory-latency-checker.html")
        sys.exit(1)

    all_results: dict = {}

    if "idle" in args.tests:
        all_results["idle_latency"] = test_idle_latency(mlc_path, output_dir)

    if "peak" in args.tests:
        all_results["peak_bandwidth"] = test_peak_bandwidth(mlc_path, output_dir)

    if "loaded" in args.tests:
        all_results["loaded_latency"] = test_loaded_latency(mlc_path, output_dir)

    if "numa" in args.tests:
        all_results["latency_matrix"] = test_latency_matrix(mlc_path, output_dir)

    save_summary(output_dir, all_results)

    section("测试完成")
    print(f"  所有结果已保存到目录: {output_dir}")
    print(f"  结束时间: {datetime.datetime.now():%Y-%m-%d %H:%M:%S}\n")


if __name__ == "__main__":
    main()
