/* /env/temp: temperature as CBOR {"t": float16}, readable with GET and pushed
 * to observers (RFC 7641) when it moves more than THRESHOLD_C, or every
 * HEARTBEAT_S seconds if it doesn't. A reading is served for at most MAX_AGE_S
 * after it was taken: Max-Age counts down as it ages, and once no accepted
 * reading is that recent, GET answers 5.03 and every observation ends with a
 * 5.03 notification.
 */
#include <math.h>
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/net/coap_service.h>
#include <zephyr/sys/util.h>
#include <zcbor_encode.h>

#include "app.h"

LOG_MODULE_REGISTER(env_temp, LOG_LEVEL_INF);

#define THRESHOLD_C 0.5f
#define HEARTBEAT_S 45
#define MAX_AGE_S   60
#define RETRY_S     10  /* Max-Age of a 5.03: when the client may ask again */

static const char unavailable_msg[] = "no fresh reading";

static float last_notified_c;
static int64_t last_notify_ms;
static uint8_t notify_type = COAP_TYPE_NON_CON;
static bool fresh, been_fresh;
static uint32_t n_threshold, n_heartbeat;
static uint16_t notify_size;

/* Observations being ended with a 5.03, collected while notifying */
static bool ending;
static struct {
	uint8_t token[COAP_TOKEN_MAX_LEN];
	uint8_t tkl;
} ended[CONFIG_COAP_SERVICE_OBSERVERS];
static int n_ended;

/* Seconds the reading stays fresh; 0 once it is too old to serve */
static uint32_t freshness_s(const struct reading *r, int64_t now)
{
	int64_t age_s;

	if (!r->valid) {
		return 0;
	}
	age_s = (now - r->at_ms) / MSEC_PER_SEC;

	return age_s < MAX_AGE_S ? MAX_AGE_S - age_s : 0;
}

/* A1 61 74 F9 hh ll = {"t": <half-precision float>} */
static size_t encode_reading(float t, uint8_t *buf, size_t size)
{
	ZCBOR_STATE_E(zs, 1, buf, size, 1);

	if (!(zcbor_map_start_encode(zs, 1) && zcbor_tstr_put_lit(zs, "t") &&
	      zcbor_float16_put(zs, t) && zcbor_map_end_encode(zs, 1))) {
		return 0;
	}

	return zs->payload - buf;
}

/* Options must be appended in option-number order: Observe (6),
 * Content-Format (12), Max-Age (14).
 */
static int build_reading(struct coap_packet *pkt, bool observe, int seq, const uint8_t *cbor,
			 size_t n, uint32_t max_age)
{
	int r = 0;

	if (n == 0) {
		return -ENOMEM;
	}
	if (observe) {
		r = coap_append_option_int(pkt, COAP_OPTION_OBSERVE, seq);
	}
	if (r == 0) {
		r = coap_append_option_int(pkt, COAP_OPTION_CONTENT_FORMAT,
					   COAP_CONTENT_FORMAT_APP_CBOR);
	}
	if (r == 0) {
		r = coap_append_option_int(pkt, COAP_OPTION_MAX_AGE, max_age);
	}
	if (r == 0) {
		r = coap_packet_append_payload_marker(pkt);
	}
	if (r == 0) {
		r = coap_packet_append_payload(pkt, cbor, n);
	}

	return r;
}

/* 5.03 with Max-Age = when to retry, and a diagnostic text payload. Error
 * responses carry no Observe option (RFC 7641 §4.2), which is what ends an
 * observation on the client.
 */
static int build_unavailable(struct coap_packet *pkt)
{
	int r = coap_append_option_int(pkt, COAP_OPTION_MAX_AGE, RETRY_S);

	if (r == 0) {
		r = coap_packet_append_payload_marker(pkt);
	}
	if (r == 0) {
		r = coap_packet_append_payload(pkt, unavailable_msg, sizeof(unavailable_msg) - 1);
	}

	return r;
}

static int env_temp_get(struct coap_resource *res, struct coap_packet *req,
			struct net_sockaddr *addr, net_socklen_t addr_len)
{
	uint8_t buf[CONFIG_COAP_SERVER_MESSAGE_SIZE];
	struct coap_packet rsp;
	char peer[NET_IPV6_ADDR_LEN];
	uint8_t cbor[8];
	size_t n;
	char hex[2 * sizeof(cbor) + 1];
	struct reading reading = reading_get();
	int64_t now = k_uptime_get();
	uint32_t max_age = freshness_s(&reading, now);
	int obs, r;

	peer_str(addr, peer, sizeof(peer));

	if (max_age == 0) {
		r = response_init(&rsp, buf, sizeof(buf), req,
				  COAP_RESPONSE_CODE_SERVICE_UNAVAILABLE);
		if (r == 0) {
			r = build_unavailable(&rsp);
		}
		if (r < 0) {
			return r;
		}
		LOG_WRN("GET /env/temp from %s: 5.03, no reading younger than %d s, retry in %d s",
			peer, MAX_AGE_S, RETRY_S);
		return coap_resource_send(res, &rsp, addr, addr_len, NULL);
	}

	obs = coap_resource_parse_observe(res, req, addr);
	n = encode_reading(reading.t, cbor, sizeof(cbor));
	r = response_init(&rsp, buf, sizeof(buf), req, COAP_RESPONSE_CODE_CONTENT);
	if (r == 0) {
		r = build_reading(&rsp, obs == 0, res->age, cbor, n, max_age);
	}
	if (r < 0) {
		return r;
	}

	if (obs == 0) {
		/* Count the next notification from this reading */
		last_notified_c = reading.t;
		last_notify_ms = now;
	}

	bin2hex(cbor, n, hex, sizeof(hex));
	LOG_INF("GET /env/temp from %s%s: 2.05, %.2f C, %llds old, Max-Age %u (CBOR %s)", peer,
		obs == 0 ? " (observe)" : obs == 1 ? " (cancel)" : "", (double)reading.t,
		(now - reading.at_ms) / MSEC_PER_SEC, max_age, hex);

	return coap_resource_send(res, &rsp, addr, addr_len, NULL);
}

static void env_temp_notify(struct coap_resource *res, struct coap_observer *obs)
{
	uint8_t buf[CONFIG_COAP_SERVER_MESSAGE_SIZE];
	struct coap_packet pkt;
	struct reading reading = reading_get();
	uint8_t code = ending ? COAP_RESPONSE_CODE_SERVICE_UNAVAILABLE
			      : COAP_RESPONSE_CODE_CONTENT;
	int r;

	r = coap_packet_init(&pkt, buf, sizeof(buf), COAP_VERSION_1, notify_type, obs->tkl,
			     obs->token, code, coap_next_id());
	if (r == 0 && ending) {
		r = build_unavailable(&pkt);
		if (n_ended < ARRAY_SIZE(ended)) {
			memcpy(ended[n_ended].token, obs->token, obs->tkl);
			ended[n_ended++].tkl = obs->tkl;
		}
	} else if (r == 0) {
		uint8_t cbor[8];
		size_t n = encode_reading(reading.t, cbor, sizeof(cbor));

		r = build_reading(&pkt, true, res->age, cbor, n,
				  freshness_s(&reading, k_uptime_get()));
	}
	if (r == 0) {
		notify_size = pkt.offset;
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

/* Tell every observer the data is gone (CON, so a vanished one is noticed),
 * then forget them: a client re-registers once readings are fresh again.
 */
static void end_observations(void)
{
	ending = true;
	notify_type = COAP_TYPE_CON;
	n_ended = 0;
	coap_resource_notify(&env_temp);
	ending = false;

	for (int i = 0; i < n_ended; i++) {
		coap_resource_remove_observer_by_token(&env_temp, ended[i].token, ended[i].tkl);
	}
	LOG_WRN("No reading younger than %d s: GET now answers 5.03; %d observation(s) ended",
		MAX_AGE_S, n_ended);
}

/* Observe policy, once a second: notify on a change or a heartbeat while the
 * data is fresh, and end the observations when it stops being fresh.
 */
static void policy(struct k_work *work)
{
	struct reading reading = reading_get();
	int64_t now = k_uptime_get();
	uint32_t max_age = freshness_s(&reading, now);
	float delta;
	bool threshold, heartbeat;

	if ((max_age > 0) != fresh) {
		fresh = max_age > 0;
		if (fresh) {
			if (been_fresh) {
				LOG_INF("Fresh readings again: GET answers 2.05; observers must "
					"register again");
			}
			been_fresh = true;
			last_notified_c = reading.t;
			last_notify_ms = now;
		} else {
			end_observations();
		}
	}

	if (fresh && !sys_slist_is_empty(&env_temp.observers)) {
		delta = fabsf(reading.t - last_notified_c);
		threshold = delta > THRESHOLD_C;
		heartbeat = now - last_notify_ms >= HEARTBEAT_S * MSEC_PER_SEC;

		if (threshold || heartbeat) {
			/* Heartbeats go CON: if the observer is gone, the retransmissions
			 * fail and the server drops it (RFC 7641 §4.5).
			 */
			notify_type = threshold ? COAP_TYPE_NON_CON : COAP_TYPE_CON;
			if (threshold) {
				n_threshold++;
			} else {
				n_heartbeat++;
			}
			int64_t since_ms = now - last_notify_ms;

			last_notified_c = reading.t;
			last_notify_ms = now;
			coap_resource_notify(&env_temp);
			LOG_INF("notify (%s, %s): T=%.2f C, delta=%.2f C, %llds since last, "
				"reading %llds old, CoAP %u B [threshold %u, heartbeat %u]",
				threshold ? "threshold" : "heartbeat", threshold ? "NON" : "CON",
				(double)reading.t, (double)delta, since_ms / MSEC_PER_SEC,
				(now - reading.at_ms) / MSEC_PER_SEC, notify_size, n_threshold,
				n_heartbeat);
		}
	}

	k_work_schedule(k_work_delayable_from_work(work), K_SECONDS(1));
}

static K_WORK_DELAYABLE_DEFINE(policy_work, policy);

static int env_temp_init(void)
{
	last_notify_ms = k_uptime_get();
	k_work_schedule(&policy_work, K_SECONDS(1));
	return 0;
}

SYS_INIT(env_temp_init, APPLICATION, CONFIG_APPLICATION_INIT_PRIORITY);
