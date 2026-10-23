#ifndef APP_H_
#define APP_H_

#include <stdbool.h>
#include <stdint.h>
#include <zephyr/net/coap.h>
#include <zephyr/net/coap_service.h>

void led_show_valve(bool open);

/* Start a response to req: piggybacked ACK for a CON request, NON otherwise */
int response_init(struct coap_packet *rsp, uint8_t *buf, size_t size,
		  const struct coap_packet *req, uint8_t code);

/* Peer address as text, for logs */
const char *peer_str(const struct net_sockaddr *addr, char *buf, size_t size);

/* Last reading that passed the plausibility checks */
struct reading {
	bool valid;     /* false until the first accepted reading */
	float t;        /* °C */
	int64_t at_ms;  /* uptime when it was taken */
	uint32_t seq;   /* increments with every accepted reading */
};

struct reading reading_get(void);

/* Name of the sensor in the devicetree, or "simulated" */
const char *reading_sensor_name(void);

/* Failed DTLS handshakes since boot (dtls_stats.c) */
uint32_t dtls_handshakes_failed(void);

/* Answers 4.29 when the peer is over its request budget: 0 when the request may
 * go on, 1 when the 4.29 was sent, negative on error (rate_limit.c)
 */
int rate_limit_check(struct coap_resource *res, const struct coap_packet *req,
		     struct net_sockaddr *addr, net_socklen_t addr_len);

/* Task watchdog (watchdog.c) */
int watchdog_start(void);
void watchdog_feed_sampler(void);

#endif
