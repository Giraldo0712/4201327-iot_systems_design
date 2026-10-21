#ifndef APP_H_
#define APP_H_

#include <stdbool.h>
#include <stdint.h>
#include <zephyr/net/coap.h>

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

#endif
