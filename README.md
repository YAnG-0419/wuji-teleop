# Wuji ROS 2 遥操与程序控制

独立的 Wuji Hand 2 工程。将整个目录复制到另一台电脑即可部署，不依赖 Li Agent、Franka、GELLO、Workbench 或原参考仓库。当前部署目标是 **Ubuntu 20.04、ROS 2 Foxy、Linux x86-64、Python 3.8**。

## 职责与通信

| 目录 | 职责 |
| --- | --- |
| `hardware/wuji_hand_driver` | 官方 Wuji SDK 到 ROS 的桥接：连接、状态反馈、20 关节命令、使能与超时禁用 |
| `teleop/wuji_teleop` | 21 点手部关键点到 20 关节的 retarget、遥操启停开关；可选 MANUS 关键点发布器 |
| `teleop/manus_bridge` | 从参考工程提取的 MANUS 原生桥与 SDK，用于读取 MANUS；不控制 Wuji |
| `control/wuji_control` | 选择遥操或程序目标，检查时效与关节范围并原样转发目标；提供 Python 控制入口 |
| `examples` | 通过同一 control 入口执行程序运动 |

```text
MANUS／其他关键点源 ─ ROS PointCloud ─ retarget ─ target/teleop ─┐
                                                            ├─ control ─ command ─ hardware ─ Wuji SDK ─ 手
Python 程序 ──────────────────────────────── target/program ─┘
                                                                ↑ joint_states
```

control 不连接 SDK，retarget 不直接发硬件命令。每只手只有一个 hardware 进程；同一台手不能同时由原工程控制。control 默认未使能，硬件电机默认未使能。源切换会清除旧目标并关闭 control；输入或反馈超时不会自动恢复运动。

## Foxy 与 Jazzy

两者的 ROS 2 编程概念和本工程使用的标准消息相近，但运行环境不能互换：Foxy 的系统 Python 是 3.8，Jazzy 的系统 Python 是 3.12，`rclpy` 等二进制扩展必须匹配。这里提供的 Pixi lock 针对 Foxy；不能用它直接加载 Jazzy 的 `rclpy`。跨 ROS 发行版的 DDS 通信也不作为本工程保证，另一台参与控制的 ROS 电脑应使用同一发行版及兼容 RMW。

原 Li Agent 的 `wuji-sdk==2026.8.31` 不适用于该部署目标。本工程固定 `wuji-sdk==2026.10.12`：官方在这个版本增加了 Python 3.8、Ubuntu 20.04 支持，提供 manylinux2014 wheel，无需复制 SDK 源码或创建额外 SDK 进程。参见 [官方发行说明](https://github.com/wuji-technology/wuji-sdk/releases/tag/v2026.10.12) 和 [PyPI 发行文件](https://pypi.org/project/wuji-sdk/2026.10.12/)。

## 在另一台电脑部署

先安装系统级 ROS 2 Foxy（至少 `ros-base`）、`sensor_msgs`、`geometry_msgs`、`std_srvs`、`launch_ros` 和 Pixi。Foxy 已结束官方维护；此工程依照用户指定的平台整理。系统 ROS 由操作系统安装，**Python、SDK、retarget、colcon 和 C++ 构建工具全部由根 `pixi.toml`／`pixi.lock` 管理**，不要额外 pip 安装或修改系统 Python。

从当前电脑打包源码和资源，排除本机环境及构建目录：

```bash
tar --exclude=.pixi --exclude=build --exclude=install --exclude=log \
    --exclude=__pycache__ --exclude=.pytest_cache \
    -C /home/descfly/lpy -czf /tmp/wuji-teleop.tar.gz wuji-teleop
```

将压缩包复制到目标电脑并解压到任意目录。在目标电脑的工程根目录运行：

```bash
source /opt/ros/foxy/setup.bash
pixi install --locked
pixi run --locked check-sdk
pixi run --locked build
source install/setup.bash
```

首次安装需要能访问 conda-forge 和 PyPI；源码目录包含 lock，但不包含预下载的离线依赖。安装生成的 `.pixi`、`build`、`install` 含本机路径，换机器后重新生成。当前 lock 仅含 `linux-64`；ARM 机器需要单独解析和验证，不能原样复用。

以后每个终端进入工程目录并执行：

```bash
source /opt/ros/foxy/setup.bash
source install/setup.bash
export ROS_DOMAIN_ID=42
export ROS_LOCALHOST_ONLY=0
```

再用 `pixi run --locked ...` 运行命令。激活脚本保留系统 ROS 的 Python 路径。

## 启动硬件与 control

将连接 Wuji 的网卡配置到手部静态 IP 所在子网，并填入实际串号。终端 A：

```bash
export WUJI_RIGHT_SERIAL='填写右手实际串号'
pixi run --locked ros2 launch wuji_control hand.launch.py \
    side:=right serial:="$WUJI_RIGHT_SERIAL" retarget:=true
```

这会启动右手 hardware、control、retarget，但不使能电机。左手另开终端，使用 `side:=left` 和左手串号；只做程序控制时省略 `retarget:=true`。

终端 B 检查反馈，不发送运动：

```bash
pixi run --locked ros2 topic echo /wuji/right/joint_states \
    --qos-reliability best_effort
```

## 遥操输入与运行

关键点输入是 `/teleop/<side>/keypoints`，类型 `sensor_msgs/msg/PointCloud`，恰好 21 个点，单位米，顺序为腕点，然后拇指、食指、中指、无名指、小指各四点（MediaPipe 顺序）。必须设置有效 `header.stamp`。其他相机或手套只需实现这个输入，不需改 hardware。

MANUS 输入使用参考工程中的 25→21 点映射和坐标处理。需要本机可访问的 MANUS Core／Robotics Service、对应手套和厂商运行依赖。MANUS SDK 为专有软件，保留在 `teleop/manus_bridge/vendor/manus_sdk`，遵循其中 `LICENSE.vendor`。桥和所附 SDK 库仅提供 x86-64 Linux 版本。

先构建桥：

```bash
pixi run --locked build-manus
```

终端 B 启动输入（保持终端 A 运行）：

```bash
pixi run --locked ros2 run wuji_teleop wuji-manus --ros-args \
    -p library:="$PWD/build/manus_bridge/libmanus_skeleton_bridge.so"
```

可用 `-p calibration_dir:=/实际标定目录` 加载 `Calibration_left.mcal`／`Calibration_right.mcal`；没有复制原操作者的标定文件。参考配置保留原工程的手长、旋转和右手 pinch 修正，需要针对新操作者核对，不能视作通用标定。

关键点和目标连续更新后，终端 C 打开遥操开关：

```bash
pixi run --locked python -m wuji_teleop.switch --side right
```

开关打开时先关闭该手输出，默认不跟随。输入 `s` 并按回车开启遥操，输入 `x` 并按回车关闭，输入 `q` 并按回车关闭后退出。Ctrl-C 或输入流关闭时也会尝试停止；失败会明确显示“停止未确认”，不能将终端退出当作停止确认。开关操作的是整只手的 control／硬件使能，打开终端开关会停止该手已有的程序控制。

开关只控制是否跟随，不启动或关闭 MANUS、retarget 或 hardware 进程；这些进程保持运行便于再次开启。数据超时关闭后，需要重新输入 `s`。重新执行 `pixi run --locked build` 后，也可以用 `pixi run --locked ros2 run wuji_teleop wuji-teleop-switch --side right` 打开。

需要脚本式操作时，可分别执行：

```bash
pixi run --locked python -m wuji_teleop.switch on --side right
pixi run --locked python -m wuji_teleop.switch off --side right
```

`on` 执行成功后退出命令，遥操继续运行，直到 `off`、终端开关停止或原有超时机制关闭。`off` 同时请求 control 停止和 hardware 禁用，任一调用失败会返回非零退出码。不要同时操作多个开关实例。

开关复用以下 ROS 服务。开启时先选择遥操来源，再等待硬件使能结果并检查最新实测反馈，然后转发目标：

```bash
pixi run --locked ros2 service call /wuji/right/select_teleop std_srvs/srv/SetBool '{data: true}'
pixi run --locked ros2 service call /wuji/right/enable std_srvs/srv/SetBool '{data: true}'
```

遥操沿用 retarget 的低通滤波：左右手配置中的 `retarget.lp_alpha` 默认为 0.2，更新公式为 `filtered = 0.8 * previous + 0.2 * current`。它减轻关键点噪声和求解波动引起的关节目标抖动，同时会引入跟随滞后；control 原样转发滤波后的关节目标，不额外限制目标变化速度。滤波器首帧及 reset 后首帧直接采用当前目标。

关键点或反馈超过 0.25 秒失效，control 停止跟随并锁存未使能；hardware 连续 0.3 秒没有有效命令或反馈超时会禁用电机。恢复输入后仍需显式使能。进程被强制杀死或机器断电后的行为由设备自身保障，ROS watchdog 不是独立硬件急停。

## 用代码控制运动

保持 hardware 和 control 运行。`WujiClient` 选择 program 来源、从实测位置开始、发布平滑目标，并依据实测反馈判断到位；退出上下文时关闭 control 和电机：

```python
import rclpy
from wuji_control.client import WujiClient

rclpy.init()
try:
    with WujiClient("right") as hand:
        hand.move_to(target_radians, duration=2.0)
finally:
    rclpy.shutdown()
```

`target_radians` 必须是经现场确认的 20 个弧度值，按拇指、食指、中指、无名指、小指排列，每指四关节。也可将数组保存为 JSON，运行：

```bash
pixi run --locked python examples/move_hand.py \
    --side right --positions /实际路径/target.json --duration 2.0
```

`move_to()` 的 `duration` 决定程序目标插值的时长，control 原样转发程序生成的目标。程序控制完成后若要回到遥操，需要重新选择来源并使能。不要同时运行两个同来源的控制程序；当前 control 没有实现同来源多客户端的排他租约。直接向 `/wuji/<side>/command` 发布会绕过 control 的来源选择、时效和范围检查，普通程序应使用 client 或 `target/program`。

## ROS 契约与停止

| 接口（将 `<side>` 替换为 left／right） | 类型 | 含义 |
| --- | --- | --- |
| `/wuji/<side>/joint_states` | `sensor_msgs/JointState` | 实测位置 rad、速度 rad/s、effort 为 SDK 电流代理 A；sensor-data QoS |
| `/wuji/<side>/target/teleop` | `sensor_msgs/JointState` | retarget 目标，保留关键点来源时间 |
| `/wuji/<side>/target/program` | `sensor_msgs/JointState` | 程序目标，带有效时间戳 |
| `/wuji/<side>/command` | `sensor_msgs/JointState` | control 到 hardware 的命令 |
| `/wuji/<side>/enable` | `std_srvs/SetBool` | 协调硬件使能并验证最新实测反馈后开关 control 输出 |
| `/wuji/<side>/hardware_enable` | `std_srvs/SetBool` | 开关硬件电机 |
| `/wuji/<side>/select_teleop` | `std_srvs/SetBool` | true=teleop、false=program；切换后 control 关闭 |

20 个线协议关节名为 `<side>_finger1_joint1` 到 `<side>_finger5_joint4`。retarget 通过模型关节名称转换到这个顺序，不假设 Pinocchio 的内部关节顺序等于设备顺序。control 要求完整且唯一的名字，并拒绝越界或非有限目标。

停止右手：

```bash
pixi run --locked ros2 service call /wuji/right/enable std_srvs/srv/SetBool '{data: false}'
pixi run --locked ros2 service call /wuji/right/hardware_enable std_srvs/srv/SetBool '{data: false}'
```

确认服务结果后退出遥操输入和 launch。禁用调用被接纳与物理静止是不同结论，现场需确认实际状态。

两台电脑通信时使用同一 ROS domain，确保 DDS 发现和数据端口互通，并同步系统时钟；本工程检查消息源时间，不能用本机接收时间掩盖跨机积压。

## 验证与来源

```bash
pixi run --locked test
pixi run --locked check-sdk
```

这些命令不连接设备。MANUS 桥的加载检查需要先运行 `build-manus`。实际执行的检查和平台限制见 [验证记录](VALIDATION.md)。复制来源和修改范围见 [SOURCES.json](SOURCES.json)，许可证见 `licenses/` 及 MANUS SDK 随附文件。
