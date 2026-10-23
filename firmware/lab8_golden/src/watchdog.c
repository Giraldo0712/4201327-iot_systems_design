/* Task watchdog with the C6's hardware watchdog as fallback: the node resets
 * itself if the sampler thread or the system workqueue (Observe policy, health
 * reports, the valve fail-safe) stops for CONFIG_LAB_WATCHDOG_S seconds.
 */
#include <zephyr/device.h>
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/task_wdt/task_wdt.h>

#include "app.h"

LOG_MODULE_REGISTER(watchdog, LOG_LEVEL_INF);

#define TIMEOUT_MS (CONFIG_LAB_WATCHDOG_S * MSEC_PER_SEC)

static int sampler_ch = -1;
static int workq_ch = -1;

void watchdog_feed_sampler(void)
{
	if (sampler_ch >= 0) {
		task_wdt_feed(sampler_ch);
	}
}

static void workq_feed(struct k_work *work)
{
	task_wdt_feed(workq_ch);
	k_work_schedule(k_work_delayable_from_work(work), K_SECONDS(1));
}

static K_WORK_DELAYABLE_DEFINE(workq_work, workq_feed);

int watchdog_start(void)
{
	const struct device *hw = DEVICE_DT_GET(DT_ALIAS(watchdog0));
	int r = task_wdt_init(device_is_ready(hw) ? hw : NULL);

	if (r < 0) {
		return r;
	}
	sampler_ch = task_wdt_add(TIMEOUT_MS, NULL, NULL);
	workq_ch = task_wdt_add(TIMEOUT_MS, NULL, NULL);
	if (sampler_ch < 0 || workq_ch < 0) {
		return -ENOMEM;
	}
	k_work_schedule(&workq_work, K_SECONDS(1));
	LOG_INF("Watchdog armed: %d s, hardware fallback %s", CONFIG_LAB_WATCHDOG_S,
		device_is_ready(hw) ? "on" : "off");
	return 0;
}
