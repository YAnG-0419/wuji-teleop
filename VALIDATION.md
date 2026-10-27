# 验证范围

记录更新日期：2026-10-27。开发主机为 Ubuntu 24.04 x86-64；项目 Pixi 环境固定 Python 3.8.20，SDK 为 2026.10.12，部署目标 glibc 2.31。依赖、SDK 和 MANUS 构建检查执行于 2026-10-26；当前目标转发改动按受影响模块检查。

| 检查 | 结果与边界 |
| --- | --- |
| `pixi install --locked` | 环境可从清单和锁文件安装；未在目标 Ubuntu 20.04 主机安装 |
| 定向 pytest：`tests/test_motion.py`、`tests/test_control.py`、`tests/test_retarget.py`、`tests/test_python_compatibility.py` | 14 项通过；覆盖选中目标原样转发、快速目标变化、非法目标拒绝、来源切换、取消后迟到结果、状态时效、左右手真实 retarget 求解、关节重排及 Python 3.8 语法 |
| 开关定向 pytest：`tests/test_switch.py`、`tests/test_control.py`、`tests/test_python_compatibility.py` | 10 项通过；覆盖开启顺序、默认关闭、失败后清理、control 不可用时仍尝试硬件禁用、q／EOF／Ctrl-C 退出清理，以及使能取消和 Python 3.8 兼容性；测试使用注入调用和 ROS 替身 |
| `python -m wuji_teleop.switch --help` | 入口和参数解析正常；未执行真实 ROS 开关调用 |
| `pixi run --locked check-sdk` | 实际导入官方 Python 3.8 SDK，构造命令和连接配置；不扫描或连接设备 |
| `pixi run --locked build-manus` | 原生 C++ 桥编译通过，ctypes ABI 与库加载通过；未连接 MANUS Core 或手套 |
| `colcon list --base-paths hardware control teleop` | 三个 ament_python 包均能识别；不是 ROS 构建或 DDS 通信验收 |
| ROS Foxy 原生构建／节点运行 | 未执行。主机只有 Jazzy，两次拉取 Foxy 测试镜像均因网络 TLS 超时失败 |
| 真机与跨机通信 | 未执行；没有连接 Wuji、MANUS 或发送物理动作 |

硬件和 control 节点的逻辑检查使用测试内 ROS 替身，因此不证明 Foxy 的 rclpy、launch、DDS 或硬件通信已经通过。retarget 测试使用实际 Pinocchio／NLopt 和左右手 URDF，但使用合成关键点，不能据此判定真人抓取效果。

目标电脑部署后需要检查：ROS 构建及节点导入、实际串号和网卡、完整 20 关节反馈、MANUS 原始关键点与标定、关节方向、初次使能时的目标差异和实际跟随、输入中断与显式停止、两机时间同步和消息时效。每次报告实际运动、停止结果和任务效果，不以软件测试代替现场验收。
