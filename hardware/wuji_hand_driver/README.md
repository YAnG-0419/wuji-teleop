# Wuji Hand 2 ROS hardware

围绕官方 `wuji-sdk==2026.10.12` 的 ROS 2 Python 桥。环境、组合启动、遥操和程序控制见根目录 [README](../../README.md)。

每个进程持有一只手；`hand_side` 为 left／right，`serial` 指定串号，空串号按左右手发现。组合 launch 要求显式串号。SDK bridge 默认关闭，不在多个 ROS 进程之间共享 SDK 设备桥。

- `/wuji/<side>/command`：`sensor_msgs/JointState`，20 关节位置 rad，可选速度 rad/s 和电流前馈 A。
- `/wuji/<side>/joint_states`：实测反馈，sensor-data QoS。
- `/wuji/<side>/hardware_enable`：`std_srvs/SetBool`，控制电机使能；一般由 control 协调调用。

线协议顺序为拇指到小指，每指四关节；具名命令可以重排。SDK 每指使用五个 node ID 槽，其中第五槽不属于运动关节，`driver.py` 负责映射。

默认不使能电机。使能前要求完整且新鲜的 20 关节反馈，使能后等待全部关节诊断确认。命令默认 0.3 秒超时，反馈默认 0.25 秒超时；超时调用 SDK disable，不自动恢复。命令必须带有效 ROS 时间戳。进程被强制终止、主机掉电不能依赖本进程 watchdog 保证物理停止。

`config/wuji_hand_2.yaml` 维护增益、电流上限、反馈频率与超时；组合 launch 复用该文件。退出时关闭订阅、发布器并禁用由本驱动使能的电机。Wuji Hand 2 使用静态 IP，主机网卡必须位于对应子网。

原驱动来源保留在 `SOURCE.json`；本独立版本的修改与版本选择见根目录 `SOURCES.json`。原驱动许可证为 Apache-2.0，见根目录 `licenses/APACHE-2.0`。
