from pathlib import Path
from setuptools import find_packages, setup

name = 'wuji_teleop'
data = [("share/ament_index/resource_index/packages", ["resource/" + name]),
        ("share/" + name, ["package.xml"])]
for directory in ("config", "models", "launch"):
    for path in Path(directory).rglob("*"):
        if path.is_file():
            data.append(("share/" + name + "/" + str(path.parent), [str(path)]))
setup(name=name, version="0.1.0", packages=find_packages(), data_files=data,
      install_requires=["setuptools"], python_requires=">=3.8", zip_safe=False,
      entry_points={"console_scripts": ['wuji-retarget = wuji_teleop.node:main', 'wuji-manus = wuji_teleop.manus_node:main', 'wuji-teleop-switch = wuji_teleop.switch:main']})
