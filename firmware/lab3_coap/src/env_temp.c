/* /env/temp: air temperature as CBOR {"t": float16}, readable with GET and
 * pushed to observers (RFC 7641) when it moves more than THRESHOLD_C, or every
 * HEARTBEAT_S seconds if it doesn't.
 */
#include <math.h>
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/net/coap_service.h>
#include <zephyr/random/random.h>
#include <zephyr/sys/util.h>
#include <zcbor_encode.h>

#include "app.h"

LOG_MODULE_REGISTER(env_temp, LOG_LEVEL_INF);

#define THRESHOLD_C 0.5f
#define HEARTBEAT_S 45
#define MAX_AGE_S   60

static float temp_c = 24.5f;
static float last_notified_c = 24.5f;
static int64_t last_notify_ms;
static uint8_t notify_type = COAP_TYPE_NON_CON;
static uint32_t n_threshold, n_heartbeat;

/* A1 61 74 F9 hh ll = {"t": <half-precision float>} */
static size_t encode_reading(float t, uint8_t *buf, size_t size)
{
	ZCBOR_STATE_E(zs, 0, buf, size, 1);

	if (!(zcbor_map_start_encode(zs, 1) && zcbor_tstr_put_lit(zs, "t") &&
	      zcbor_float16_put(zs, t) && zcbor_map_end_encode(zs, 1))) {
		return 0;
	}

	return zs->payload - buf;
}

/* Options must be appended in option-number order: Observe (6),
 * Content-Format (12), Max-Age (14).
 */
static int build_reading(struct coap_packet *pkt, bool observe, int seq)
{
	uint8_t cbor[8];
	size_t n = encode_reading(temp_c, cbor, sizeof(cbor));
	int r = 0;

	if (observe) {
		r = coap_append_option_int(pkt, COAP_OPTION_OBSERVE, seq);
	}
	if (r == 0) {
		r = coap_append_option_int(pkt, COAP_OPTION_CONTENT_FORMAT,
					   COAP_CONTENT_FORMAT_APP_CBOR);
	}
	if (r == 0) {
		r = coap_append_option_int(pkt, COAP_OPTION_MAX_AGE, MAX_AGE_S);
	}
	if (r == 0) {
		r = coap_packet_append_payload_marker(pkt);
	}
	if (r == 0) {
		r = coap_packet_append_payload(pkt, cbor, n);
	}

	return r;
}

static int env_temp_get(struct coap_resource *res, struct coap_packet *req,
			struct net_sockaddr *addr, net_socklen_t addr_len)
{
	uint8_t buf[CONFIG_COAP_SERVER_MESSAGE_SIZE];
	struct coap_packet rsp;
	char peer[NET_IPV6_ADDR_LEN];
	char hex[2 * 8 + 1];
	uint16_t len;
	const uint8_t *payload;
	int obs = coap_resource_parse_observe(res, req, addr);
	int r;

	r = response_init(&rsp, buf, sizeof(buf), req, COAP_RESPONSE_CODE_CONTENT);
	if (r == 0) {
		r = build_reading(&rsp, obs == 0, res->age);
	}
	if (r < 0) {
		return r;
	}

	if (obs == 0) {
		/* Count the next notification from this reading */
		last_notified_c = temp_c;
		last_notify_ms = k_uptime_get();
	}

	payload = coap_packet_get_payload(&rsp, &len);
	bin2hex(payload, len, hex, sizeof(hex));
	LOG_INF("GET /env/temp from %s%s: 2.05, %.2f C, CoAP %u B (CBOR %s), request %u B",
		peer_str(addr, peer, sizeof(peer)),
		obs == 0 ? " (observe)" : obs == 1 ? " (cancel)" : "",
		(double)temp_c, rsp.offset, hex, req->max_len);

	return coap_resource_send(res, &rsp, addr, addr_len, NULL);
}

static void env_temp_notify(struct coap_resource *res, struct coap_observer *obs)
{
	uint8_t buf[CONFIG_COAP_SERVER_MESSAGE_SIZE];
	struct coap_packet pkt;
	int r;

	r = coap_packet_init(&pkt, buf, sizeof(buf), COAP_VERSION_1, notify_type, obs->tkl,
			     obs->token, COAP_RESPONSE_CODE_CONTENT, coap_next_id());
	if (r == 0) {
		r = build_reading(&pkt, true, res->age);
	}
	if (r == 0) {
		r = coap_resource_send(res, &pkt, net_sad(&obs->addr),
				       net_family2size(obs->addr.ss_family), NULL);
	}
	if (r < 0) {
		LOG_WRN("Notification failed (%d)", r);
	}
}

static const char *const env_temp_path[] = { "env", "temp", NULL };
COAP_RESOURCE_DEFINE(env_temp, soilsense, {
	.get = env_temp_get,
	.path = env_temp_path,
	.notify = env_temp_notify,
});

/* Simulated sensor: 24.5 °C ± 1 °C over a 60 s period, plus ±0.1 °C noise.
 * Lab 4 replaces it with a real one.
 */
static void sample(struct k_work *work)
{
	int64_t now = k_uptime_get();
	float noise = (int32_t)(sys_rand32_get() % 201 - 100) / 1000.0f;
	float delta;
	bool threshold, heartbeat;

	temp_c = 24.5f + sinf(2.0f * 3.14159265f * (float)(now % 60000) / 60000.0f) + noise;
	delta = fabsf(temp_c - last_notified_c);
	threshold = delta > THRESHOLD_C;
	heartbeat = now - last_notify_ms >= HEARTBEAT_S * MSEC_PER_SEC;

	if ((threshold || heartbeat) && !sys_slist_is_empty(&env_temp.observers)) {
		/* Heartbeats go CON: if the observer is gone, the retransmissions
		 * fail and the server drops it (RFC 7641 §4.5).
		 */
		notify_type = threshold ? COAP_TYPE_NON_CON : COAP_TYPE_CON;
		if (threshold) {
			n_threshold++;
		} else {
			n_heartbeat++;
		}
		LOG_INF("notify (%s, %s): T=%.2f C, delta=%.2f C, %llds since last "
			"[threshold %u, heartbeat %u]",
			threshold ? "threshold" : "heartbeat", threshold ? "NON" : "CON",
			(double)temp_c, (double)delta, (now - last_notify_ms) / MSEC_PER_SEC,
			n_threshold, n_heartbeat);
		last_notified_c = temp_c;
		last_notify_ms = now;
		coap_resource_notify(&env_temp);
	}

	k_work_schedule(k_work_delayable_from_work(work), K_SECONDS(1));
}

static K_WORK_DELAYABLE_DEFINE(sample_work, sample);

static int env_temp_init(void)
{
	last_notify_ms = k_uptime_get();
	k_work_schedule(&sample_work, K_SECONDS(1));
	return 0;
}

SYS_INIT(env_temp_init, APPLICATION, CONFIG_APPLICATION_INIT_PRIORITY);
