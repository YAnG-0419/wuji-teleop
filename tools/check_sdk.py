from importlib.metadata import version

from wuji_sdk import ConnectOptions, Handedness, JointCommand, SdkManager, WujiHand2

assert version("wuji-sdk") == "2026.10.12"
options = ConnectOptions(enable_bridge=False)
command = JointCommand(0.0, 0.0, 0.0)
print("wuji-sdk", version("wuji-sdk"), "imports; command/options constructed; no device connection")
