#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/drivers/led_strip.h>
#include <openthread.h>
#include <openthread/thread.h>

LOG_MODULE_REGISTER(lab2_mesh, LOG_LEVEL_INF);

static const struct device *const strip = DEVICE_DT_GET(DT_ALIAS(led_strip));

/* Thread role → LED colour, indexed by otDeviceRole */
static const struct led_rgb role_colors[] = {
	[OT_DEVICE_ROLE_DISABLED] = { .r = 0x00, .g = 0x00, .b = 0x00 },
	[OT_DEVICE_ROLE_DETACHED] = { .r = 0x20, .g = 0x00, .b = 0x00 },
	[OT_DEVICE_ROLE_CHILD]    = { .r = 0x20, .g = 0x18, .b = 0x00 },
	[OT_DEVICE_ROLE_ROUTER]   = { .r = 0x00, .g = 0x20, .b = 0x00 },
	[OT_DEVICE_ROLE_LEADER]   = { .r = 0x00, .g = 0x00, .b = 0x20 },
};

static atomic_t role = ATOMIC_INIT(OT_DEVICE_ROLE_DISABLED);

/* The OpenThread callback runs with the stack locked; drive the LED from the system workqueue */
static void led_work_handler(struct k_work *work)
{
	struct led_rgb pixel = role_colors[atomic_get(&role)];

	if (led_strip_update_rgb(strip, &pixel, 1) != 0) {
		LOG_ERR("Failed to drive LED");
	}
}

static K_WORK_DEFINE(led_work, led_work_handler);

static void ot_state_changed(otChangedFlags flags, void *user_data)
{
	if (!(flags & OT_CHANGED_THREAD_ROLE)) {
		return;
	}

	otDeviceRole r = otThreadGetDeviceRole(openthread_get_default_instance());

	LOG_INF("Thread role: %s", otThreadDeviceRoleToString(r));
	atomic_set(&role, r);
	k_work_submit(&led_work);
}

static struct openthread_state_changed_callback ot_state_cb = {
	.otCallback = ot_state_changed,
};

int main(void)
{
	if (!device_is_ready(strip)) {
		LOG_ERR("LED strip device not ready");
	} else {
		k_work_submit(&led_work);
		openthread_state_changed_callback_register(&ot_state_cb);
	}

	LOG_INF("Thread mesh node ready. OpenThread commands start with \"ot\".");

	return 0;
}
