#include <zephyr/logging/log.h>

LOG_MODULE_REGISTER(lab1_radio, LOG_LEVEL_INF);

int main(void)
{
	LOG_INF("802.15.4 radio ready. OpenThread commands start with \"ot\".");

	return 0;
}
