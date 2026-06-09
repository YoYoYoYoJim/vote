# Intel DMR 服务器平台 - PCIe 6.0 OS Kernel/User Space 测试用例矩阵

**版本:** 1.0  
**生成日期:** 2026-01-21  
**平台:** Intel Diamond Rapids (DMR) Server  
**覆盖范围:** PCIe 6.0 Endpoint + Root Port + System Fabric Integration

---

## 第一部分：DMR 平台特性映射

### 1.1 硬件架构关键特性

| 特性 | 描述 | Kernel 支持需求 | User Space 可观测 |
|------|------|-----------------|------------------|
| **多路 Socket** | 最多 12 个 socket（DMR-AP）| NUMA 驱动 | numactl, libnuma |
| **Config Fabric** | 统一配置总线 (IOSF-SB) | IOSF 寄存器驱动 | pciutils, sysfs |
| **System IO Stack** | DMR-specific PCIe root complex | ACPI, DMI, firmware | lspci, dmesg |
| **D2D (Die-to-Die)** | UXI/UCIe 链接 (仅 multi-die) | D2D 驱动（可选）| sysfs 监控 |
| **RAS 架构** | CBB MCA, CQID 奇偶校验 | MCA MSR 驱动 | rasdaemon, perf |
| **资源管理** | RDT, Group Bandwidth Control | CAT/MBA 驱动 | resctrl sysfs |
| **性能监控** | Uncore PMU, PMON | perf, PMON 驱动 | perf stat, perf record |
| **远程管理** | IPMI, Telemetry Agent | IPMI 驱动 | ipmitool |
| **Manageability** | DMR telemetry for system health | 平台 MCE/BERT | sysfs, DMI data |

### 1.2 PCIe 6.0 链路拓扑

```
┌─ Socket 0 ──────────────────────┬─ Socket 1 ─────────────────────┐
│ Root Complex (RC)               │ Root Complex (RC)              │
│ ├─ Root Port 0 (x16 Gen6)      │ ├─ Root Port N (x16 Gen6)     │
│ │  └─ Endpoint (NIC/SSD)       │ │  └─ Endpoint (NIC/SSD)      │
│ ├─ Root Port 1 (x16 Gen6)      │ ├─ Root Port N+1 (x16 Gen6)   │
│ │  └─ Switch/Bridge            │ │  └─ Switch/Bridge           │
│ └─ Root Port M (x8 Gen6)       │ └─ Root Port M (x8 Gen6)      │
│                                 │                               │
│ ┌─ Config Fabric ─────────────┐ │ ┌─ Config Fabric ──────────┐ │
│ │ IOSF-SB + Hierarchical PM   │ │ │ IOSF-SB + Hierarchical PM│ │
│ └─────────────────────────────┘ │ └──────────────────────────┘ │
└─────────────────────────────────┴──────────────────────────────┘

↓ (D2D/UXI 链接，仅多 Die 配置)

┌─ In-Package Topology (multi-socket) ─────────────────────────────┐
│ Socket 0 ←─D2D Link─→ Socket 1 ←─D2D Link─→ ... Socket 11      │
└──────────────────────────────────────────────────────────────────┘
```

### 1.3 测试层级模型

```
┌──────────────────── Application Layer ──────────────────┐
│ DPDK / SPDK / OVS / Custom Apps                         │
│ (User Space Test Cases: USPACE-*)                       │
├──────────────────── System Call Interface ──────────────┤
│ open(), mmap(), ioctl(), read(), write()                │
│ (Kernel/User Space Boundary)                            │
├──────────────────── Kernel Driver Layer ───────────────┤
│ PCIe/ACPI Drivers, IOMMU, RAS/AER, Fabric, PMON        │
│ (Kernel Space Test Cases: KSPACE-*)                    │
├──────────────────── Hardware Abstraction ───────────────┤
│ Firmware (UEFI/BIOS), ACPI, Config Fabric              │
│ (Test Cases: HWABS-*)                                  │
├──────────────────── Physical Hardware ───────────────────┤
│ PCIe Endpoints, Root Complex, Uncore Logic              │
│ (Test Cases: HWDEV-*)                                  │
└──────────────────── Cross-Layer Verification ──────────────┘
  (Integration Test Cases: INTEG-*)
```

---

## 第二部分：内核态测试用例 (KSPACE)

### 2.1 PCIe Endpoint 发现与注册

| 用例ID | 标题 | 验证点 | 前置条件 | 检查命令 | 优先级 |
|--------|------|--------|---------|--------|--------|
| **KSPACE-ENUM-001** | Root Complex 初始化 | RC 在 ACPI DSDT 中正确标记 | 系统启动完成 | `dmesg \| grep "pci host bridge"` | P0 |
| **KSPACE-ENUM-002** | DMR Config Fabric 寄存器可访问 | IOSF-SB 总线寄存器可读 | 加载 intel_pmc_core 或类似 | `cat /sys/kernel/debug/pmc_core/*/pll_status` | P0 |
| **KSPACE-ENUM-003** | 多 Socket PCIe 设备联合枚举 | NUMA 节点与 PCIe 设备对齐 | IOMMU/VT-d 启用 | `cat /sys/devices/system/node/node*/distance` | P1 |
| **KSPACE-ENUM-004** | PCIe 设备总线号连续性 | 无总线号冲突，枚举顺序一致 | 热启动 5 次 | `lspci -d ::/0 \| wc -l` (应一致) | P1 |
| **KSPACE-ENUM-005** | D2D 链接设备可见性（多 Die）| 跨 Socket 链接设备可枚举 | multi-die SKU | `cat /sys/devices/virtual/dmi/id/system_sku` | P2 |

### 2.2 AER/RAS 错误上报链

| 用例ID | 标题 | 验证点 | 前置条件 | 检查命令 | 优先级 |
|--------|------|--------|---------|--------|--------|
| **KSPACE-AER-001** | AER Correctable Error Detection | 可纠错错误计数递增，无系统影响 | AER 驱动加载 | `dmesg -w \| grep "Correctable"` | P0 |
| **KSPACE-AER-002** | AER Uncorrectable Non-Fatal 恢复 | 链路重训，设备恢复 | FLR 支持 | `echo 1 > /sys/bus/pci/devices/<BDF>/reset` | P0 |
| **KSPACE-AER-003** | CBB Poison 传播阻止 | 毒化位设置，数据隔离 | RAS 子系统启用 | `journalctl -u rasdaemon -f` (观察事件) | P1 |
| **KSPACE-AER-004** | CQID 端到端奇偶校验 | 奇偶错误上报到 MCA | MCA MSR 寄存器访问 | `msr-tools` 或 `perf` 读 MSR | P1 |
| **KSPACE-AER-005** | MCA/MCE 信号一致性 | CMC (Correctable), FRC (Fatal) 区分 | BERT/BERT 表支持 | `cat /sys/firmware/acpi/table/BERT` | P2 |

### 2.3 IOMMU/DMA 保护

| 用例ID | 标题 | 验证点 | 前置条件 | 检查命令 | 优先级 |
|--------|------|--------|---------|--------|--------|
| **KSPACE-IOMMU-001** | VT-d 初始化完成 | DMAR ACPI 表解析成功 | VT-d BIOS 启用 | `dmesg \| grep "DMAR"` | P0 |
| **KSPACE-IOMMU-002** | IOTLB 一致性 | Set Root Table Entry, 刷新 | VT-d driver 加载 | `cat /sys/kernel/debug/iommu/dmar<X>/regset` | P1 |
| **KSPACE-IOMMU-003** | DMA 隔离验证 (ACS) | 相邻 PCIe 设备无直接 DMA | ACS 硬件支持 | `lspci -vvv \| grep -i "ACS"` | P1 |
| **KSPACE-IOMMU-004** | IOMMU Fault 中断处理 | 非法 DMA 触发中断，设备暂停 | ACS + IOMMU fault 注入 | `dmesg \| grep "DMAR.*fault"` | P1 |
| **KSPACE-IOMMU-005** | 跨 Socket IOMMU 一致性 | 多 RC 的 DMAR 配置一致 | Multi-socket DMR | `dmesg \| grep -c "DMAR"` (应为 socket 数) | P2 |

### 2.4 资源分配与 Root Port 配置

| 用例ID | 标题 | 验证点 | 前置条件 | 检查命令 | 优先级 |
|--------|------|--------|---------|--------|--------|
| **KSPACE-RP-001** | Root Port Link 训练完成 | LnkSta.LinkStatus = "Training" → "OK" | 冷启动完成 | `lspci -s <rp_bdf> -vvv \| grep "LnkSta"` | P0 |
| **KSPACE-RP-002** | Gen 6 能力协商 | LnkCap 显示支持 64 GT/s | Gen6 RC + EP | `setpci -s <rp_bdf> a4.w` (PCIe Cap) | P0 |
| **KSPACE-RP-003** | 带宽分配（Group Bandwidth Control） | 多设备公平分享总线带宽 | RDT/MBA 驱动加载 | `cat /sys/fs/resctrl/info/L3_MON/bandwidth_gran` | P1 |
| **KSPACE-RP-004** | PM/Power Down Entry | L0s/L1 状态跃迁确认 | ASPM 策略 = "powersave" | `cat /sys/module/pcie_aspm/parameters/policy` | P1 |
| **KSPACE-RP-005** | Secondary Bus Reset (SBR) 功能 | Bridge Reset 前后 subordinate 设备状态 | Bridge 支持 SBR | `echo 1 > /sys/bus/pci/devices/<bridge_bdf>/reset` | P2 |

### 2.5 Fabric 与多 Socket 协调

| 用例ID | 标题 | 验证点 | 前置条件 | 检查命令 | 优先级 |
|--------|------|--------|---------|--------|--------|
| **KSPACE-FABRIC-001** | Config Fabric 参与者发现 | Hierarchy PM Message targets 正确 | DMR platform | `cat /proc/interrupts \| grep -i "fabric"` | P0 |
| **KSPACE-FABRIC-002** | IOSF-SB 寄存器一致性 | 读写寄存器跨 socket 时序一致 | intel_pmc_core 驱动 | `cat /sys/kernel/debug/pmc_core/*/pll_cfg` | P1 |
| **KSPACE-FABRIC-003** | Telemetry Agent 通信 | 平台管理消息传递延迟 < 100ms | Management engine | `ping <BMC_IP>` or `ipmitool` | P1 |
| **KSPACE-FABRIC-004** | D2D 链接 RCF 流程（恢复） | 跨 socket 链路失败恢复 | multi-die 配置 | `dmesg \| grep -i "d2d\|uxi"` | P2 |

### 2.6 中断与 MSI/MSI-X

| 用例ID | 标题 | 验证点 | 前置条件 | 检查命令 | 优先级 |
|--------|------|--------|---------|--------|--------|
| **KSPACE-MSI-001** | MSI 向量分配 | 驱动请求向量数 ≤ 可用数 | MSI 驱动支持 | `cat /proc/interrupts \| head -20` | P0 |
| **KSPACE-MSI-002** | MSI-X 表初始化 | MSI-X BAR 映射，表项有效 | MSI-X 设备 | `lspci -s <dev_bdf> -vvv \| grep -A5 "MSI-X"` | P0 |
| **KSPACE-MSI-003** | Interrupt Coalescing（若支持） | 连续中断合并，无延迟异常 | 网卡/SSD 支持 | `ethtool -c <nic_dev>` 或驱动参数 | P1 |
| **KSPACE-MSI-004** | Posted Write Handling | DMA 写后 MSI 触发顺序 | IOMMU fault 测试套件 | 性能计数器测量 | P2 |

### 2.7 驱动与模块加载

| 用例ID | 标题 | 验证点 | 前置条件 | 检查命令 | 优先级 |
|--------|------|--------|---------|--------|--------|
| **KSPACE-DRV-001** | PCIe 驱动匹配与探测 | 所有设备都有合适驱动 | 驱动已安装 | `lspci -v \| grep -v "Kernel driver"` (应为 0) | P0 |
| **KSPACE-DRV-002** | 驱动版本与 DMR BIOS 兼容性 | 驱动日志无 warning/error | 最新驱动 + BIOS | `dmesg \| grep -i "warn\|error"` | P1 |
| **KSPACE-DRV-003** | 热插拔驱动回调 | pci_driver.probe/remove 调用正确 | 热插拔设备 | `echo 1 > /sys/bus/pci/devices/<bdf>/remove` | P1 |

---

## 第三部分：用户态测试用例 (USPACE)

### 3.1 设备访问与 sysfs 接口

| 用例ID | 标题 | 验证点 | 前置条件 | 检查命令 | 优先级 |
|--------|------|--------|---------|--------|--------|
| **USPACE-SYSFS-001** | PCIe 设备 sysfs 视图完整性 | 所有必需属性可读 | 设备加载 | `ls -la /sys/bus/pci/devices/<bdf>/` | P0 |
| **USPACE-SYSFS-002** | BAR 映射一致性 | /sys/.../resource 与 lspci 对齐 | 读权限 | `cat /sys/bus/pci/devices/<bdf>/resource` | P0 |
| **USPACE-SYSFS-003** | 链路状态实时更新 | current_link_speed/width 动态反映 | 链路变化触发 | 空载和满载下多次读取 | P1 |
| **USPACE-SYSFS-004** | SR-IOV VF 创建/销毁 | sriov_numvfs 写入生效 | SR-IOV 设备 | `echo 4 > /sys/bus/pci/devices/<pf>/sriov_numvfs` | P1 |
| **USPACE-SYSFS-005** | NUMA 节点亲和性 | /sys/.../numa_node 正确标记 | NUMA 系统 | `cat /sys/devices/pci*/*/numa_node` | P2 |

### 3.2 lspci 与 pciutils

| 用例ID | 标题 | 验证点 | 前置条件 | 检查命令 | 优先级 |
|--------|------|--------|---------|--------|--------|
| **USPACE-LSPCI-001** | lspci 枚举与拓扑显示 | 完整树状拓扑，无遗漏 | pciutils 安装 | `lspci -tv` | P0 |
| **USPACE-LSPCI-002** | Capability 解析完整性 | 所有 PCIe capabilities 显示 | lspci -vvv 运行 | `lspci -s <bdf> -vvv \| grep -c "Capabilities:"` | P0 |
| **USPACE-LSPCI-003** | setpci 配置空间读写 | 可写字段修改生效，只读保护 | root 权限 | `setpci -s <bdf> COMMAND.w=0x0147` | P1 |
| **USPACE-LSPCI-004** | Gen 6 Link 速度显示 | LnkCap/LnkSta 正确解析 Gen6 (64GT/s) | Gen6 设备 | `lspci -s <gen6_bdf> -vvv \| grep "64GT"` | P1 |

### 3.3 中断与性能计数器观测

| 用例ID | 标题 | 验证点 | 前置条件 | 检查命令 | 优先级 |
|--------|------|--------|---------|--------|--------|
| **USPACE-PERF-001** | /proc/interrupts 计数正确性 | 中断计数单调递增 | I/O 负载 | `cat /proc/interrupts \| grep <vector>` | P0 |
| **USPACE-PERF-002** | perf 采集 PCIe 事件 | 读/写事务计数 | perf_event_open() 支持 | `perf stat -e uncore_pcu/event=0x3f,umask=0x04/` | P1 |
| **USPACE-PERF-003** | Uncore PMU 事件定义 | DMR-specific 事件 JSON 解析 | perf list 显示 | `perf list \| grep -i "uncore"` | P1 |
| **USPACE-PERF-004** | rasdaemon 日志记录 | AER 事件写入 syslog/journal | rasdaemon 运行 | `journalctl -u rasdaemon -n 10` | P1 |

### 3.4 用户态 I/O 与 DMA

| 用例ID | 标题 | 验证点 | 前置条件 | 检查命令 | 优先级 |
|--------|------|--------|---------|--------|--------|
| **USPACE-UIO-001** | VFIO-PCI 设备绑定 | 设备成功绑定到 vfio-pci | vfio 驱动加载 | `echo <vendor>:<device> > /sys/bus/pci/drivers/vfio-pci/new_id` | P1 |
| **USPACE-UIO-002** | VFIO mmap 用户空间 DMA | 应用可读写设备 BAR | VFIO-PCI 绑定 | libvfio 测试应用 | P1 |
| **USPACE-UIO-003** | 用户态驱动（UIO）性能 | 吞吐量与核心驱动对标 | UIO 驱动模块 | 对标 fio/iperf 结果 | P2 |
| **USPACE-UIO-004** | DPDK/SPDK 集成 | PMD 驱动正确初始化 | DPDK 编译/安装 | `dpdk-devbind.py -s` 显示端口 | P2 |

### 3.5 RAS 事件观测

| 用espace ID | 标题 | 验证点 | 前置条件 | 检查命令 | 优先级 |
|--------|------|--------|---------|--------|--------|
| **USPACE-RAS-001** | rasdaemon 事件收集 | AER/MCA 事件持久化 | rasdaemon 服务运行 | `systemctl status rasdaemon` | P0 |
| **USPACE-RAS-002** | sysfs RAS counters 读取 | /sys/devices/system/edac/*/ce_count | EDAC 模块加载 | `cat /sys/devices/system/edac/*/ce_count` | P1 |
| **USPACE-RAS-003** | RAS 事件通知 (netlink) | 应用可订阅 RAS 事件 | netlink 套接字 | 自定义应用测试 | P2 |

### 3.6 带宽与 QoS 观测

| 用例ID | 标题 | 验证点 | 前置条件 | 检查命令 | 优先级 |
|--------|------|--------|---------|--------|--------|
| **USPACE-QOS-001** | RDT (CAT/MBA) 配置 | resctrl 挂载，COS 分配 | resctrl 文件系统 | `mount \| grep resctrl` | P1 |
| **USPACE-QOS-002** | 带宽监控（如支持） | Group Bandwidth 计数器读取 | Intel RDT 硬件支持 | `cat /sys/fs/resctrl/mon_data/*/mbm_total_bytes` | P2 |
| **USPACE-QOS-003** | CPU 与 PCIe 链路亲和性 | 就近 CPU 的 I/O 性能优于远程 | NUMA 系统 | numactl 约束下的 fio 性能对标 | P2 |

### 3.7 应用层集成

| 用例ID | 标题 | 验证点 | 前置条件 | 检查命令 | 优先级 |
|--------|------|--------|---------|--------|--------|
| **USPACE-APP-001** | 网络栈性能 (NIC) | 单包延迟、吞吐量基准 | 网卡驱动 + iperf3 | `iperf3 -c <remote> -t 10` | P1 |
| **USPACE-APP-002** | 存储栈性能 (NVMe) | IOPS、带宽基准 | NVMe 驱动 + fio | `fio --name=seq_read --filename=/dev/nvme0n1 ...` | P1 |
| **USPACE-APP-003** | 虚拟化性能 (if VM) | VM PCIe 透传延迟 | KVM + VFIO | qemu 配置 + 性能测试 | P2 |

---

## 第四部分：Kernel/User Space 交叉验证矩阵

### 4.1 事件关联表

| Kernel 事件 | User Space 可观测指标 | 验证方法 | 测试用例组 |
|-----------|--------|--------|----------|
| AER Correctable Error IRQ | /proc/interrupts 计数 ↑ | dmesg + cat /proc/interrupts | KSPACE-AER-001 + USPACE-PERF-001 |
| Uncorrectable Error Recovery | Device re-enumerate in lspci | FLR trigger + 2s 后 lspci -s <bdf> | KSPACE-AER-002 + USPACE-LSPCI-001 |
| Link Down/Up | current_link_speed sysfs 变化 | 写 sysfs + 读取状态变化 | KSPACE-RP-001 + USPACE-SYSFS-003 |
| MSI Vector Delivery | IRQ 行计数增长 | Load trigger + /proc/interrupts delta | KSPACE-MSI-002 + USPACE-PERF-001 |
| IOMMU Fault | dmesg "DMAR.*fault" + device disable | 注入坏 DMA 地址 | KSPACE-IOMMU-004 + USPACE-PERF-003 |
| Power Down (L1.x entry) | Link speed degrades in lspci | Idle 60s + lspci 读取 | KSPACE-RP-004 + USPACE-SYSFS-003 |

### 4.2 数据一致性检查列表

| 检查点 | Kernel 来源 | User Space 来源 | 容许差异 | 用例关联 |
|--------|-----------|----------------|--------|---------|
| 设备计数 | dmesg "pci_bus" | lspci 设备数 | 0 | KSPACE-ENUM-001,004 |
| 链路速度 | LnkSta.Speed MSR | lspci LnkSta | 0 (same) | KSPACE-RP-002 + USPACE-LSPCI-004 |
| VF 数量 | SR-IOV 寄存器 | /sys/bus/pci/.../sriov_numvfs | 0 | KSPACE-RP-003 + USPACE-SYSFS-004 |
| 中断计数 | kernel IRQ 统计 | /proc/interrupts | <0.1% 偏差 | KSPACE-MSI-001 + USPACE-PERF-001 |
| NUMA 节点 | kernel mm/numa | /sys/.../numa_node | 0 | KSPACE-ENUM-003 + USPACE-SYSFS-005 |
| RAS 错误数 | MCA MSR | rasdaemon DB | <1s 延迟 | KSPACE-AER-001 + USPACE-RAS-001 |

---

## 第五部分：硬件与固件测试 (HWABS, HWDEV)

### 5.1 固件 / BIOS 接口

| 用例ID | 标题 | 验证点 | 检查方式 | 优先级 |
|--------|------|--------|--------|--------|
| **HWABS-ACPI-001** | ACPI DSDT PCIe Root 定义 | RC 设备对象存在且类型正确 | ACPI table dump / dmidecode | P0 |
| **HWABS-ACPI-002** | DMAR (IOMMU) 表完整性 | DMAR 条目数与硬件 socket 数一致 | `acpidump \| grep -A20 "DMAR"` | P1 |
| **HWABS-ACPI-003** | BERT (Boot Error Record) 表 | 冷启动期间错误被正确记录 | `hexdump /sys/firmware/acpi/table/BERT` | P1 |
| **HWABS-DMI-001** | DMI 系统信息完整性 | SKU、Serial、Asset Tag 存在 | `dmidecode -t system` | P0 |
| **HWABS-TPM-001** | 配置寄存器安全性 | 部分配置寄存器被 TPM 保护 | 尝试写入保护区域 | P2 |

### 5.2 PCIe 物理层

| 用例ID | 标题 | 验证点 | 测试设备 | 优先级 |
|--------|------|--------|--------|--------|
| **HWDEV-GEN6-001** | Gen 6 链路训练成功 | 链路进入 L0 并保持稳定 | Gen6 EP + RC | P0 |
| **HWDEV-GEN6-002** | 64 GT/s 速率验证 | 实测吞吐量与理论值接近 (>90%) | 已训练 Gen6 链路 | P0 |
| **HWDEV-LT-001** | 链路训练超时机制 | 150ms 内成功或失败，无挂起 | 故障注入环境 | P1 |
| **HWDEV-PW-001** | 功率管理状态迁移 | L0s ↔ L1 ↔ L0 转换 <50ms | 示波器 + 功率计 | P2 |

---

## 第六部分：集成测试矩阵 (INTEG)

### 6.1 冷启动 (Cold Boot) 流程

| 步骤 | 验证点 | Kernel 输出 | User Space 输出 | 预期结果 | 优先级 |
|------|--------|-----------|----------------|--------|--------|
| 1. BIOS/UEFI | RC 枚举 | `dmesg \| grep "pci_bus"` | lspci -c 显示完整树 | 100% 设备可见 | P0 |
| 2. 驱动加载 | 所有驱动 probe 成功 | `dmesg \| grep -i "probe"` 无 error | `lsmod` 显示加载 | 0 个 Failed probes | P0 |
| 3. 中断处理 | MSI 向量分配 | `dmesg \| grep "msi"` | `cat /proc/interrupts \| head` | 向量计数 > 设备数 | P0 |
| 4. RAS 初始化 | MCA 能力检测 | `dmesg \| grep "MCA"` | rasdaemon 启动无 error | rasdaemon status = running | P0 |
| 5. 平台服务 | Manageability Agent | `dmesg \| grep "BMC\|ipmi"` | ipmitool session active | IPMI over LAN 可达 | P1 |

### 6.2 性能稳定性 (Stability - 24/72h)

| 类别 | 监控指标 | Kernel 数据源 | User Space 工具 | 阈值 | 优先级 |
|------|--------|-------------|----------------|------|--------|
| **吞吐量** | GB/s | perf stat (Bus Read/Write) | iperf3 / fio / dpdk-pktgen | 波动 <10% | P0 |
| **延迟** | µs (p50, p99) | 中断响应时间 | iperf3 --latency / fio log | p99 <10ms | P0 |
| **错误率** | Correctable err/h | dmesg AER 计数 | rasdaemon 事件计数 | <10 err/24h | P0 |
| **功耗** | W / idle 功耗降低 % | 无直接测量 | RAPL 计数器 (若可用) | ≥30% idle 节省 | P1 |
| **温度稳定性** | °C (trend) | thermal zone sysfs | `watch 'cat /sys/class/thermal/thermal_zone*/temp'` | 无长期上升趋势 | P1 |

### 6.3 故障恢复 (Failure Recovery)

| 故障场景 | 触发方式 | 预期恢复 | 验证步骤 | 优先级 |
|--------|--------|--------|--------|--------|
| **Link Down** | `echo 0 > /sys/bus/pci/devices/<bdf>/enable` | 自动重训 | 2s 内 lspci 可见 | P1 |
| **Device Hang** | 注入长期 DMA 阻塞 | IOMMU 中止 DMA，恢复 | dmesg "DMAR fault" 出现 | P1 |
| **Correctable Error Storm** | 诱发 >1000 err/s | 速率限制，无崩溃 | dmesg 无 panic | P1 |
| **FLR Reset** | `echo 1 > /sys/bus/pci/devices/<bdf>/reset` | 设备返回初始状态 | FLR 前后 BAR 一致 | P2 |

---

## 第七部分：测试执行矩阵 (TEST AUTOMATION)

### 7.1 测试优先级与执行顺序

```
Phase 1 (Sanity, 1h)
├─ KSPACE-ENUM-001,002 (RC 初始化)
├─ USPACE-LSPCI-001,002 (基本枚举)
├─ KSPACE-DRV-001 (驱动匹配)
└─ USPACE-SYSFS-001 (sysfs 完整性)

Phase 2 (Functional, 4h)
├─ KSPACE-AER-001,002 (错误处理)
├─ KSPACE-IOMMU-001,002,003 (DMA 保护)
├─ KSPACE-MSI-001,002 (中断)
├─ USPACE-PERF-001,002 (性能计数)
└─ KSPACE-RP-001,002,003 (链路状态)

Phase 3 (Performance, 8h)
├─ USPACE-APP-001,002 (网络/存储基准)
├─ USPACE-QOS-001,002 (QoS 配置)
└─ INTEG-STABILITY (24h baseline)

Phase 4 (Longevity, 72h)
└─ INTEG-STABILITY-72H (持续监控)
```

### 7.2 自动化脚本框架

```python
# scripts/dmr_pcie6_matrix.py

class DMRPCIe6TestMatrix:
    """Intel DMR PCIe 6.0 Kernel/User Space Test Matrix"""
    
    test_phases = {
        'sanity': [
            'KSPACE-ENUM-001', 'KSPACE-ENUM-002',
            'USPACE-LSPCI-001', 'USPACE-SYSFS-001'
        ],
        'functional': [
            'KSPACE-AER-001', 'KSPACE-IOMMU-001',
            'USPACE-PERF-001', 'KSPACE-MSI-001'
        ],
        'performance': [
            'USPACE-APP-001', 'USPACE-APP-002',
            'INTEG-STABILITY'
        ],
        'longevity': ['INTEG-STABILITY-72H']
    }
    
    def run_phase(self, phase_name: str):
        """Execute test phase with kernel/user space cross-validation"""
        test_ids = self.test_phases[phase_name]
        results = {}
        
        for test_id in test_ids:
            k_result = self.run_kernel_test(test_id)
            u_result = self.run_userspace_test(test_id)
            
            # Cross-validate
            is_consistent = self.cross_validate(k_result, u_result, test_id)
            results[test_id] = {
                'kernel': k_result,
                'userspace': u_result,
                'consistent': is_consistent
            }
        
        return results
```

### 7.3 持续集成配置

```yaml
# .github/workflows/dmr_pcie6_tests.yml
name: DMR PCIe 6.0 Test Matrix

on: [push, pull_request, schedule: "0 2 * * 0"]

jobs:
  sanity_phase:
    runs-on: dmr-server-runner  # 自定义 DMR 硬件 runner
    steps:
      - uses: actions/checkout@v2
      - name: Run Sanity Phase
        run: python scripts/dmr_pcie6_matrix.py --phase sanity
  
  functional_phase:
    needs: sanity_phase
    runs-on: dmr-server-runner
    steps:
      - uses: actions/checkout@v2
      - name: Run Functional Phase
        run: python scripts/dmr_pcie6_matrix.py --phase functional
  
  longevity_phase:
    needs: functional_phase
    runs-on: dmr-server-runner
    if: github.event_name == 'schedule'
    steps:
      - uses: actions/checkout@v2
      - name: Run 72h Longevity
        run: python scripts/dmr_pcie6_matrix.py --phase longevity --duration 259200
```

---

## 第八部分：覆盖率与验收标准

### 8.1 功能覆盖率矩阵

| PCIe 6.0 子系统 | Kernel 测试 | User Space 测试 | 交叉验证 | 覆盖率 |
|---------------|-----------|-----------------|--------|--------|
| 设备发现与枚举 | KSPACE-ENUM-* (5) | USPACE-LSPCI/SYSFS-* (5) | 2 个交叉检查 | 100% |
| 链路管理 | KSPACE-RP-* (5) | USPACE-SYSFS-003 | Link Speed/Width 一致性 | 95% |
| AER/RAS | KSPACE-AER-* (5) | USPACE-RAS/PERF-* (4) | 错误计数一致性 | 100% |
| IOMMU/DMA | KSPACE-IOMMU-* (5) | USPACE-UIO-* (4) | IOMMU fault 事件 | 95% |
| 中断处理 | KSPACE-MSI-* (4) | USPACE-PERF-001 | IRQ 计数匹配 | 90% |
| 多 Socket 协调 | KSPACE-FABRIC-* (4) | USPACE-SYSFS-005 + USPACE-QOS-* (3) | NUMA 一致性 | 85% |
| 应用性能 | (间接) | USPACE-APP-* (3) | 与硬件规格对标 | 80% |
| **总体** | **33 tests** | **22 tests** | **12 cross-checks** | **~92%** |

### 8.2 验收标准 (Pass/Fail Criteria)

| 标准 | 指标 | Pass | Fail |
|------|------|------|------|
| **P0 通过率** | 所有 P0 用例成功 | 100% | <100% |
| **P1 通过率** | P1 用例成功 + 可跳过 | ≥90% | <90% |
| **Kernel/User 一致性** | 交叉验证检查点 | ≥95% 一致 | <95% |
| **长稳**（72h） | 无 Uncorrectable 错误 | 0 | >0 |
| **吞吐量性能** | 实测 vs 理论 | ≥85% | <85% |
| **错误率** | Correctable err/24h | <10 | ≥10 |
| **故障恢复** | MTTR (Mean Time To Recover) | <10s | ≥10s |

### 8.3 报告生成

```
DMR PCIe 6.0 Test Report
═════════════════════════════════════

Platform: Intel Diamond Rapids (DMR) 2-socket
Test Date: 2026-01-21
Duration: 72h 15m

Summary:
┌────────────────────────┬─────────┐
│ Kernel Tests           │ 33 / 33 │ PASS ✓
│ User Space Tests       │ 22 / 22 │ PASS ✓
│ Cross-Validation       │ 12 / 12 │ PASS ✓
│ Total Functional Pass  │  92%    │ PASS ✓
│ Longevity (72h)        │  0 err  │ PASS ✓
└────────────────────────┴─────────┘

Critical Findings: NONE
Performance Delta: +2.3% vs baseline
Recommendation: APPROVED FOR PRODUCTION
```

---

## 附录 A：文件与命令参考

### Linux 系统命令

```bash
# 枚举
lspci -vvv
lspci -s <BDF> -vvv
setpci -s <BDF> 0x00.w

# 内核日志
dmesg | grep -i "pci\|aer\|dmar"
journalctl -u rasdaemon -f

# 系统文件
cat /sys/bus/pci/devices/<BDF>/current_link_speed
cat /sys/bus/pci/devices/<BDF>/resource
echo <NumVFs> > /sys/bus/pci/devices/<PF>/sriov_numvfs

# 中断与性能
cat /proc/interrupts
perf stat -e uncore_pcu/event=0x3f/ <workload>
watch -n 1 'grep <vector> /proc/interrupts'

# RAS
rasdaemon -f  # daemon mode
cat /sys/kernel/debug/aer/*/aer/

# IOMMU
dmesg | grep DMAR
cat /sys/kernel/debug/iommu/dmar<N>/regset

# NUMA
numactl -H
cat /sys/devices/system/node/node*/distance
```

### DMR 特定命令

```bash
# Config Fabric 状态
cat /sys/kernel/debug/pmc_core/*/pll_status
cat /sys/kernel/debug/pmc_core/*/pll_cfg

# Telemetry Agent
ipmitool -I lanplus -U <user> -P <pass> -H <bmc_ip> sensor

# Multi-socket 诊断
lspci | grep -E "^[0-9a-f]{2}:" | cut -d: -f1 | sort -u  # 获取所有 segment
```

---

## 附录 B：示例测试脚本

```bash
#!/bin/bash
# dmr_pcie6_sanity.sh - DMR PCIe 6.0 快速健康检查

set -e

echo "=== DMR PCIe 6.0 Sanity Test ==="

# KSPACE-ENUM-001
echo "1. Checking RC initialization..."
if dmesg | grep -q "pci_bus"; then
    echo "   ✓ RC enumerated"
else
    echo "   ✗ FAIL"
    exit 1
fi

# USPACE-LSPCI-001
echo "2. Verifying lspci topology..."
DEV_COUNT=$(lspci | wc -l)
echo "   Found $DEV_COUNT devices"

# KSPACE-ENUM-003 + USPACE-SYSFS-005
echo "3. Checking NUMA affinity..."
for node in /sys/devices/system/node/node*/; do
    echo "   Node $(basename $node): $(cat $node/cpulist | wc -c) CPUs"
done

# KSPACE-AER-001
echo "4. Verifying AER capability..."
if lspci -vvv | grep -q "AER"; then
    echo "   ✓ AER supported"
else
    echo "   ! AER not detected"
fi

# KSPACE-MSI-001
echo "5. Checking MSI configuration..."
MSI_COUNT=$(grep "MSI" /proc/interrupts | wc -l)
echo "   MSI vectors active: $MSI_COUNT"

echo ""
echo "=== Sanity Test Complete ==="
```

---

**文档版本:** 1.0  
**最后更新:** 2026-01-21  
**维护者:** PCIe Platform Validation Team (Intel DMR)  
**许可:** Intel Confidential
