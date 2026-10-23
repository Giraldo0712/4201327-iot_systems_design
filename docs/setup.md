# Setup — Zephyr on ESP32-C6

One-time install, done **before Lab 1**. Budget ~1 hour, almost all of it downloads.

**You are done when this prints on your board:**

```
*** Booting Zephyr OS ***
Hello World! esp32c6_devkitc/esp32c6/hpcore
```

---

## 0. Get a Linux shell

- **Windows** → install WSL2 and pass the board through with `usbipd`:
  [wsl2-embedded-dev-setup](https://github.com/saacifuentesmu/wsl2-embedded-dev-setup) (steps 1–3).
- **Linux / macOS** → you already have one. Skip to step 1.

Everything below runs *inside* that shell.

## 1. Packages

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install --no-install-recommends git cmake ninja-build gperf ccache \
  dfu-util device-tree-compiler wget python3-pip python3-dev python3-venv \
  xz-utils file make gcc gcc-multilib g++-multilib libsdl2-dev libmagic1
sudo usermod -aG dialout $USER
```

Close the terminal and open a new one (the `dialout` group only applies to new shells).

## 2. west

```bash
python3 -m venv ~/zephyrproject/.venv
source ~/zephyrproject/.venv/bin/activate
pip install --upgrade pip west
```

## 3. Workspace

The course is validated on one Zephyr revision, pinned in [west.yml](../west.yml); the
`checkout` line puts your workspace on it.

```bash
west init ~/zephyrproject   # 10+ min, and prints nothing while it clones
cd ~/zephyrproject
git -C zephyr checkout 2f0bc11264a8e72e214f3db0a3fa221eb022453a
west update                 # slower still: clones the HALs
west packages pip --install
west zephyr-export
```

Then write the two lines every new terminal needs into one file:

```bash
cat > ~/zephyrproject/env.sh <<'END'
source ~/zephyrproject/.venv/bin/activate
source ~/zephyrproject/zephyr/zephyr-env.sh
END
```

> **Every terminal starts with `source ~/zephyrproject/env.sh`.** Nearly every
> "west: command not found" is a forgotten `source`.

> `west init` looks frozen for ten minutes or more. Let it finish — a Ctrl-C
> here leaves a broken `.west/` that you have to `rmdir` before retrying.

## 4. ESP32-C6 blobs and compiler

```bash
cd ~/zephyrproject/zephyr
west blobs fetch hal_espressif        # RF binaries, not shipped in the tree
west sdk install -t riscv64-zephyr-elf
```

## 5. Hello World

```bash
west build -p auto -b esp32c6_devkitc/esp32c6/hpcore samples/hello_world
west flash
west espressif monitor                # Ctrl+] to exit
```

On Windows, run `usbipd attach --wsl --busid <BUSID>` from PowerShell first, then
check the board is there with `ls /dev/ttyUSB* /dev/ttyACM*`.

The C6-DevKitC-1 and DevKitM-1 have **two** USB-C ports: `UART` shows up as
`/dev/ttyUSB0`, `USB` as `/dev/ttyACM0`. Both can flash, but the console (and the shell in
the labs) is on **UART**; the USB port shows nothing with the stock board config. An
ESP32-C6 Super Mini has only the USB port; Lab 1 shows the build option that moves the
console there.

## 6. Fork the course repo

Your deliverables live in your own fork.

1. Fork [4201327-iot_systems_design](https://github.com/saacifuentesmu/4201327-iot_systems_design).
2. Clone it: `git clone https://github.com/<YOUR_USERNAME>/4201327-iot_systems_design.git`

---

## When something breaks

| Symptom | Fix |
|---|---|
| `west: command not found` | `source ~/zephyrproject/env.sh` |
| `Unable to find a valid toolchain` | Step 4. Check names with `west sdk list` |
| `No module named 'jsonschema'` + a long traceback | `west packages pip --install`, then re-run `west zephyr-export` |
| Build complains about espressif blobs | `west blobs fetch hal_espressif` |
| No `/dev/ttyUSB*` or `/dev/ttyACM*` | Windows: re-run `usbipd attach`. Then `lsusb` |
| `Permission denied: '/dev/ttyUSB0'` | Step 1's `usermod`, then open a new terminal |
| Flash hangs or fails to sync | Hold **BOOT**, tap **RESET**, release **BOOT**, retry |

Still stuck? Bring the **error text** (not a photo) to the next session.
