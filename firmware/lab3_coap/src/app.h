#ifndef APP_H_
#define APP_H_

#include <stdbool.h>
#include <zephyr/net/coap.h>

void led_show_valve(bool open);

/* Start a response to req: piggybacked ACK for a CON request, NON otherwise */
int response_init(struct coap_packet *rsp, uint8_t *buf, size_t size,
		  const struct coap_packet *req, uint8_t code);

/* Peer address as text, for logs */
const char *peer_str(const struct net_sockaddr *addr, char *buf, size_t size);

#endif
