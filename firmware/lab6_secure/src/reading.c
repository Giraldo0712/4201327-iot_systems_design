/* The sensor side of /env/temp. A thread reads the sensor every SAMPLE_MS,
 * rejects values that can't be real, and keeps the last good reading plus the
 * counters printed by "soilsense stats". The sensor is whatever the devicetree
 * alias temp-sensor points at (an overlay from sensors/); without one, the
 * Lab 3 simulation runs instead.
 */
#include <math.h>
#include <stdlib.h>
#include <zephyr/kernel.h>
#include <zephyr/device.h>
#include <zephyr/drivers/sensor.h>
#include <zephyr/logging/log.h>
#include <zephyr/random/random.h>
#include <zephyr/shell/shell.h>

#include "app.h"

LOG_MODULE_REGISTER(reading, LOG_LEVEL_INF);

#define SAMPLE_MS     2000
#define T_MIN_C       (-40.0f)
#define T_MAX_C       85.0f   /* exclusive: a DS18B20 reports exactly 85.0 at power-on */
#define MAX_STEP_C    5.0f    /* between two samples; no air or soil warms that fast */
#define STEP_CHECK_MS 10000   /* the step check only applies against a recent value */
#define LOST_AFTER    3       /* consecutive failed reads before the sensor counts as lost */

#if DT_HAS_ALIAS(temp_sensor)
static const struct device *const sensor = DEVICE_DT_GET(DT_ALIAS(temp_sensor));
#endif

static struct k_spinlock lock;
static struct reading last;
static float last_rh = NAN;
static bool log_samples;

static struct {
	uint32_t reads;
	uint32_t failed;
	uint32_t rejected;
	uint32_t in_a_row;
	uint32_t read_us_min;
	uint32_t read_us_max;
	uint64_t read_us_sum;
	int64_t since_ms;
} stats;

struct reading reading_get(void)
{
	struct reading r;

	K_SPINLOCK(&lock) {
		r = last;
	}

	return r;
}

const char *reading_sensor_name(void)
{
#if DT_HAS_ALIAS(temp_sensor)
	return sensor->name;
#else
	return "simulated";
#endif
}

/* Why t can't be a real reading, or NULL if it is plausible */
static const char *implausible(float t, int64_t now, char *buf, size_t size)
{
	if (t < T_MIN_C || t >= T_MAX_C) {
		snprintk(buf, size, "outside %.0f..%.0f C", (double)T_MIN_C, (double)T_MAX_C);
		return buf;
	}
	if (last.valid && now - last.at_ms < STEP_CHECK_MS && fabsf(t - last.t) > MAX_STEP_C) {
		snprintk(buf, size, "jumped %+.1f C in one sample", (double)(t - last.t));
		return buf;
	}

	return NULL;
}

static void check_and_store(float t, float rh, const char *source)
{
	int64_t now = k_uptime_get();
	char buf[40];
	const char *why;

	K_SPINLOCK(&lock) {
		why = implausible(t, now, buf, sizeof(buf));
		if (why == NULL) {
			last.valid = true;
			last.t = t;
			last.at_ms = now;
			last.seq++;
		} else {
			stats.rejected++;
		}
	}

	if (why != NULL) {
		LOG_WRN("Rejected %.2f C from %s: %s", (double)t, source, why);
	} else if (log_samples && !isnan(rh)) {
		LOG_INF("%s: %.2f C, %.1f %%RH", source, (double)t, (double)rh);
	} else if (log_samples) {
		LOG_INF("%s: %.2f C", source, (double)t);
	}
}

#if DT_HAS_ALIAS(temp_sensor)
static void read_sensor(void)
{
	struct sensor_value v, h;
	float rh = NAN;
	uint32_t c0, us, in_a_row = 0;
	int rc;

	c0 = k_cycle_get_32();
	rc = device_is_ready(sensor) ? sensor_sample_fetch(sensor) : -ENODEV;
	us = k_cyc_to_us_floor32(k_cycle_get_32() - c0);
	if (rc == 0) {
		rc = sensor_channel_get(sensor, SENSOR_CHAN_AMBIENT_TEMP, &v);
	}
	if (rc == 0 && sensor_channel_get(sensor, SENSOR_CHAN_HUMIDITY, &h) == 0) {
		rh = sensor_value_to_float(&h);
	}

	K_SPINLOCK(&lock) {
		stats.reads++;
		stats.read_us_sum += us;
		stats.read_us_min = MIN(stats.read_us_min, us);
		stats.read_us_max = MAX(stats.read_us_max, us);
		if (rc < 0) {
			stats.failed++;
			in_a_row = ++stats.in_a_row;
		} else {
			in_a_row = stats.in_a_row;
			stats.in_a_row = 0;
			last_rh = rh;
		}
	}

	if (rc < 0) {
		if (rc == -ENODEV && in_a_row == 1) {
			LOG_ERR("%s was not found at boot; fix the wiring, then reset the board",
				sensor->name);
		} else if (in_a_row < LOST_AFTER) {
			LOG_WRN("Read failed (%d) after %u us", rc, us);
		} else if (in_a_row == LOST_AFTER) {
			LOG_ERR("Sensor lost: %u failed reads in a row; retrying every %d s",
				in_a_row, SAMPLE_MS / MSEC_PER_SEC);
		}
		return;
	}

	if (in_a_row >= LOST_AFTER) {
		LOG_INF("Sensor back after %u failed reads", in_a_row);
	}
	check_and_store(sensor_value_to_float(&v), rh, sensor->name);
}
#else
/* Lab 3's simulated sensor: 24.5 °C ± 1 °C over 60 s, plus ±0.1 °C noise */
static void read_sensor(void)
{
	float noise = (int32_t)(sys_rand32_get() % 201 - 100) / 1000.0f;
	float phase = (float)(k_uptime_get() % 60000) / 60000.0f;

	K_SPINLOCK(&lock) {
		stats.reads++;
	}
	check_and_store(24.5f + sinf(2.0f * 3.14159265f * phase) + noise, NAN, "simulated");
}
#endif

static void reset_stats(void)
{
	K_SPINLOCK(&lock) {
		memset(&stats, 0, sizeof(stats));
		stats.read_us_min = UINT32_MAX;
		stats.since_ms = k_uptime_get();
	}
}

static void sampler(void *p1, void *p2, void *p3)
{
	int64_t next = k_uptime_get();

	reset_stats();
	LOG_INF("Reading %s every %d s", reading_sensor_name(), SAMPLE_MS / MSEC_PER_SEC);

	while (true) {
		read_sensor();
		next += SAMPLE_MS;
		k_sleep(K_TIMEOUT_ABS_MS(next));
	}
}

/* Below the OpenThread thread (8): the radio may interrupt a sensor read */
K_THREAD_DEFINE(sampler_tid, 2048, sampler, NULL, NULL, NULL, 10, 0, 0);

static int cmd_stats(const struct shell *sh, size_t argc, char **argv)
{
	struct reading r;
	float rh;
	typeof(stats) s;
	int64_t now = k_uptime_get();

	K_SPINLOCK(&lock) {
		r = last;
		rh = last_rh;
		s = stats;
	}

	shell_print(sh, "sensor:    %s", reading_sensor_name());
	if (r.valid) {
		shell_print(sh, "last good: %.2f C, %lld s ago", (double)r.t,
			    (now - r.at_ms) / MSEC_PER_SEC);
	} else {
		shell_print(sh, "last good: none yet");
	}
	if (!isnan(rh)) {
		shell_print(sh, "humidity:  %.1f %%RH", (double)rh);
	}
	shell_print(sh, "reads:     %u in %lld s: %u failed (%.1f %%), %u rejected", s.reads,
		    (now - s.since_ms) / MSEC_PER_SEC, s.failed,
		    s.reads ? 100.0 * s.failed / s.reads : 0.0, s.rejected);
	if (s.reads > 0 && s.read_us_max > 0) {
		shell_print(sh, "read time: min %u us, avg %llu us, max %u us", s.read_us_min,
			    s.read_us_sum / s.reads, s.read_us_max);
	}
	if (s.in_a_row > 0) {
		shell_print(sh, "now:       %u failed reads in a row", s.in_a_row);
	}

	return 0;
}

static int cmd_reset(const struct shell *sh, size_t argc, char **argv)
{
	reset_stats();
	shell_print(sh, "Counters zeroed");
	return 0;
}

static int cmd_log(const struct shell *sh, size_t argc, char **argv)
{
	if (strcmp(argv[1], "on") == 0) {
		log_samples = true;
	} else if (strcmp(argv[1], "off") == 0) {
		log_samples = false;
	} else {
		shell_error(sh, "Usage: soilsense log on|off");
		return -EINVAL;
	}

	return 0;
}

static int cmd_inject(const struct shell *sh, size_t argc, char **argv)
{
	char *end;
	float t = strtof(argv[1], &end);

	if (end == argv[1] || *end != '\0') {
		shell_error(sh, "Usage: soilsense inject <degrees C>");
		return -EINVAL;
	}

	check_and_store(t, NAN, "inject");
	return 0;
}

SHELL_STATIC_SUBCMD_SET_CREATE(soilsense_cmds,
	SHELL_CMD_ARG(stats, NULL, "Last reading, failure counts and read time", cmd_stats, 1, 0),
	SHELL_CMD_ARG(reset, NULL, "Zero the counters", cmd_reset, 1, 0),
	SHELL_CMD_ARG(log, NULL, "Print every reading: log on|off", cmd_log, 2, 0),
	SHELL_CMD_ARG(inject, NULL, "Pass one made-up reading through the checks: inject <C>",
		      cmd_inject, 2, 0),
	SHELL_SUBCMD_SET_END);

SHELL_CMD_REGISTER(soilsense, &soilsense_cmds, "SoilSense sensor tools", NULL);
