#!/usr/bin/env bash
# Build every course firmware on every board and option the labs use: the list CI runs.
# Lab 0's apps are skeletons with TASK markers that stop the build until students
# complete them, so they are not here. Logs: build/ci/*.log
set -euo pipefail
cd "$(dirname "$0")/.."
out=${BUILD_ROOT:-build/ci}
mkdir -p "$out"
fail=0

build() {  # app board [cmake args...]
	local app=$1 board=$2
	shift 2
	local name
	name="$(basename "$app")-${board//\//_}${*:+-$(echo "$*" | md5sum | cut -c1-6)}"
	if west build -p -b "$board" "$app" -d "$out/$name" -- "$@" >"$out/$name.log" 2>&1; then
		echo "ok    $app  $board  $*"
	else
		echo "FAIL  $app  $board  $*  (log: $out/$name.log)"
		fail=1
	fi
}

C6=esp32c6_devkitc/esp32c6/hpcore
S3=esp32s3_devkitc/esp32s3/procpu
USB=(-DEXTRA_CONF_FILE=usb_console.conf -DEXTRA_DTC_OVERLAY_FILE=usb_console.overlay)

build firmware/lab1_radio $C6
build firmware/lab1_radio $C6 "${USB[@]}"
build firmware/lab2_mesh $C6
build firmware/lab3_coap $C6
build firmware/lab4_sensors $C6
for s in ds18b20 dht22 dht11 bmp280; do
	build firmware/lab4_sensors $C6 -DEXTRA_DTC_OVERLAY_FILE=sensors/$s.overlay
done
build firmware/lab4_sensors $C6 -DEXTRA_CONF_FILE=usb_console.conf \
	"-DEXTRA_DTC_OVERLAY_FILE=usb_console.overlay;sensors/dht22.overlay"
build firmware/lab5_rcp $C6
build firmware/lab6_secure $C6
build firmware/lab6_secure $C6 -DEXTRA_DTC_OVERLAY_FILE=sensors/dht22.overlay
build firmware/lab6_secure $C6 "${USB[@]}"
build firmware/lab7_telemetry $C6
build firmware/lab7_telemetry $C6 -DEXTRA_DTC_OVERLAY_FILE=sensors/dht22.overlay
build firmware/lab7_telemetry $C6 "${USB[@]}"
build firmware/lab8_golden $C6 "-DCONFIG_LAB_PSK=\"ci-key\""
build firmware/lab8_golden $C6 "${USB[@]}" "-DCONFIG_LAB_PSK=\"ci-key\""
build firmware/lab5_border_router $S3
build firmware/lab5_border_router $S3 -DEXTRA_CONF_FILE=autostart.conf

exit $fail
