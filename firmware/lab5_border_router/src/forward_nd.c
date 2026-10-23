#include <errno.h>
#include <zephyr/net/net_core.h>
#include <zephyr/net/net_pkt.h>

/* Zephyr forwards a packet only to a next hop that is already in the neighbor
 * cache. A reply from the mesh to a Wi-Fi host the Border Router has never
 * talked to is dropped ("Cannot find ... neighbor"): a laptop's ping or CoAP
 * request reaches the node, but the answer never comes back. Sending it through
 * the normal output path instead makes Neighbor Discovery resolve the host and
 * queue the packet until it answers.
 */
int net_route_ipv6_decrement_hop_limit(struct net_pkt *pkt);
int __real_net_route_ipv6_packet(struct net_pkt *pkt, const struct net_in6_addr *nexthop);

int __wrap_net_route_ipv6_packet(struct net_pkt *pkt, const struct net_in6_addr *nexthop)
{
	int ret = __real_net_route_ipv6_packet(pkt, nexthop);

	if (ret != -ENOENT) {
		return ret;
	}

	if (net_pkt_forwarding(pkt)) {
		ret = net_route_ipv6_decrement_hop_limit(pkt);
		if (ret < 0) {
			return ret;
		}
	}

	(void)net_linkaddr_copy(net_pkt_lladdr_src(pkt), net_pkt_lladdr_if(pkt));
	(void)net_linkaddr_clear(net_pkt_lladdr_dst(pkt));

	return net_send_data(pkt);
}
