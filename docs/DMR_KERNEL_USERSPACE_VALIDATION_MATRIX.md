# Intel DMR PCIe 6.0 Kernel/User Space 交叉验证矩阵

## 核心验证表格

| ID | 证据等级 | 测试目标 | Kernel 侧步骤 | User Space 侧步骤 | 通过准则 | 常见失败归因 |
|---|---|---|---|---|---|---|
| **CV-001** | P0 Critical | 设备枚举一致性 | `dmesg \| grep "pci.*: \[RC\]" \| wc -l` 统计 RC 数量 | `lspci \| grep "PCI bridge" \| wc -l` 统计桥数 | Kernel 数量 = User Space 数量 ± 0 | ① Firmware 未初始化某些 RC ② BIOS 选项关闭了设备 ③ 驱动绑定失败 |
| **CV-002** | P0 Critical | 设备总线号一致性 | `cat /proc/bus/pci/devices \| awk '{print $1}' \| cut -d: -f1 \| sort -u` | `lspci -n \| awk '{print $1}' \| cut -d: -f1 \| sort -u` | Bus 编号集合完全一致 | ① BIOS 总线枚举顺序错误 ② 某个 Socket 未被枚举 ③ PCIe port 驱动未加载 |
| **CV-003** | P0 Critical | 链路速度协商一致性 | `dmesg \| grep -i "LnkSta:" \| head -1` 检查 Root Port 链路速度 | `lspci -vvv \| grep -i "LnkSta:" \| head -1` 获取 Link Speed | Kernel dmesg "Speed" = User Space lspci "Speed" | ① 硬件不支持 Gen6 ② Firmware 降速 ③ 电源管理策略限制 ④ 物理连接不良 |
| **CV-004** | P0 Critical | 链路宽度协商一致性 | `dmesg \| grep -i "LnkSta:" \| sed 's/.*Width x//' \| cut -d' ' -f1` | `lspci -vvv \| grep "LnkSta:" \| grep -o "Width x[0-9]*" \| grep -o "[0-9]*"` | Width 值完全一致 | ① 物理连接未满带宽（缺少 PCIe 线） ② 插槽降速 ③ 板级设计限制 |
| **CV-005** | P0 Critical | AER 错误计数一致性 | `cat /sys/kernel/debug/ras/pcidev_mce_errors \| grep "AER" \| wc -l` 或 `journalctl -xe \| grep "AER" \| wc -l` | `rasdaemon -i` 查询数据库中 AER 事件数 `sqlite3 /var/lib/rasdaemon/ras.db "SELECT count(*) FROM mce_record WHERE type='PCI Express Error';"` | Kernel 错误计数 = User Space 数据库计数 ± <5% | ① rasdaemon 未启动 ② 日志轮转丢失事件 ③ MCA MSR 清除时序问题 ④ 驱动上报漏洞 |
| **CV-006** | P0 Critical | 中断向量数一致性 | `cat /proc/interrupts \| grep -E "PCI-MSI|PCI-MSIX" \| wc -l` 统计 MSI 行数 | `lspci -vvv \| grep -i "msi:" \| wc -l` 统计支持 MSI 设备数 | Kernel /proc/interrupts 中 MSI 中断向量数 ≥ User Space 设备 MSI 向量数（多对一可能） | ① 驱动未申请所有可用向量 ② BIOS MSI 配置不完整 ③ 中断控制器初始化失败 ④ 设备驱动版本过旧 |
| **CV-007** | P1 High | 中断处理延迟一致性 | `perf stat -e cycles,instructions "cat /proc/interrupts | wc"` 多次采样，计算平均时延 | `top -b -n 1 \| grep irq` 或 `perf record -a -g -F 99 sleep 10 && perf report` | Kernel 侧平均中断处理时延 ≤ 1ms，User Space 侧观测不到异常长尾延迟 | ① 高优先级任务抢占 ② 系统负载过高 ③ IRQ 线程优先级设置不当 ④ CPU 频率缩放 |
| **CV-008** | P0 Critical | IOMMU 映射表一致性 | `cat /sys/kernel/debug/iommu/intel/domains` 查询域表项数 或 `dmesg \| grep -i "iommu\|dmar" \| head -20` | `lspci -vvv \| grep -i "iommu\|amd-vi" \| wc -l` 统计 VT-d 设备 | Kernel IOMMU 域数量 = User Space 识别的 IOMMU 设备数 ± 合理偏差 | ① IOMMU 驱动未加载 (`intel_iommu=on` 参数缺失) ② Firmware 禁用 VT-d ③ BIOS 配置不完整 |
| **CV-009** | P1 High | SR-IOV 虚拟函数一致性 | `cat /sys/bus/pci/devices/*/sriov_totalvfs` 求和统计总 VF 能力 | `lspci -v \| grep "Virtual" -A 2` 统计虚拟函数数 | Kernel sysfs 总 VF 能力 ≥ User Space lspci 显示的 VF 数 | ① SR-IOV 驱动未加载 ② Firmware 不支持 SR-IOV ③ 物理函数 (PF) 驱动未绑定 |
| **CV-010** | P0 Critical | NUMA 节点亲和性一致性 | `dmesg \| grep -i "NUMA\|node" \| head -10` 检查 NUMA 节点划分 | `numactl -H \| grep "node" \| wc -l` 统计 NUMA 节点数 | Kernel 识别的 NUMA 节点数 = User Space numactl 显示的节点数 | ① NUMA 支持未启用 (`numa=on` 参数缺失) ② Firmware 错误报告节点拓扑 ③ BIOS 选项禁用 NUMA ④ 多 Socket 系统未正确互联 |
| **CV-011** | P2 Medium | 电源管理状态一致性 | `cat /sys/module/pcie_port/parameters/pcie_aspm_policy` 检查 ASPM 策略或 `dmesg \| grep -i "aspm\|l1ss"` | `lspci -vvv \| grep -i "aspm\|l1ss" \| head -5` 统计支持设备数 | Kernel ASPM 配置 与 User Space 支持情况一致（全启用或全禁用） | ① Firmware 禁用 ASPM ② 硬件版本不支持 L1 Substates ③ BIOS 选项冲突 ④ 电源策略过保守 |
| **CV-012** | P1 High | DPC (Downstream Port Containment) 一致性 | `dmesg \| grep -i "dpc" \| head -5` 检查 DPC 状态 | `lspci -vvv \| grep -i "DPC" \| head -3` 统计支持 DPC 的端口 | Kernel DPC 驱动启用的端口数 ≥ User Space 硬件支持数的 80% | ① DPC 驱动未加载 ② Firmware 禁用 DPC ③ 硬件版本过旧（不支持 DPC） |
| **CV-013** | P2 Medium | 热插拔事件同步 | 插入设备，`dmesg \| tail -20 \| grep -i "new.*device\|enabling device"` 统计消息 | 同时监控 `udevadm monitor` 计数 | Kernel dmesg 新设备消息 ≈ User Space udevadm 事件消息（差异 <5%） | ① udev 规则配置不当 ② 热插拔驱动未加载 ③ 物理插槽接触不良 ④ 固件热插拔支持不完整 |
| **CV-014** | P2 Medium | 功能级重置 (FLR) 可靠性 | 执行 FLR：`echo 1 > /sys/bus/pci/devices/<BDF>/reset` 后 `dmesg \| tail -5` 检查是否成功重置 | `lspci -vvv -s <BDF>` 检查设备状态是否恢复为初始值 | FLR 完成后，Kernel 无错误日志，User Space lspci 显示设备恢复为初始配置 | ① 设备不支持 FLR ② 驱动仍持有资源 ③ Firmware 限制 FLR ④ PCIe 物理层问题导致超时 |
| **CV-015** | P2 Medium | RAS (Reliability, Availability, Serviceability) 事件完整性 | 运行压力测试触发错误：`stress-ng --pci 1 --timeout 60s` 后查看 `dmesg \| grep -i "correctable\|recoverable"` 计数 | 同时运行 `rasdaemon` 后台采集：`rasdaemon -i` 查询结果 | Kernel dmesg 上报的可恢复错误数 ≈ User Space rasdaemon 采集数（误差 <10%） | ① rasdaemon 配置不完整 ② 日志系统延迟 ③ MCA 寄存器溢出 ④ 部分错误类型驱动未上报 |
| **CV-016** | P1 High | 配置空间访问一致性 | 读取特定寄存器：`setpci -s <BDF> 0.W` 获取 Vendor/Device ID | `lspci -s <BDF> -x \| head -1` 对比 Vendor/Device ID | Vendor/Device ID 完全一致 | ① PCIe 物理层连接故障 ② 设备未供电 ③ 重复的设备地址 (BAR 冲突) |
| **CV-017** | P2 Medium | 内存映射 I/O (MMIO) 窗口对齐 | `cat /proc/iomem \| grep -i "pci\|root.*mem"` 检查分配的内存窗口 | `lspci -vvv -s <BDF> \| grep "Memory at"` 对比 BAR 分配 | Kernel 分配的 MMIO 窗口基址 = User Space lspci 显示的 BAR 基址（字节对齐） | ① BIOS MMIO 配置不当 ② 内存资源池耗尽 ③ 地址重叠冲突 ④ 设备未响应配置请求 |
| **CV-018** | P1 High | 错误日志翻译一致性 | 配置 AER 上报错误：`setpci -s <RC-BDF> 0xA8.W` 启用 AER，监控 `dmesg` | 使用 `pciscan` 或定制工具解析原始 AER 寄存器值，与 kernel 翻译对比 | Kernel dmesg 中的错误解释 与 User Space 原始寄存器翻译一致（错误类型、严重程度) | ① 驱动 AER 解析代码有 bug ② 错误上报字段误解 ③ 硬件 AER 寄存器格式非标准 |
| **CV-019** | P2 Medium | 链路恢复成功率一致性 | 注入 Link Down 事件，监控 `dmesg \| grep -i "link.*down.*recovery\|recovering link"` 计数恢复次数 | 同时观测 `lspci -vvv` 链路状态变化（多次采样查看 LnkSta） | Kernel 记录的恢复次数 ≈ User Space 观测的链路状态切换次数 / 2 | ① 恢复驱动逻辑不完整 ② 物理连接不稳定 ③ Firmware 恢复支持不足 ④ 超时时间设置不当 |
| **CV-020** | P2 Medium | 性能计数器读数准确性 | 使用 `perf record` 采集 uncore PMU 数据（PCIe 吞吐）：`perf stat -e "uncore_pcu/clockticks/" stress-ng --pci 1 --timeout 10s` | 同时用应用层工具测速：`iperf` 或自定义 PCIe 带宽测试程序 | Kernel perf 统计的吞吐 与 User Space 应用测速结果误差 < 5% | ① 性能计数器未正确配置 ② uncore PMU 驱动问题 ③ 应用测试方法不规范 ④ 系统功耗降频 |
| **CV-021** | P1 High | Poison 错误处理一致性 | 注入 Poison TLP：使用 FPGA 或硬件模拟注入 Poison，监控 `dmesg \| grep -i "poison\|fatal"` | 应用捕获信号并记录错误恢复，对比 Kernel dmesg 错误分类 | Kernel 将 Poison 正确分类为致命错误 (Fatal/Non-Fatal)，User Space 应用能正确捕获异常信号 | ① 硬件不支持 Poison 注入 ② 驱动 Poison 处理逻辑缺陷 ③ 信号传递链断裂 |
| **CV-022** | P1 High | 设备移除通知一致性 | 物理拔出设备，监控 `dmesg \| grep -i "device.*removed\|disabled"` | 同时运行 `udevadm monitor` 捕获移除事件 | Kernel 移除通知时间点 ≈ User Space udevadm 事件时间点（差异 <100ms） | ① 移除检测延迟过长 ② udev 规则未正确配置 ③ 驱动资源释放不及时 ④ 物理连接检测可靠性差 |

---

## 表格使用指南

### 1. **证据等级说明**

| 等级 | 定义 | 失败影响 |
|------|------|--------|
| **P0 Critical** | 系统关键，必须 PASS | 系统无法启动或完全不可用 |
| **P1 High** | 功能重要，优先修复 | 功能不完整，用户可感知 |
| **P2 Medium** | 功能辅助，按需修复 | 性能降低，部分用户受影响 |

### 2. **通过准则解读**

- **绝对一致** (`=`): 两侧数值必须完全相等，差异 = 0
- **容许偏差** (`±X%`): 允许在指定百分比范围内的差异
- **相对关系** (`≥`, `≤`): 满足大小关系即可
- **时间同步** (`<Xms`): 时间差异小于阈值

### 3. **常见失败归因分类**

```
① Firmware/BIOS 层    → 需要更新 BIOS 或 Firmware
② 硬件设计问题       → 硬件替换或板级修复
③ 驱动/内核 Bug      → 提交 kernel patch
④ 物理连接问题       → 重新插拔、检查线缆
⑤ 配置/参数错误      → 调整系统参数、内核参数
```

### 4. **快速诊断流程**

```
测试失败？
  ↓
检查是否属于 P0 Critical？
  ├─ 是 → 需要立即修复（阻塞上线）
  └─ 否 → 继续
  ↓
查表找到对应 CV-ID
  ↓
执行 Kernel 侧步骤 → 记录输出
  ↓
执行 User Space 侧步骤 → 记录输出
  ↓
对比两侧输出结果
  ↓
查看"通过准则"
  ├─ 满足 → PASS，问题解决
  └─ 不满足 → 查看"常见失败归因" → 按序排查
```

---

## 实战案例

### 案例 1: 链路速度不匹配 (CV-003)

**现象:** 系统启动时 lspci 显示 Gen6，但设备实际降速到 Gen5

**诊断步骤:**

```bash
# Step 1: Kernel 侧检查
dmesg | grep -i "LnkSta:" | head -1
# 输出: PCIe: [RC1] LnkSta: Speed 5GT/s (2.5 GT/s)

# Step 2: User Space 侧检查
lspci -vvv | grep -i "LnkSta:" | head -1
# 输出: LnkSta: Speed 5GT/s (compared to 5GT/s)

# 对比: Kernel 显示 5GT, User Space 也显示 5GT → 一致!
# 但问题是都降速了，不是 6GT

# Step 3: 排查原因
# 查看是否 Firmware 限制了速度
# → 进入 BIOS，查看 PCIe 速度设置，可能被设为 Gen5
# → 或硬件环境问题 (线缆、温度、电源)
```

### 案例 2: AER 错误计数不一致 (CV-005)

**现象:** 运行压力测试后，Kernel dmesg 显示 10 条 AER 错误，但 rasdaemon 数据库只有 5 条

**诊断步骤:**

```bash
# Step 1: 检查 rasdaemon 是否运行
ps aux | grep rasdaemon
# 如果未运行 → systemctl start rasdaemon

# Step 2: 检查日志是否丢失
journalctl -xe | grep "rasdaemon\|AER" | wc -l
# 对比与 dmesg 的计数差异

# Step 3: 检查数据库配置
sqlite3 /var/lib/rasdaemon/ras.db ".schema mce_record"
# 查看表结构是否完整

# Step 4: 重新启动并重新采集
systemctl restart rasdaemon
# 重新运行压力测试并对比
```

### 案例 3: IOMMU 映射失败 (CV-008)

**现象:** 某些 PCIe 设备无法进行 DMA，提示 IOMMU 映射失败

**诊断步骤:**

```bash
# Step 1: 检查 IOMMU 驱动是否加载
cat /sys/kernel/debug/iommu/intel/domains
# 如果文件不存在 → IOMMU 未启用

# Step 2: 检查内核启动参数
cat /proc/cmdline | grep intel_iommu
# 如果没有 intel_iommu=on → 需要添加到 GRUB 配置

# Step 3: 重新启动并验证
# 编辑 /etc/default/grub，添加 intel_iommu=on
# 运行 sudo grub-mkconfig -o /boot/grub/grub.cfg
# 重启后再检查
```

---

## 集成测试检查清单

```bash
#!/bin/bash
# dmr_cross_validation_check.sh

echo "=== DMR Kernel/User Space 交叉验证检查清单 ==="

# CV-001: 设备枚举
K_DEV=$(dmesg | grep "pci.*: \[RC\]" | wc -l)
U_DEV=$(lspci | grep "PCI bridge" | wc -l)
echo "CV-001 设备枚举: K=$K_DEV, U=$U_DEV → $([ $K_DEV -eq $U_DEV ] && echo PASS || echo FAIL)"

# CV-003: 链路速度
K_SPEED=$(dmesg | grep -i "LnkSta:" | head -1 | grep -o "Speed [^(]*" | cut -d' ' -f2)
U_SPEED=$(lspci -vvv | grep -i "LnkSta:" | head -1 | grep -o "Speed [^(]*" | cut -d' ' -f2)
echo "CV-003 链路速度: K=$K_SPEED, U=$U_SPEED → $([ "$K_SPEED" = "$U_SPEED" ] && echo PASS || echo FAIL)"

# CV-005: AER 错误计数
K_AER=$(journalctl -xe | grep "AER" | wc -l)
U_AER=$(rasdaemon -i | grep "AER" | wc -l 2>/dev/null || echo 0)
AER_DIFF=$((K_AER - U_AER))
AER_RATIO=$(echo "scale=2; $AER_DIFF / $K_AER * 100" | bc 2>/dev/null || echo 0)
echo "CV-005 AER 错误计数: K=$K_AER, U=$U_AER → $([ $(echo "$AER_RATIO < 5" | bc 2>/dev/null) -eq 1 ] && echo PASS || echo FAIL)"

# CV-010: NUMA 节点
K_NUMA=$(dmesg | grep -i "node" | grep -c "node[0-9]*")
U_NUMA=$(numactl -H | grep "node" | wc -l)
echo "CV-010 NUMA 节点: K=$K_NUMA, U=$U_NUMA → $([ $K_NUMA -eq $U_NUMA ] && echo PASS || echo FAIL)"

echo "=== 检查完毕 ==="
```

---

## 关键指标

| 指标 | 目标值 | 含义 |
|------|--------|------|
| P0 Critical 通过率 | 100% | 所有关键点必须 PASS |
| P1 High 通过率 | ≥90% | 最多允许 1 个 FAIL |
| P2 Medium 通过率 | ≥80% | 最多允许 2 个 FAIL |
| 交叉验证一致性 | ≥95% | Kernel/User Space 数据差异 <5% |
| 整体合格 | PASS | 三个条件同时满足 |

---

**版本:** 1.0  
**更新日期:** 2026-04-21  
**文档所有者:** PCIe Platform Validation Team
