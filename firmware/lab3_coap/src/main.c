#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/drivers/led_strip.h>
#include <zephyr/net/coap_service.h>
#include <openthread.h>
#include <openthread/thread.h>

#include "app.h"

LOG_MODULE_REGISTER(lab3_coap, LOG_LEVEL_INF);

static uint16_t coap_port = 5683;

/* Starts at boot on every board. On the board where you run "ot coap start",
 * OpenThread binds port 5683 itself and keeps the traffic, so that board acts
 * as the client and this server stays silent.
 */
COAP_SERVICE_DEFINE(soilsense, NULL, &coap_port, COAP_SERVICE_AUTOSTART);

static const struct device *const strip = DEVICE_DT_GET(DT_ALIAS(led_strip));

/* Thread role → LED colour, indexed by otDeviceRole */
static const struct led_rgb role_colors[] = {
	[OT_DEVICE_ROLE_DISABLED] = { .r = 0x00, .g = 0x00, .b = 0x00 },
	[OT_DEVICE_ROLE_DETACHED] = { .r = 0x20, .g = 0x00, .b = 0x00 },
	[OT_DEVICE_ROLE_CHILD]    = { .r = 0x20, .g = 0x18, .b = 0x00 },
	[OT_DEVICE_ROLE_ROUTER]   = { .r = 0x00, .g = 0x20, .b = 0x00 },
	[OT_DEVICE_ROLE_LEADER]   = { .r = 0x00, .g = 0x00, .b = 0x20 },
};
static const struct led_rgb valve_open_color = { .r = 0x30, .g = 0x30, .b = 0x30 };

static atomic_t role = ATOMIC_INIT(OT_DEVICE_ROLE_DISABLED);
static atomic_t valve_open;

/* The OpenThread callback runs with the stack locked; drive the LED from the system workqueue */
static void led_work_handler(struct k_work *work)
{
	struct led_rgb pixel = atomic_get(&valve_open) ? valve_open_color
						       : role_colors[atomic_get(&role)];

	if (led_strip_update_rgb(strip, &pixel, 1) != 0) {
		LOG_ERR("Failed to drive LED");
	}
}

static K_WORK_DEFINE(led_work, led_work_handler);

void led_show_valve(bool open)
{
	atomic_set(&valve_open, open);
	k_work_submit(&led_work);
}

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

int response_init(struct coap_packet *rsp, uint8_t *buf, size_t size,
		  const struct coap_packet *req, uint8_t code)
{
	uint8_t token[COAP_TOKEN_MAX_LEN];
	uint8_t tkl = coap_header_get_token(req, token);
	bool con = coap_header_get_type(req) == COAP_TYPE_CON;

	return coap_packet_init(rsp, buf, size, COAP_VERSION_1,
				con ? COAP_TYPE_ACK : COAP_TYPE_NON_CON, tkl, token, code,
				con ? coap_header_get_id(req) : coap_next_id());
}

const char *peer_str(const struct net_sockaddr *addr, char *buf, size_t size)
{
	return net_addr_ntop(NET_AF_INET6, &net_sin6(addr)->sin6_addr, buf, size);
}

int main(void)
{
	if (!device_is_ready(strip)) {
		LOG_ERR("LED strip device not ready");
	} else {
		k_work_submit(&led_work);
		openthread_state_changed_callback_register(&ot_state_cb);
	}

	LOG_INF("SoilSense node ready: CoAP /env/temp and /act/valve on UDP %u. "
		"OpenThread commands start with \"ot\".", coap_port);

	return 0;
}
