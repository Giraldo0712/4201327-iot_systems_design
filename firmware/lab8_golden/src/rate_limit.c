/* Per-peer rate limiting: each client may send CONFIG_LAB_RATE_LIMIT_MAX
 * requests per CONFIG_LAB_RATE_LIMIT_WINDOW_S window; more are answered
 * 4.29 Too Many Requests (RFC 8516), with Max-Age = seconds until the window
 * reopens. A few slots track the most recent peers; the stalest is reused.
 * Observe notifications don't pass through here: only requests do.
 */
#include <string.h>
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/net/coap_service.h>

#include "app.h"

LOG_MODULE_REGISTER(rate_limit, LOG_LEVEL_INF);

#define SLOTS 4
#define WINDOW_MS (CONFIG_LAB_RATE_LIMIT_WINDOW_S * MSEC_PER_SEC)

static struct {
	struct net_in6_addr peer;
	int64_t window_start_ms;
	uint32_t count;
} slots[SLOTS];

static K_MUTEX_DEFINE(lock);

/* Milliseconds until this peer may send again; 0 when the request is allowed */
static int64_t over_limit(const struct net_sockaddr *addr)
{
	const struct net_in6_addr *peer = &net_sin6(addr)->sin6_addr;
	int64_t now = k_uptime_get();
	int64_t wait = 0;
	int i, stalest = 0;

	k_mutex_lock(&lock, K_FOREVER);
	for (i = 0; i < SLOTS; i++) {
		if (memcmp(&slots[i].peer, peer, sizeof(*peer)) == 0) {
			break;
		}
		if (slots[i].window_start_ms < slots[stalest].window_start_ms) {
			stalest = i;
		}
	}
	if (i == SLOTS) {
		i = stalest;
		slots[i].peer = *peer;
		slots[i].window_start_ms = now;
		slots[i].count = 0;
	}
	if (now - slots[i].window_start_ms >= WINDOW_MS) {
		slots[i].window_start_ms = now;
		slots[i].count = 0;
	}
	if (++slots[i].count > CONFIG_LAB_RATE_LIMIT_MAX) {
		wait = slots[i].window_start_ms + WINDOW_MS - now;
	}
	k_mutex_unlock(&lock);

	return wait;
}

int rate_limit_check(struct coap_resource *res, const struct coap_packet *req,
		     struct net_sockaddr *addr, net_socklen_t addr_len)
{
	int64_t wait_ms = over_limit(addr);
	uint8_t buf[64];
	struct coap_packet rsp;
	char peer[NET_IPV6_ADDR_LEN];
	int r;

	if (wait_ms == 0) {
		return 0;
	}

	r = response_init(&rsp, buf, sizeof(buf), req, COAP_RESPONSE_CODE_TOO_MANY_REQUESTS);
	if (r == 0) {
		r = coap_append_option_int(&rsp, COAP_OPTION_MAX_AGE,
					   DIV_ROUND_UP(wait_ms, MSEC_PER_SEC));
	}
	if (r == 0) {
		r = coap_resource_send(res, &rsp, addr, addr_len, NULL);
	}
	LOG_WRN("4.29 to %s: over %d requests in %d s, retry in %lld s",
		peer_str(addr, peer, sizeof(peer)), CONFIG_LAB_RATE_LIMIT_MAX,
		CONFIG_LAB_RATE_LIMIT_WINDOW_S, DIV_ROUND_UP(wait_ms, MSEC_PER_SEC));

	return r < 0 ? r : 1;
}
