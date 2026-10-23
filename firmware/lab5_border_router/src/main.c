/* The Border Router starts by itself once Wi-Fi is up and the Thread network
 * is formed; everything in Lab 5 happens on the shell.
 *
 * Lab 8 builds with autostart.conf (CONFIG_LAB_AUTOSTART): the Thread network
 * and the Wi-Fi credentials stay in flash, and both are rejoined at boot, so a
 * power cut needs nobody at the console.
 */
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>

#if defined(CONFIG_LAB_AUTOSTART)
#include <zephyr/net/net_if.h>
#include <zephyr/net/net_mgmt.h>
#include <zephyr/net/wifi_credentials.h>
#include <zephyr/net/wifi_mgmt.h>
#include <openthread.h>
#include <openthread/dataset.h>

LOG_MODULE_REGISTER(lab5_border_router, LOG_LEVEL_INF);

static void autostart(void)
{
	struct net_if *wifi = net_if_get_first_wifi();
	bool stored;

	if (wifi != NULL && !wifi_credentials_is_empty()) {
		LOG_INF("Connecting to the stored Wi-Fi network");
		(void)net_mgmt(NET_REQUEST_WIFI_CONNECT_STORED, wifi, NULL, 0);
	} else {
		LOG_INF("No Wi-Fi network stored: add one with \"wifi cred add\"");
	}

	openthread_mutex_lock();
	stored = otDatasetIsCommissioned(openthread_get_default_instance());
	openthread_mutex_unlock();
	if (stored && openthread_run() == 0) {
		LOG_INF("Rejoining the stored Thread network");
	} else if (!stored) {
		LOG_INF("No Thread network stored: form one (SOP-05 §2)");
	}
}
#endif

int main(void)
{
#if defined(CONFIG_LAB_AUTOSTART)
	autostart();
#endif
	return 0;
}
