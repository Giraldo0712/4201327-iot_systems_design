/* /act/valve: irrigation valve (the board's LED), state as CBOR {"v": 0|1}.
 * PUT sets it, GET reads it. The OpenThread shell can't send binary payloads,
 * so a request without a Content-Format may carry the text "0" or "1" instead.
 *
 * Fail-safe: water flowing is the dangerous state. With the valve open and no
 * neighbour at all (detached, or a router left alone) for CONFIG_LAB_FAILSAFE_S
 * seconds, the valve closes itself.
 */
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/net/coap_service.h>
#include <zephyr/sys/util.h>
#include <zcbor_decode.h>
#include <zcbor_encode.h>
#include <openthread.h>
#include <openthread/thread.h>

#include "app.h"

LOG_MODULE_REGISTER(valve, LOG_LEVEL_INF);

static atomic_t valve_open;

/* A1 61 76 0X = {"v": X} */
static size_t encode_state(bool open, uint8_t *buf, size_t size)
{
	ZCBOR_STATE_E(zs, 1, buf, size, 1);

	if (!(zcbor_map_start_encode(zs, 1) && zcbor_tstr_put_lit(zs, "v") &&
	      zcbor_uint32_put(zs, open) && zcbor_map_end_encode(zs, 1))) {
		return 0;
	}

	return zs->payload - buf;
}

static int decode_command(const struct coap_packet *req, bool *open)
{
	uint16_t len;
	const uint8_t *p = coap_packet_get_payload(req, &len);
	int format = coap_get_option_int(req, COAP_OPTION_CONTENT_FORMAT);

	if (p == NULL || len == 0) {
		return -EINVAL;
	}

	if (format == COAP_CONTENT_FORMAT_APP_CBOR) {
		ZCBOR_STATE_D(zs, 1, p, len, 1, 0);
		uint32_t v;

		if (!(zcbor_map_start_decode(zs) && zcbor_tstr_expect_lit(zs, "v") &&
		      zcbor_uint32_decode(zs, &v) && zcbor_map_end_decode(zs)) || v > 1) {
			return -EINVAL;
		}
		*open = v;
		return 0;
	}

	if ((format < 0 || format == COAP_CONTENT_FORMAT_TEXT_PLAIN) && len == 1 &&
	    (p[0] == '0' || p[0] == '1')) {
		*open = p[0] == '1';
		return 0;
	}

	return -EINVAL;
}

static int reply_state(struct coap_resource *res, const struct coap_packet *req,
		       struct net_sockaddr *addr, net_socklen_t addr_len, uint8_t code,
		       uint16_t *size)
{
	uint8_t buf[CONFIG_COAP_SERVER_MESSAGE_SIZE];
	uint8_t cbor[4];
	size_t n = encode_state(atomic_get(&valve_open), cbor, sizeof(cbor));
	struct coap_packet rsp;
	int r;

	r = response_init(&rsp, buf, sizeof(buf), req, code);
	if (r == 0) {
		r = coap_append_option_int(&rsp, COAP_OPTION_CONTENT_FORMAT,
					   COAP_CONTENT_FORMAT_APP_CBOR);
	}
	if (r == 0) {
		r = coap_packet_append_payload_marker(&rsp);
	}
	if (r == 0) {
		r = coap_packet_append_payload(&rsp, cbor, n);
	}
	if (r < 0) {
		return r;
	}
	*size = rsp.offset;

	return coap_resource_send(res, &rsp, addr, addr_len, NULL);
}

static int valve_put(struct coap_resource *res, struct coap_packet *req,
		     struct net_sockaddr *addr, net_socklen_t addr_len)
{
	char peer[NET_IPV6_ADDR_LEN];
	bool was_open = atomic_get(&valve_open);
	bool open;
	uint16_t size = 0;
	int r = rate_limit_check(res, req, addr, addr_len);

	if (r != 0) {
		return r < 0 ? r : 0;
	}
	peer_str(addr, peer, sizeof(peer));

	if (decode_command(req, &open) < 0) {
		LOG_WRN("PUT /act/valve from %s: payload not {\"v\": 0|1} or \"0\"/\"1\" -> 4.00",
			peer);
		/* A positive return makes the server ACK a CON request with this code */
		return COAP_RESPONSE_CODE_BAD_REQUEST;
	}

	atomic_set(&valve_open, open);
	led_show_valve(open);
	r = reply_state(res, req, addr, addr_len, COAP_RESPONSE_CODE_CHANGED, &size);
	LOG_INF("PUT /act/valve from %s (%s): %s%s -> 2.04, CoAP %u B, request %u B", peer,
		coap_header_get_type(req) == COAP_TYPE_CON ? "CON" : "NON",
		open ? "OPEN" : "CLOSED", open == was_open ? ", no change" : "", size,
		req->max_len);

	return r;
}

static int valve_get(struct coap_resource *res, struct coap_packet *req,
		     struct net_sockaddr *addr, net_socklen_t addr_len)
{
	char peer[NET_IPV6_ADDR_LEN];
	uint16_t size = 0;
	int r = rate_limit_check(res, req, addr, addr_len);

	if (r != 0) {
		return r < 0 ? r : 0;
	}
	r = reply_state(res, req, addr, addr_len, COAP_RESPONSE_CODE_CONTENT, &size);
	LOG_INF("GET /act/valve from %s: %s -> 2.05, CoAP %u B, request %u B",
		peer_str(addr, peer, sizeof(peer)), atomic_get(&valve_open) ? "OPEN" : "CLOSED", size,
		req->max_len);

	return r;
}

static const char *const valve_path[] = { "act", "valve", NULL };
COAP_RESOURCE_DEFINE(valve, soilsense, {
	.get = valve_get,
	.put = valve_put,
	.path = valve_path,
});

/* No neighbour at all: detached or disabled, or a router whose every link died */
static bool isolated(void)
{
	otInstance *ot = openthread_get_default_instance();
	otNeighborInfoIterator it = OT_NEIGHBOR_INFO_ITERATOR_INIT;
	otNeighborInfo info;
	bool alone;

	openthread_mutex_lock();
	switch (otThreadGetDeviceRole(ot)) {
	case OT_DEVICE_ROLE_CHILD:
		alone = false;
		break;
	case OT_DEVICE_ROLE_ROUTER:
	case OT_DEVICE_ROLE_LEADER:
		alone = otThreadGetNextNeighborInfo(ot, &it, &info) != OT_ERROR_NONE;
		break;
	default:
		alone = true;
	}
	openthread_mutex_unlock();

	return alone;
}

static void failsafe(struct k_work *work)
{
	static int64_t alone_since_ms;
	int64_t now = k_uptime_get();

	if (!isolated()) {
		alone_since_ms = 0;
	} else if (alone_since_ms == 0) {
		alone_since_ms = now;
	} else if (atomic_get(&valve_open) &&
		   now - alone_since_ms >= CONFIG_LAB_FAILSAFE_S * MSEC_PER_SEC) {
		atomic_set(&valve_open, false);
		led_show_valve(false);
		LOG_WRN("FAILSAFE: no neighbour for %lld s with the valve open: closing it",
			(now - alone_since_ms) / MSEC_PER_SEC);
	}
	k_work_schedule(k_work_delayable_from_work(work), K_SECONDS(1));
}

static K_WORK_DELAYABLE_DEFINE(failsafe_work, failsafe);

static int failsafe_init(void)
{
	k_work_schedule(&failsafe_work, K_SECONDS(1));
	return 0;
}

SYS_INIT(failsafe_init, APPLICATION, CONFIG_APPLICATION_INIT_PRIORITY);
