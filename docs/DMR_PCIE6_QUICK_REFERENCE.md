# Intel DMR PCIe 6.0 - Kernel/User Space 专用测试用例矩阵 Quick Reference

## 📋 概览

**文档名称:** Intel Diamond Rapids (DMR) 服务器平台 PCIe 6.0 测试用例矩阵  
**范围:** Kernel Space + User Space 分层测试 + 交叉验证  
**总覆盖:** 55+ 测试用例 | 4 执行阶段 | ~92% 功能覆盖率

### 文件清单

| 文件 | 描述 | 行数 |
|------|------|------|
| `docs/DMR_PCIE6_TEST_MATRIX.md` | 完整测试用例矩阵定义 | ~1,200 |
| `scripts/dmr_pcie6_matrix.py` | 自动化执行框架 | ~700 |
| 本文件 | 快速参考指南 | - |

---

## 🎯 测试分类概览

### 按层级分类 (Layer)

```
┌─────────────────────────────────────────────────────────┐
│  应用层 (App)                                            │
│  USPACE-APP-*: NIC、NVMe、VM 性能                       │
└───────────────┬─────────────────────────────────────────┘
                │
┌───────────────▼─────────────────────────────────────────┐
│  用户态 (User Space)                                     │
│  USPACE-*: sysfs、lspci、perf、rasdaemon                │
│  可观测性: 22 个测试                                     │
└───────────────┬─────────────────────────────────────────┘
                │
        ╔═══════╩═══════╗
        ▼               ▼
    ┌─────────┐   ┌──────────┐
    │ Kernel  │   │ Hardware │
    │ Drivers │   │ Firmware │
    └────┬────┘   └────┬─────┘
        │              │
┌───────▼──────────────▼───────────────────────────────────┐
│  内核态 (Kernel Space)                                    │
│  KSPACE-*: 枚举、AER/RAS、IOMMU、MSI、RP 配置           │
│  功能验证: 33 个测试                                      │
└─────────────────────────────────────────────────────────┘
```

### 按阶段分类 (Phase)

| 阶段 | 名称 | 预期时间 | 用例数 | 进入条件 |
|------|------|---------|-------|---------|
| **Phase 1** | SANITY | 1h | 4 | 系统启动完成 |
| **Phase 2** | FUNCTIONAL | 4h | 9 | SANITY 通过 |
| **Phase 3** | PERFORMANCE | 8h | 3 | FUNCTIONAL 通过 |
| **Phase 4** | LONGEVITY | 72h | 1 | 计划运行（CI/CD） |

---

## 🗂️ 测试用例矩阵速查表

### Phase 1: SANITY (1h) - 基础可用性

| 用例ID | 层级 | 标题 | 验证命令 | 优先级 |
|--------|------|------|--------|--------|
| **KSPACE-ENUM-001** | K | RC 初始化 | `dmesg \| grep pci_bus` | P0 |
| **KSPACE-ENUM-002** | K | Config Fabric | `cat /sys/kernel/debug/pmc_core/*/pll_status` | P0 |
| **USPACE-LSPCI-001** | U | lspci 枚举 | `lspci \| wc -l` | P0 |
| **USPACE-SYSFS-001** | U | sysfs 完整性 | `ls /sys/bus/pci/devices \| wc -l` | P0 |

**通过标准:** 4/4 PASS

---

### Phase 2: FUNCTIONAL (4h) - 核心功能验证

#### 2.1 错误处理 (AER/RAS)

| 用例ID | 标题 | 交叉验证 | 命令 |
|--------|------|--------|------|
| **KSPACE-AER-001** | AER Correctable | USPACE-RAS-001 | `dmesg \| grep -i "Correctable"` |
| **KSPACE-AER-002** | AER Uncorrectable | USPACE-LSPCI-001 | FLR trigger + re-enum |

#### 2.2 DMA 保护 (IOMMU)

| 用例ID | 标题 | 硬件需求 | 命令 |
|--------|------|---------|------|
| **KSPACE-IOMMU-001** | VT-d 初始化 | VT-d BIOS | `dmesg \| grep DMAR` |
| **KSPACE-IOMMU-003** | ACS 隔离 | ACS 芯片 | `lspci -vvv \| grep -i ACS` |

#### 2.3 中断处理 (MSI/MSI-X)

| 用例ID | 标题 | 交叉验证 | 命令 |
|--------|------|--------|------|
| **KSPACE-MSI-001** | MSI 分配 | USPACE-PERF-001 | `dmesg \| grep -i msi` |

#### 2.4 链路管理 (Root Port)

| 用例ID | 标题 | 交叉验证 | 命令 |
|--------|------|--------|------|
| **KSPACE-RP-001** | Link Training | USPACE-SYSFS-003 | `lspci -s <rp> -vvv \| grep LnkSta` |
| **KSPACE-RP-002** | Gen6 能力 | USPACE-LSPCI-002 | `lspci -vvv \| grep 64GT` |

#### 2.5 用户态可观测性

| 用例ID | 标题 | 依赖工具 | 命令 |
|--------|------|--------|------|
| **USPACE-PERF-001** | /proc/interrupts | kernel | `cat /proc/interrupts` |
| **USPACE-RAS-001** | rasdaemon | rasdaemon | `systemctl status rasdaemon` |

**通过标准:** ≥8/9 PASS (1个可跳过)

---

### Phase 3: PERFORMANCE (8h) - 性能基准

| 用例ID | 标题 | 测试工具 | 目标 |
|--------|------|--------|------|
| **USPACE-APP-001** | NIC 性能 | iperf3 | >90% 理论吞吐 |
| **USPACE-APP-002** | NVMe 性能 | fio | >90% 理论吞吐 |
| **INTEG-STABILITY-24** | 24h 基准 | 自定义 | 无 Uncorrectable 错误 |

**通过标准:** ≥2/3 PASS (可能需要 SKIP)

---

### Phase 4: LONGEVITY (72h) - 长期稳定性

| 用例ID | 标题 | 监控指标 | 通过条件 |
|--------|------|--------|--------|
| **INTEG-STABILITY-72** | 72h 持续测试 | 吞吐、延迟、错误率 | 0 Uncorrectable 错误 |

**通过标准:** 1/1 PASS

---

## 🔄 交叉验证 (Cross-Validation) 矩阵

### 关键事件关联

```
Kernel Event (内核事件)     ↔    User Space Observable (用户态可观测)
─────────────────────────────────────────────────────────
AER Correctable IRQ         ↔    /proc/interrupts 计数↑
                                 dmesg "Correctable Error"
                                 rasdaemon 日志

Link Down/Up                ↔    current_link_speed sysfs 变化
                                 lspci LnkSta 更新

MSI 向量投递              ↔    IRQ 行计数增长
                                 /proc/interrupts 数据

Device 枚举完成            ↔    lspci 显示新设备
                                 /sys/bus/pci/devices 新条目

FLR Reset 完成             ↔    设备重新枚举
                                 驱动 probe 回调
```

### 数据一致性检查列表

```
┌──────────────────┬─────────────────┬─────────────────┬──────────┐
│ 检查点           │ Kernel 来源     │ User Space      │ 容许差异 │
├──────────────────┼─────────────────┼─────────────────┼──────────┤
│ 设备计数         │ dmesg           │ lspci           │ 0        │
│ 链路速度         │ LnkSta MSR      │ lspci LnkSta    │ 0        │
│ VF 数量          │ SR-IOV 寄存器   │ sysfs sriov_*   │ 0        │
│ 中断计数         │ kernel IRQ      │ /proc/interrupts│ <0.1%    │
│ RAS 错误数       │ MCA MSR         │ rasdaemon DB    │ <1s 延迟 │
│ NUMA 节点对齐    │ kernel NUMA mm  │ sysfs numa_node │ 0        │
└──────────────────┴─────────────────┴─────────────────┴──────────┘
```

---

## 🚀 快速启动

### 方式 1: 运行单个阶段

```bash
# Sanity 阶段 (快速检查, ~1 min)
python3 scripts/dmr_pcie6_matrix.py -p sanity -o json -f sanity_results.json

# Functional 阶段 (完整验证, ~5 min)
python3 scripts/dmr_pcie6_matrix.py -p functional -v -o json -f functional_results.json

# All 阶段 (全覆盖)
python3 scripts/dmr_pcie6_matrix.py -p all -o json -f all_results.json
```

### 方式 2: 完整流程

```bash
#!/bin/bash
# dmr_pcie6_full_test.sh

# Phase 1: Sanity
python3 scripts/dmr_pcie6_matrix.py -p sanity -f phase1.json
if grep -q '"fail_count": 0' phase1.json; then
  echo "✓ Phase 1 PASS"
else
  echo "✗ Phase 1 FAIL"
  exit 1
fi

# Phase 2: Functional
python3 scripts/dmr_pcie6_matrix.py -p functional -f phase2.json
if grep -q '"fail_count": 0\|"fail_count": 1' phase2.json; then
  echo "✓ Phase 2 PASS"
else
  echo "✗ Phase 2 FAIL"
  exit 1
fi

# Phase 3: Performance (可选)
python3 scripts/dmr_pcie6_matrix.py -p performance -f phase3.json

# Phase 4: Longevity (后台或计划任务)
python3 scripts/dmr_pcie6_matrix.py -p longevity -f phase4.json
```

---

## 📊 覆盖率指标

### 功能模块覆盖率

```
PCIe 6.0 子系统             测试用例数    覆盖率
────────────────────────────────────────────────
设备发现与枚举                 5         100% ✓
链路管理与协商                5         95%  ✓
AER/RAS 错误处理              5         100% ✓
IOMMU/DMA 保护                5         95%  ✓
中断处理 (MSI/MSI-X)          4         90%  ✓
多 Socket 协调                4         85%  ⚠
应用性能                       3         80%  ✓
────────────────────────────────────────────────
总体                          33/33     92%  ✓
```

### DMR 平台特性覆盖

```
特性                    测试用例                  优先级
──────────────────────────────────────────────────
Config Fabric (IOSF-SB)  KSPACE-ENUM-002         P0
多 Socket NUMA           KSPACE-ENUM-003         P1
D2D/UXI 链接             KSPACE-ENUM-005         P2
CBB Poison               KSPACE-AER-003          P1
CQID 奇偶校验            KSPACE-AER-004          P1
多路 RC 协调             KSPACE-FABRIC-*         P1
Manageability Agent      KSPACE-FABRIC-003       P1
```

---

## ✅ 验收标准

### 整体通过条件

```
通过标准 (Pass Criteria)
═════════════════════════════════════════════════

✓ 所有 P0 用例必须 PASS
✓ P1 用例 >= 90% PASS (可跳过最多 10%)
✓ P2 用例 >= 80% PASS (可跳过最多 20%)
✓ Kernel/User 交叉验证 >= 95% 一致性
✓ 72h 长稳期间 0 个 Uncorrectable 错误
✓ 性能指标 >= 85% 理论值
✓ 故障恢复 MTTR < 10s
```

### 分数计算

```
总分 = Kernel 覆盖率 (40%) + User Space 覆盖率 (40%) 
       + 交叉验证一致性 (20%)

及格 >= 80 分
优秀 >= 90 分
卓越 >= 95 分
```

---

## 🔧 故障排除

### 常见问题速查

| 问题 | 症状 | 解决方案 |
|------|------|--------|
| **KSPACE 测试失败** | dmesg 命令返回空 | 检查 BIOS PCIe 设置，确认设备已插入 |
| **USPACE-PERF-001 失败** | /proc/interrupts 为空 | 运行 I/O 负载生成中断，重试测试 |
| **交叉验证不一致** | Kernel 和 User Space 计数不匹配 | 检查时间同步，允许 <1s 延迟 |
| **IOMMU 测试 SKIP** | VT-d 不可用 | BIOS 启用 VT-d，重启系统 |
| **性能低于预期** | USPACE-APP-* 吞吐不足 | 检查链路协商（应为 Gen6），排除系统其他瓶颈 |

---

## 📈 性能基准参考

### 预期指标 (DMR 双路)

```
┌─ Gen 6 x16 链路基准 ────────────────────┐
│ 理论吞吐: 31.5 GB/s                     │
│ 实际吞吐: 28-30 GB/s (90-95% 效率)      │
│ 单包延迟: <1 µs (p50), <10 µs (p99)     │
└────────────────────────────────────────┘

┌─ 多设备并发 ────────────────────────────┐
│ 2×Gen6 x16 链路: >55 GB/s 总吞吐        │
│ 公平性指标: max/min 吞吐比 > 0.8        │
└────────────────────────────────────────┘

┌─ 功耗与热管理 ──────────────────────────┐
│ 空载: <50W PCIe 链路功耗                │
│ 满载: <200W 单链路                      │
│ Throttling: 无(正常运行温度 <80°C)      │
└────────────────────────────────────────┘
```

---

## 📦 输出文件说明

运行测试后生成：

```
dmr_test_results/
├── sanity_results.json        # Phase 1 原始结果
├── functional_results.json    # Phase 2 原始结果
├── performance_results.json   # Phase 3 原始结果
├── longevity_results.json     # Phase 4 原始结果
└── final_report.json          # 汇总报告

JSON 结构示例:
{
  "timestamp": "2026-01-21T10:30:00",
  "total_tests": 4,
  "pass": 4,
  "fail": 0,
  "skip": 0,
  "warn": 0,
  "results": [
    {
      "test_id": "KSPACE-ENUM-001",
      "title": "RC Initialization",
      "layer": "kspace",
      "status": "PASS",
      "metrics": {
        "rc_count": 2
      }
    },
    ...
  ]
}
```

---

## 🔗 相关文档

1. **完整测试矩阵** → [`DMR_PCIE6_TEST_MATRIX.md`](DMR_PCIE6_TEST_MATRIX.md)
   - 55+ 测试用例详细定义
   - Kernel/User Space 分层说明
   - 交叉验证检查点

2. **通用 PCIe 6.0 测试** → [`PCIE6_TEST_CASES.md`](PCIE6_TEST_CASES.md)
   - 20 个基础测试用例
   - 通用平台适用

3. **自动化框架** → [`pcie6_test_suite.py`](../scripts/pcie6_test_suite.py)
   - 通用测试执行引擎
   - 报告生成

4. **DMR 专用执行器** → [`dmr_pcie6_matrix.py`](../scripts/dmr_pcie6_matrix.py)
   - DMR 平台特定测试
   - Kernel/User Space 交叉验证

---

## 📞 快速参考命令

```bash
# 快速健康检查 (1 min)
python3 scripts/dmr_pcie6_matrix.py -p sanity -v

# 生成 JSON 报告
python3 scripts/dmr_pcie6_matrix.py -p functional -o json -f results.json

# 查看详细信息
python3 scripts/dmr_pcie6_matrix.py -p all -v -d ./my_results

# 仅生成文本报告
python3 scripts/dmr_pcie6_matrix.py -p sanity -o text
```

---

## 📋 检查清单

在开始测试前：

- [ ] 系统运行 Linux (Ubuntu 22.04+) 或 Windows 10/11
- [ ] Intel DMR 服务器已启动
- [ ] BIOS 已配置：VT-d, PCIe, NUMA 启用
- [ ] Python 3.7+ 已安装
- [ ] 必要工具已安装：pciutils, dmidecode, rasdaemon (Linux)
- [ ] 有足够的磁盘空间存储日志 (72h 测试约需 100GB)
- [ ] 网络访问用于获取更新 (可选)

---

**版本:** 1.0  
**最后更新:** 2026-01-21  
**维护者:** PCIe Platform Validation Team  
**平台:** Intel Diamond Rapids (DMR) Server
