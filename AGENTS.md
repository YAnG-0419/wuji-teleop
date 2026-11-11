# Working rules

- Read `README.md`, `SOURCES.json`, and `VALIDATION.md` before changing interfaces or deployment.
- Support Ubuntu 20.04 / ROS 2 Foxy / Python 3.8 through the default Pixi environment, and Ubuntu 24.04 / ROS 2 Jazzy / Python 3.12 through the jazzy environment, on Linux x86-64. Keep ROS binary extensions aligned with the interpreter and keep build/install outputs separate.
- Manage Python, SDK and build dependencies through root `pixi.toml` and `pixi.lock`; run commands with `pixi run --locked`. Do not create separate venvs or install packages outside the manifest.
- Hardware owns SDK protocols; teleop owns input and retarget; control owns source selection and motion generation. Keep motion logic independent of ROS and SDK imports.
- Preserve source licenses and update provenance when adapting copied code. Reference checkouts are read-only.
- Keep comments minimal and retain existing comments unless directly affected.
- Select checks from the changed behavior. Fake ROS tests do not establish native ROS or hardware acceptance.
- Do not enable or move physical devices without an explicit task instruction to operate them.
