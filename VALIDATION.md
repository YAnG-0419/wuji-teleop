# 验证范围

记录更新日期：2026-11-11。验证主机为 Ubuntu 24.04 x86-64，安装系统 ROS 2 Jazzy。默认 Pixi 环境使用 Python 3.8，jazzy 环境使用 Python 3.12；SDK 均为 2026.10.12，retarget 均为 Pinocchio 2.7.0／NLopt 2.7.1。

| 检查 | 结果与边界 |
| --- | --- |
| `pixi install --locked`、`pixi install --locked -e jazzy` | 两套锁定环境均安装通过；未在 Ubuntu 20.04 主机安装 |
| 两环境的兼容测试基线 | 各 33 项通过、1 项跳过；包括左右手真实 retarget 求解、关节映射、驱动协议、开关、Python 3.8 语法与环境选择；跳过的是需单独启用的原生 ROS 测试 |
| 两环境定向 pytest：`tests/test_control.py`、`tests/test_motion.py`、`tests/test_build_environment.py`、`tests/test_python_compatibility.py` | 各 13 项通过；覆盖当前启动等待／超时修复、取消后迟到结果、目标原样转发、反馈时效、错误 ROS 发行版拒绝和 Python 版本匹配 |
| 两环境 `check-sdk` | 实际导入各自 Python 版本的官方 SDK，构造命令和连接配置；不扫描或连接设备 |
| 两环境 `build-manus` | 两套输出目录分别编译通过，ctypes ABI 与库加载通过；未连接 MANUS Core 或手套 |
| `pixi run --locked -e jazzy build` | hardware、control、teleop 三个 ROS 包原生构建成功 |
| Jazzy `check-ros`、launch `--show-args`、已安装开关 `--help` | ROS 类型、节点模块导入、launch 描述和安装入口验证通过 |
| `pixi run --locked -e jazzy test-ros` | 1 项实际 ROS/DDS 合成链路检查通过：关键点 → retarget → control → 模拟硬件命令、真实开关 CLI 开关、输入超时停止转发、无新鲜输入时拒绝使能 |
| ROS Foxy 原生构建／节点运行 | 未执行；当前主机没有系统 Foxy。Python 3.8 软件检查不等于 Foxy 原生验证 |
| 真机与跨机通信 | 未执行；没有连接 Wuji、MANUS 或发送物理动作 |

单元测试使用 ROS 替身；原生 Jazzy 测试使用系统 rclpy、消息和 DDS，但硬件使能服务、反馈、关键点由测试节点生成，未启动 Wuji hardware 驱动。retarget 使用实际 Pinocchio／NLopt 和 URDF。Pinocchio 的 Frame.parent 弃用提示仍会出现，不影响本次检查结果。这些结果不证明 Foxy 原生环境、实际 SDK 通信或真人抓取效果。

目标电脑部署后需要检查：ROS 构建及节点导入、实际串号和网卡、完整 20 关节反馈、MANUS 原始关键点与标定、关节方向、初次使能时的目标差异和实际跟随、输入中断与显式停止、两机时间同步和消息时效。每次报告实际运动、停止结果和任务效果，不以软件测试代替现场验收。
