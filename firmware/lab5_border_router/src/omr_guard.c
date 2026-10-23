#include <openthread/instance.h>
#include <openthread/ip6.h>
#include <openthread/thread.h>

/* Zephyr's infra_if.c reads every Router Advertisement this Border Router
 * sends on Wi-Fi and, for each Route Information Option, installs a route to
 * that prefix through the Thread interface, using get_ot_slaac_address() as the
 * next hop. That lookup returns NULL until the Border Router has an address on
 * its own OMR prefix, and infra_if.c dereferences it: the board crashes as soon
 * as Wi-Fi comes up, and later, when the prefix changes, the route is lost.
 * The next hop only selects the Thread interface, so the mesh-local EID serves
 * just as well.
 */
const otIp6Address *__real_get_ot_slaac_address(otInstance *instance);

const otIp6Address *__wrap_get_ot_slaac_address(otInstance *instance)
{
	const otIp6Address *addr = __real_get_ot_slaac_address(instance);

	return addr != NULL ? addr : otThreadGetMeshLocalEid(instance);
}
