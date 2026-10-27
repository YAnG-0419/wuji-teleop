from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    side = LaunchConfiguration("side")
    serial = LaunchConfiguration("serial")
    return LaunchDescription([
        DeclareLaunchArgument("side", default_value="right", choices=["left", "right"]),
        DeclareLaunchArgument("serial", description="Explicit Wuji Hand 2 serial number"),
        DeclareLaunchArgument("retarget", default_value="false"),
        DeclareLaunchArgument("params_file", default_value=PathJoinSubstitution([
            FindPackageShare("wuji_hand_driver"), "config", "wuji_hand_2.yaml"])),
        Node(package="wuji_hand_driver", executable="wuji-hand-2-driver", name="wuji_hardware",
             namespace=side, output="screen", parameters=[LaunchConfiguration("params_file"), {
                 "hand_side": side, "serial": serial, "auto_enable": False,
                 "command_timeout_sec": 0.3, "feedback_timeout_sec": 0.25,
             }]),
        Node(package="wuji_control", executable="wuji-control", name="wuji_control",
             namespace=side, output="screen", parameters=[{"side": side}]),
        Node(package="wuji_teleop", executable="wuji-retarget", name="wuji_retarget",
             namespace=side, output="screen", parameters=[{"side": side}],
             condition=IfCondition(LaunchConfiguration("retarget"))),
    ])
