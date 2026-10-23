/* /sys/health: the node's own health, for operations, as CBOR
 * {"batt": mV, "rssi": dBm, "up": s, "hsfail": n, "ver": "x.y.z"}. GET it, or observe it for a
 * CON notification every report period. "health" in the shell prints the same
 * values and changes the period.
 *
 * The battery is simulated, since these boards run from USB: it starts at
 * 3300 mV and loses 1 mV a minute. "health batt <mV>" sets it, to rehearse a
 * low-battery alert.
 */
#include <stdlib.h>
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/net/coap_service.h>
#include <zephyr/shell/shell.h>
#include <zephyr/app_version.h>
#include <zephyr/sys/util.h>
#include <zcbor_encode.h>
#include <openthread.h>
#include <openthread/thread.h>

#include "app.h"

LOG_MODULE_REGISTER(health, LOG_LEVEL_INF);

#define NO_LINK_DBM (-127)

static uint32_t period_s = CONFIG_LAB_HEALTH_PERIOD_S;
static int32_t batt_start_mv = 3300;
static int64_t batt_start_ms;
static int64_t last_notify_ms;
static uint16_t notify_size;

static uint32_t batt_mv(void)
{
	int64_t drop = (k_uptime_get() - batt_start_ms) / (60 * MSEC_PER_SEC);

	return MAX(batt_start_mv - drop, 0);
}

/* Average RSSI of the link this node depends on: its parent if it is a
 * child, otherwise its strongest neighbouring router.
 */
static int8_t link_rssi(void)
{
	otInstance *ot = openthread_get_default_instance();
	int8_t best = NO_LINK_DBM;

	openthread_mutex_lock();
	if (otThreadGetDeviceRole(ot) == OT_DEVICE_ROLE_CHILD) {
		(void)otThreadGetParentAverageRssi(ot, &best);
	} else {
		otNeighborInfoIterator it = OT_NEIGHBOR_INFO_ITERATOR_INIT;
		otNeighborInfo info;

		while (otThreadGetNextNeighborInfo(ot, &it, &info) == OT_ERROR_NONE) {
			if (!info.mIsChild && info.mAverageRssi > best) {
				best = info.mAverageRssi;
			}
		}
	}
	openthread_mutex_unlock();

	return best;
}

static size_t encode_health(uint8_t *buf, size_t size)
{
	ZCBOR_STATE_E(zs, 1, buf, size, 1);

	if (!(zcbor_map_start_encode(zs, 5) &&
	      zcbor_tstr_put_lit(zs, "batt") && zcbor_uint32_put(zs, batt_mv()) &&
	      zcbor_tstr_put_lit(zs, "rssi") && zcbor_int32_put(zs, link_rssi()) &&
	      zcbor_tstr_put_lit(zs, "up") && zcbor_uint32_put(zs, k_uptime_get() / MSEC_PER_SEC) &&
	      zcbor_tstr_put_lit(zs, "hsfail") && zcbor_uint32_put(zs, dtls_handshakes_failed()) &&
	      zcbor_tstr_put_lit(zs, "ver") && zcbor_tstr_put_lit(zs, APP_VERSION_STRING) &&
	      zcbor_map_end_encode(zs, 5))) {
		return 0;
	}

	return zs->payload - buf;
}

/* Observe (6), Content-Format (12), Max-Age (14), in option-number order */
static int build_health(struct coap_packet *pkt, bool observe, int seq)
{
	uint8_t cbor[64];
	size_t n = encode_health(cbor, sizeof(cbor));
	int r = n ? 0 : -ENOMEM;

	if (r == 0 && observe) {
		r = coap_append_option_int(pkt, COAP_OPTION_OBSERVE, seq);
	}
	if (r == 0) {
		r = coap_append_option_int(pkt, COAP_OPTION_CONTENT_FORMAT,
					   COAP_CONTENT_FORMAT_APP_CBOR);
	}
	if (r == 0) {
		r = coap_append_option_int(pkt, COAP_OPTION_MAX_AGE, period_s);
	}
	if (r == 0) {
		r = coap_packet_append_payload_marker(pkt);
	}
	if (r == 0) {
		r = coap_packet_append_payload(pkt, cbor, n);
	}

	return r;
}

static int health_get(struct coap_resource *res, struct coap_packet *req,
		      struct net_sockaddr *addr, net_socklen_t addr_len)
{
	uint8_t buf[CONFIG_COAP_SERVER_MESSAGE_SIZE];
	struct coap_packet rsp;
	char peer[NET_IPV6_ADDR_LEN];
	int obs, r = rate_limit_check(res, req, addr, addr_len);

	if (r != 0) {
		return r < 0 ? r : 0;
	}
	obs = coap_resource_parse_observe(res, req, addr);
	r = response_init(&rsp, buf, sizeof(buf), req, COAP_RESPONSE_CODE_CONTENT);

	if (r == 0) {
		r = build_health(&rsp, obs == 0, res->age);
	}
	if (r < 0) {
		return r;
	}
	if (obs == 0) {
		last_notify_ms = k_uptime_get();  /* this response is the first report */
	}

	LOG_INF("GET /sys/health from %s%s: 2.05, CoAP %u B", peer_str(addr, peer, sizeof(peer)),
		obs == 0 ? " (observe)" : obs == 1 ? " (cancel)" : "", rsp.offset);

	return coap_resource_send(res, &rsp, addr, addr_len, NULL);
}

/* CON, so an observer that vanished is dropped after its retransmissions fail */
static void health_notify(struct coap_resource *res, struct coap_observer *obs)
{
	uint8_t buf[CONFIG_COAP_SERVER_MESSAGE_SIZE];
	struct coap_packet pkt;
	int r = coap_packet_init(&pkt, buf, sizeof(buf), COAP_VERSION_1, COAP_TYPE_CON, obs->tkl,
				 obs->token, COAP_RESPONSE_CODE_CONTENT, coap_next_id());

	if (r == 0) {
		r = build_health(&pkt, true, res->age);
	}
	if (r == 0) {
		notify_size = pkt.offset;
		r = coap_resource_send(res, &pkt, net_sad(&obs->addr),
				       net_family2size(obs->addr.ss_family), NULL);
	}
	if (r < 0) {
		LOG_WRN("Health notification failed (%d)", r);
	}
}

static const char *const health_path[] = { "sys", "health", NULL };
COAP_RESOURCE_DEFINE(sys_health, soilsense, {
	.get = health_get,
	.path = health_path,
	.notify = health_notify,
});

static void report(struct k_work *work)
{
	int64_t now = k_uptime_get();

	if (!sys_slist_is_empty(&sys_health.observers) &&
	    now - last_notify_ms >= (int64_t)period_s * MSEC_PER_SEC) {
		last_notify_ms = now;
		coap_resource_notify(&sys_health);
		LOG_INF("notify /sys/health (CON): CoAP %u B, next in %u s", notify_size, period_s);
	}
	k_work_schedule(k_work_delayable_from_work(work), K_SECONDS(1));
}

static K_WORK_DELAYABLE_DEFINE(report_work, report);

static int health_init(void)
{
	last_notify_ms = k_uptime_get();
	k_work_schedule(&report_work, K_SECONDS(1));
	return 0;
}

SYS_INIT(health_init, APPLICATION, CONFIG_APPLICATION_INIT_PRIORITY);

static int cmd_health(const struct shell *sh, size_t argc, char **argv)
{
	shell_print(sh, "batt:   %u mV (simulated)", batt_mv());
	shell_print(sh, "rssi:   %d dBm", link_rssi());
	shell_print(sh, "up:     %lld s", k_uptime_get() / MSEC_PER_SEC);
	shell_print(sh, "hsfail: %u failed DTLS handshakes", dtls_handshakes_failed());
	shell_print(sh, "period: %u s", period_s);
	shell_print(sh, "ver:    %s", APP_VERSION_STRING);
	return 0;
}

static int cmd_batt(const struct shell *sh, size_t argc, char **argv)
{
	batt_start_mv = atoi(argv[1]);
	batt_start_ms = k_uptime_get();
	shell_print(sh, "Simulated battery set to %d mV", batt_start_mv);
	return 0;
}

static int cmd_period(const struct shell *sh, size_t argc, char **argv)
{
	int s = atoi(argv[1]);

	if (s < 1) {
		shell_error(sh, "The period is at least 1 s");
		return -EINVAL;
	}
	period_s = s;
	shell_print(sh, "Report period %u s", period_s);
	return 0;
}

/* Chaos drill: block the system workqueue, as a hung handler would. The
 * watchdog should reset the node CONFIG_LAB_WATCHDOG_S seconds later.
 */
static void stall(struct k_work *work)
{
	LOG_WRN("Stalling the system workqueue");
	k_sleep(K_FOREVER);
}

static K_WORK_DEFINE(stall_work, stall);

static int cmd_stall(const struct shell *sh, size_t argc, char **argv)
{
	shell_print(sh, "Blocking the system workqueue; the watchdog should reset in %d s",
		    CONFIG_LAB_WATCHDOG_S);
	k_work_submit(&stall_work);
	return 0;
}

SHELL_STATIC_SUBCMD_SET_CREATE(health_cmds,
	SHELL_CMD_ARG(batt, NULL, "Set the simulated battery: <mV>", cmd_batt, 2, 0),
	SHELL_CMD_ARG(period, NULL, "Report period for observers: <s>", cmd_period, 2, 0),
	SHELL_CMD(stall, NULL, "Chaos drill: hang the system workqueue", cmd_stall),
	SHELL_SUBCMD_SET_END);

SHELL_CMD_REGISTER(health, &health_cmds, "Node health: batt, rssi, up, hsfail", cmd_health);
