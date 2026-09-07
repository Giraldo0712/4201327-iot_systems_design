/*
 * Lab 0 - Minimal IoT Implementation (MQTT)
 *
 * Sensing capability:   PUBLISH   iot/sensor  -> {"temperature": 24.5}
 * Actuating capability: SUBSCRIBE iot/control <- {"state": 0|1}
 *
 * Same two capabilities as the HTTP version, but the node is now a client that
 * connects outward to a broker instead of a server waiting to be polled.
 */

#include <zephyr/kernel.h>
#include <zephyr/device.h>
#include <zephyr/data/json.h>
#include <zephyr/drivers/led_strip.h>
#include <zephyr/net/mqtt.h>
#include <zephyr/net/net_event.h>
#include <zephyr/net/net_if.h>
#include <zephyr/net/net_mgmt.h>
#include <zephyr/net/socket.h>
#include <zephyr/net/wifi_mgmt.h>
#include <zephyr/random/random.h>
#include <zephyr/logging/log.h>

#if !defined(CONFIG_WIFI) || !defined(CONFIG_MQTT_LIB) || \
	!defined(CONFIG_JSON_LIBRARY) || !defined(CONFIG_LED_STRIP)
#error "TASK 1 is not done yet: add the four capability symbols to prj.conf. \
The lab guide lists them in section 0."
#endif

#if !defined(CONFIG_LAB_BROKER_ADDR)
#error "TASK 2 is not done yet: declare LAB_BROKER_ADDR and LAB_BROKER_PORT in Kconfig. \
The lab guide gives them in 'Point the node at your broker'."
#endif

LOG_MODULE_REGISTER(lab0_mqtt, LOG_LEVEL_INF);

#define TOPIC_SENSOR  "iot/sensor"
#define TOPIC_CONTROL "iot/control"

#define PUBLISH_INTERVAL K_SECONDS(2)

static const struct device *const strip = DEVICE_DT_GET(DT_ALIAS(led_strip));

static K_SEM_DEFINE(ipv4_ready, 0, 1);

static struct net_mgmt_event_callback wifi_cb;
static struct net_mgmt_event_callback ipv4_cb;

static struct mqtt_client client;
static struct sockaddr_storage broker;
static uint8_t rx_buffer[256];
static uint8_t tx_buffer[256];
static struct zsock_pollfd fds[1];
static bool connected;

/* --- Actuating capability ------------------------------------------------ */

struct control_cmd {
	int state;
};

static const struct json_obj_descr control_cmd_descr[] = {
	JSON_OBJ_DESCR_PRIM(struct control_cmd, state, JSON_TOK_NUMBER),
};

static void led_set(int on)
{
	/* TASK 3 - Actuating Capability. Same as the HTTP lab. */
	ARG_UNUSED(on);
}

static void handle_control_payload(struct mqtt_client *c,
				   const struct mqtt_publish_param *pub)
{
	uint8_t payload[64];
	uint32_t len = pub->message.payload.len;
	struct control_cmd cmd = { 0 };
	int ret;

	if (len >= sizeof(payload)) {
		LOG_WRN("Control payload too large (%u bytes), dropping", len);
		return;
	}

	/* TASK 4 - Actuating Capability.
	 * The payload is not in the event: read `len` bytes out of the socket
	 * first, then parse and actuate, then acknowledge. Guide section 3 explains
	 * both the read and why the acknowledgement is not optional.
	 */
	ARG_UNUSED(ret);
	ARG_UNUSED(cmd);
	ARG_UNUSED(pub);
}

/* --- Sensing capability -------------------------------------------------- */

static int publish_sensor(struct mqtt_client *c)
{
	uint8_t payload[64];
	struct mqtt_publish_param param = { 0 };
	uint32_t tenths = 200 + (sys_rand32_get() % 100);
	int len = snprintf(payload, sizeof(payload), "{\"temperature\": %u.%u}",
			   tenths / 10, tenths % 10);

	/* TASK 5 - Sensing Capability.
	 * `payload` already holds the JSON. Describe the message in `param` and
	 * publish it. Guide section 2 lists the fields and asks you to justify the
	 * QoS you pick.
	 */
	ARG_UNUSED(len);
	ARG_UNUSED(param);

	return 0;
}

static int subscribe_control(struct mqtt_client *c)
{
	struct mqtt_topic topic = {
		.topic = {
			.utf8 = (uint8_t *)TOPIC_CONTROL,
			.size = strlen(TOPIC_CONTROL),
		},
		.qos = MQTT_QOS_1_AT_LEAST_ONCE,
	};
	struct mqtt_subscription_list list = {
		.list = &topic,
		.list_count = 1,
		.message_id = sys_rand16_get(),
	};

	LOG_INF("Subscribing to %s", TOPIC_CONTROL);

	return mqtt_subscribe(c, &list);
}

static void mqtt_evt_handler(struct mqtt_client *const c, const struct mqtt_evt *evt)
{
	switch (evt->type) {
	case MQTT_EVT_CONNACK:
		if (evt->result != 0) {
			LOG_ERR("MQTT connect failed (%d)", evt->result);
			break;
		}
		connected = true;
		LOG_INF("Connected to broker");
		subscribe_control(c);
		break;

	case MQTT_EVT_DISCONNECT:
		LOG_INF("Disconnected from broker (%d)", evt->result);
		connected = false;
		break;

	case MQTT_EVT_PUBLISH:
		handle_control_payload(c, &evt->param.publish);
		break;

	case MQTT_EVT_SUBACK:
		LOG_INF("Subscribed to %s", TOPIC_CONTROL);
		break;

	default:
		break;
	}
}

static void broker_init(void)
{
	struct sockaddr_in *b = (struct sockaddr_in *)&broker;

	b->sin_family = AF_INET;
	b->sin_port = htons(CONFIG_LAB_BROKER_PORT);
	zsock_inet_pton(AF_INET, CONFIG_LAB_BROKER_ADDR, &b->sin_addr);
}

static void client_init(struct mqtt_client *c)
{
	static const char client_id[] = "esp32c6-node";

	mqtt_client_init(c);
	broker_init();

	c->broker = &broker;
	c->evt_cb = mqtt_evt_handler;
	c->client_id.utf8 = (uint8_t *)client_id;
	c->client_id.size = strlen(client_id);
	c->password = NULL;
	c->user_name = NULL;
	c->protocol_version = MQTT_VERSION_3_1_1;
	c->transport.type = MQTT_TRANSPORT_NON_SECURE;

	c->rx_buf = rx_buffer;
	c->rx_buf_size = sizeof(rx_buffer);
	c->tx_buf = tx_buffer;
	c->tx_buf_size = sizeof(tx_buffer);
}

/* --- Interface capability: join the Wi-Fi network ------------------------ */

static void wifi_event_handler(struct net_mgmt_event_callback *cb, uint64_t event,
			       struct net_if *iface)
{
	const struct wifi_status *st = (const struct wifi_status *)cb->info;

	if (event == NET_EVENT_WIFI_CONNECT_RESULT) {
		if (st->status) {
			LOG_ERR("Wi-Fi association failed (%d)", st->status);
		} else {
			LOG_INF("Associated with \"%s\"", CONFIG_LAB_WIFI_SSID);
		}
	} else if (event == NET_EVENT_WIFI_DISCONNECT_RESULT) {
		LOG_WRN("Wi-Fi disconnected");
	}
}

static void ipv4_event_handler(struct net_mgmt_event_callback *cb, uint64_t event,
			       struct net_if *iface)
{
	if (event != NET_EVENT_IPV4_ADDR_ADD) {
		return;
	}

	for (int i = 0; i < NET_IF_MAX_IPV4_ADDR; i++) {
		char buf[NET_IPV4_ADDR_LEN];

		if (iface->config.ip.ipv4->unicast[i].ipv4.addr_type != NET_ADDR_DHCP) {
			continue;
		}

		LOG_INF("IPv4 address: %s",
			net_addr_ntop(AF_INET,
				      &iface->config.ip.ipv4->unicast[i].ipv4.address.in_addr,
				      buf, sizeof(buf)));
		k_sem_give(&ipv4_ready);
	}
}

static int wifi_connect(void)
{
	struct net_if *iface = net_if_get_first_wifi();
	struct wifi_connect_req_params params = { 0 };

	if (iface == NULL) {
		LOG_ERR("No Wi-Fi interface found");
		return -ENODEV;
	}

	params.ssid = (const uint8_t *)CONFIG_LAB_WIFI_SSID;
	params.ssid_length = strlen(CONFIG_LAB_WIFI_SSID);
	params.psk = (const uint8_t *)CONFIG_LAB_WIFI_PSK;
	params.psk_length = strlen(CONFIG_LAB_WIFI_PSK);
	params.security = WIFI_SECURITY_TYPE_PSK;
	params.channel = WIFI_CHANNEL_ANY;
	params.band = WIFI_FREQ_BAND_2_4_GHZ;
	params.mfp = WIFI_MFP_OPTIONAL;

	LOG_INF("Connecting to \"%s\"...", CONFIG_LAB_WIFI_SSID);

	return net_mgmt(NET_REQUEST_WIFI_CONNECT, iface, &params, sizeof(params));
}

int main(void)
{
	int64_t next_publish;
	int rc;

	if (!device_is_ready(strip)) {
		LOG_ERR("LED strip device not ready");
		return -ENODEV;
	}
	led_set(0);

	net_mgmt_init_event_callback(&wifi_cb, wifi_event_handler,
				     NET_EVENT_WIFI_CONNECT_RESULT |
					     NET_EVENT_WIFI_DISCONNECT_RESULT);
	net_mgmt_add_event_callback(&wifi_cb);

	net_mgmt_init_event_callback(&ipv4_cb, ipv4_event_handler, NET_EVENT_IPV4_ADDR_ADD);
	net_mgmt_add_event_callback(&ipv4_cb);

	if (wifi_connect() != 0) {
		LOG_ERR("Wi-Fi connect request failed");
		return -EIO;
	}

	k_sem_take(&ipv4_ready, K_FOREVER);

	while (1) {
		client_init(&client);

		LOG_INF("Connecting to broker %s:%d", CONFIG_LAB_BROKER_ADDR,
			CONFIG_LAB_BROKER_PORT);

		rc = mqtt_connect(&client);
		if (rc != 0) {
			LOG_ERR("mqtt_connect failed (%d), retrying in 5s", rc);
			k_sleep(K_SECONDS(5));
			continue;
		}

		fds[0].fd = client.transport.tcp.sock;
		fds[0].events = ZSOCK_POLLIN;

		next_publish = k_uptime_get() + 2000;

		while (1) {
			int timeout = mqtt_keepalive_time_left(&client);
			int wait = MIN(timeout, 1000);

			rc = zsock_poll(fds, 1, wait);
			if (rc < 0) {
				LOG_ERR("poll failed (%d)", errno);
				break;
			}

			if (rc > 0 && (fds[0].revents & ZSOCK_POLLIN)) {
				rc = mqtt_input(&client);
				if (rc != 0) {
					LOG_ERR("mqtt_input failed (%d)", rc);
					break;
				}
			}

			if (fds[0].revents & (ZSOCK_POLLERR | ZSOCK_POLLHUP)) {
				LOG_ERR("Broker connection lost");
				break;
			}

			rc = mqtt_live(&client);
			if (rc != 0 && rc != -EAGAIN) {
				LOG_ERR("mqtt_live failed (%d)", rc);
				break;
			}

			if (connected && k_uptime_get() >= next_publish) {
				publish_sensor(&client);
				next_publish = k_uptime_get() + 2000;
			}
		}

		connected = false;
		mqtt_disconnect(&client, NULL);
		k_sleep(K_SECONDS(5));
	}

	return 0;
}
