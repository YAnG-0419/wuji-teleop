import argparse
import signal


class TeleopSwitch:
    def __init__(self, call):
        self.call = call

    def start(self):
        try:
            self.call("select_teleop", True)
            self.call("enable", True)
        except Exception as error:
            try:
                self.stop()
            except Exception as stop_error:
                raise RuntimeError("启动失败: %s；停止未确认: %s" % (error, stop_error)) from error
            raise

    def stop(self):
        errors = []
        for service in ("enable", "hardware_enable"):
            try:
                self.call(service, False)
            except Exception as error:
                errors.append("%s: %s" % (service, error))
        if errors:
            raise RuntimeError("停止未完全确认: " + "; ".join(errors))


def keyboard(switch, read=input, write=print):
    try:
        switch.stop()
        write("已关闭输出。输入 s 开启遥操，x 关闭，q 关闭并退出；按回车执行。")
        write("输入超时会关闭跟随；恢复数据后请重新输入 s。")
        while True:
            command = read("teleop> ").strip().lower()
            if command == "q":
                return
            if command not in ("s", "x"):
                write("请输入 s / x / q。")
                continue
            try:
                if command == "s":
                    switch.start()
                    write("遥操已开启。")
                else:
                    switch.stop()
                    write("遥操已关闭，硬件禁用调用成功。")
            except Exception as error:
                write(str(error))
    except (EOFError, KeyboardInterrupt):
        write("正在关闭遥操。")
    finally:
        switch.stop()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Wuji 遥操启停开关；默认进入终端操作。")
    parser.add_argument("action", choices=("keyboard", "on", "off"), nargs="?", default="keyboard")
    parser.add_argument("--side", choices=("left", "right"), default="right")
    args = parser.parse_args(argv)

    import rclpy
    from rclpy.node import Node
    from std_srvs.srv import SetBool

    rclpy.init(args=[])
    node = Node("wuji_teleop_switch_" + args.side)

    def interrupt(signum, frame):
        raise KeyboardInterrupt

    previous_signal = signal.signal(signal.SIGINT, interrupt)

    def call(service, enabled):
        endpoint = "/wuji/" + args.side + "/" + service
        client = node.create_client(SetBool, endpoint)
        try:
            if not client.wait_for_service(timeout_sec=3.0):
                raise TimeoutError(endpoint + " 不可用")
            future = client.call_async(SetBool.Request(data=enabled))
            rclpy.spin_until_future_complete(node, future, timeout_sec=16.0)
            if not future.done():
                raise TimeoutError(endpoint + " 结果未知")
            result = future.result()
            if result is None or not result.success:
                raise RuntimeError(endpoint + ": " + (result.message if result else "无响应"))
        finally:
            node.destroy_client(client)

    switch = TeleopSwitch(call)
    try:
        if args.action == "keyboard":
            keyboard(switch)
        elif args.action == "on":
            try:
                switch.start()
            except KeyboardInterrupt:
                switch.stop()
                raise
            print("遥操已开启；随后可用 off 命令关闭。")
        else:
            switch.stop()
            print("遥操已关闭，硬件禁用调用成功。")
    except (Exception, KeyboardInterrupt) as error:
        print("开关操作失败: " + str(error))
        raise SystemExit(1)
    finally:
        signal.signal(signal.SIGINT, previous_signal)
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
