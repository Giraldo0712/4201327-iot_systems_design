/* "coaps" shell command: a CoAP client over DTLS with this node's PSK, for
 * requests from inside the mesh. The OpenThread shell's own CoAPS client
 * doesn't build against Mbed TLS 4, so this one uses Zephyr's DTLS sockets.
 * Each command opens one DTLS session, prints how long its handshake took,
 * sends its requests over it and closes it.
 */
#include <stdlib.h>
#include <string.h>
#include <zephyr/kernel.h>
#include <zephyr/net/coap.h>
#include <zephyr/net/socket.h>
#include <zephyr/net/tls_credentials.h>
#include <zephyr/random/random.h>
#include <zephyr/shell/shell.h>

#define CLIENT_TAG    2
#define COAPS_PORT    5684
#define ACK_TIMEOUT_MS 2000
#define MAX_RETRANSMIT 4

static char key[CONFIG_MBEDTLS_PSK_MAX_LEN + 1] = CONFIG_LAB_PSK;

static int key_install(const struct shell *sh)
{
	(void)tls_credential_delete(CLIENT_TAG, TLS_CREDENTIAL_PSK);
	(void)tls_credential_delete(CLIENT_TAG, TLS_CREDENTIAL_PSK_ID);

	int r = tls_credential_add(CLIENT_TAG, TLS_CREDENTIAL_PSK, key, strlen(key));

	if (r == 0) {
		r = tls_credential_add(CLIENT_TAG, TLS_CREDENTIAL_PSK_ID, CONFIG_LAB_PSK_ID,
				       strlen(CONFIG_LAB_PSK_ID));
	}
	if (r < 0) {
		shell_error(sh, "Can't install the PSK (%d)", r);
	}
	return r;
}

/* DTLS session to [addr]:5684; the handshake runs inside connect() */
static int session_open(const struct shell *sh, const char *addr_str)
{
	struct net_sockaddr_in6 addr = {
		.sin6_family = NET_AF_INET6,
		.sin6_port = net_htons(COAPS_PORT),
	};
	static const sec_tag_t tags[] = { CLIENT_TAG };

	if (net_addr_pton(NET_AF_INET6, addr_str, &addr.sin6_addr) < 0) {
		shell_error(sh, "Not an IPv6 address: %s", addr_str);
		return -EINVAL;
	}
	if (key_install(sh) < 0) {
		return -EINVAL;
	}

	int fd = zsock_socket(NET_AF_INET6, NET_SOCK_DGRAM, NET_IPPROTO_DTLS_1_2);

	if (fd < 0) {
		shell_error(sh, "No DTLS socket (%d)", -errno);
		return -errno;
	}
	if (zsock_setsockopt(fd, ZSOCK_SOL_TLS, ZSOCK_TLS_SEC_TAG_LIST, tags, sizeof(tags)) < 0) {
		shell_error(sh, "Can't set the PSK tag (%d)", -errno);
		zsock_close(fd);
		return -errno;
	}

	int64_t t0 = k_uptime_get();

	if (zsock_connect(fd, (struct net_sockaddr *)&addr, sizeof(addr)) < 0) {
		int err = errno;

		shell_error(sh, "DTLS handshake failed after %lld ms (%d)", k_uptime_get() - t0, -err);
		zsock_close(fd);
		return -err;
	}
	shell_print(sh, "DTLS handshake: %lld ms", k_uptime_get() - t0);
	return fd;
}

static int build_request(struct coap_packet *req, uint8_t *buf, size_t size, uint8_t method,
			 const char *path, int value)
{
	uint32_t token = sys_rand32_get();
	char segs[64];
	int r;

	r = coap_packet_init(req, buf, size, COAP_VERSION_1, COAP_TYPE_CON, sizeof(token),
			     (uint8_t *)&token, method, coap_next_id());
	strncpy(segs, path, sizeof(segs) - 1);
	segs[sizeof(segs) - 1] = '\0';
	for (char *save, *s = strtok_r(segs, "/", &save); r == 0 && s;
	     s = strtok_r(NULL, "/", &save)) {
		r = coap_packet_append_option(req, COAP_OPTION_URI_PATH, s, strlen(s));
	}
	if (r == 0 && value >= 0) {
		const uint8_t cbor[] = { 0xA1, 0x61, 0x76, (uint8_t)value }; /* {"v": value} */

		r = coap_append_option_int(req, COAP_OPTION_CONTENT_FORMAT,
					   COAP_CONTENT_FORMAT_APP_CBOR);
		if (r == 0) {
			r = coap_packet_append_payload_marker(req);
		}
		if (r == 0) {
			r = coap_packet_append_payload(req, cbor, sizeof(cbor));
		}
	}
	return r;
}

/* One CON exchange with RFC 7252 retransmission; prints the response */
static int exchange(const struct shell *sh, int fd, uint8_t method, const char *path, int value)
{
	uint8_t buf[256];
	struct coap_packet req, rsp;
	int r = build_request(&req, buf, sizeof(buf), method, path, value);

	if (r < 0) {
		shell_error(sh, "Can't build the request (%d)", r);
		return r;
	}

	uint16_t id = coap_header_get_id(&req);
	int64_t t0 = k_uptime_get();
	int wait = ACK_TIMEOUT_MS;

	for (int attempt = 0; attempt <= MAX_RETRANSMIT; attempt++, wait *= 2) {
		if (zsock_send(fd, req.data, req.offset, 0) < 0) {
			shell_error(sh, "Send failed (%d)", -errno);
			return -errno;
		}

		struct zsock_pollfd pfd = { .fd = fd, .events = ZSOCK_POLLIN };

		while (zsock_poll(&pfd, 1, wait) > 0) {
			uint8_t in[256];
			int n = zsock_recv(fd, in, sizeof(in), 0);

			if (n <= 0 || coap_packet_parse(&rsp, in, n, NULL, 0) < 0 ||
			    coap_header_get_id(&rsp) != id) {
				continue;
			}

			uint8_t code = coap_header_get_code(&rsp);
			uint16_t len;
			const uint8_t *p = coap_packet_get_payload(&rsp, &len);
			char hex[2 * 32 + 1] = "";

			for (int i = 0; p && i < len && i < 32; i++) {
				snprintk(&hex[2 * i], 3, "%02x", p[i]);
			}
			shell_print(sh, "%u.%02u, payload %s, RTT %lld ms", code >> 5, code & 0x1f,
				    len ? hex : "(none)", k_uptime_get() - t0);
			return 0;
		}
	}
	shell_error(sh, "No response after %d transmissions", MAX_RETRANSMIT + 1);
	return -ETIMEDOUT;
}

static int cmd_get(const struct shell *sh, size_t argc, char **argv)
{
	int count = argc > 3 ? atoi(argv[3]) : 1;
	int fd = session_open(sh, argv[1]);

	if (fd < 0) {
		return fd;
	}
	for (int i = 0; i < count; i++) {
		(void)exchange(sh, fd, COAP_METHOD_GET, argv[2], -1);
	}
	zsock_close(fd);
	return 0;
}

static int cmd_put(const struct shell *sh, size_t argc, char **argv)
{
	int value = atoi(argv[3]);

	if (strlen(argv[3]) != 1 || (value != 0 && value != 1)) {
		shell_error(sh, "The valve takes 0 or 1");
		return -EINVAL;
	}

	int fd = session_open(sh, argv[1]);

	if (fd < 0) {
		return fd;
	}
	(void)exchange(sh, fd, COAP_METHOD_PUT, argv[2], value);
	zsock_close(fd);
	return 0;
}

static int cmd_key(const struct shell *sh, size_t argc, char **argv)
{
	const char *k = strcmp(argv[1], "default") == 0 ? CONFIG_LAB_PSK : argv[1];

	if (strlen(k) >= sizeof(key)) {
		shell_error(sh, "Key longer than %u characters", sizeof(key) - 1);
		return -EINVAL;
	}
	strcpy(key, k);
	shell_print(sh, "Client PSK set (identity \"%s\")", CONFIG_LAB_PSK_ID);
	return 0;
}

SHELL_STATIC_SUBCMD_SET_CREATE(coaps_cmds,
	SHELL_CMD_ARG(get, NULL, "GET over DTLS: <addr> <path> [count]", cmd_get, 3, 1),
	SHELL_CMD_ARG(put, NULL, "PUT {\"v\": 0|1} over DTLS: <addr> <path> <0|1>", cmd_put, 4, 0),
	SHELL_CMD_ARG(key, NULL, "Client PSK: <key> | default", cmd_key, 2, 0),
	SHELL_SUBCMD_SET_END);

SHELL_CMD_REGISTER(coaps, &coaps_cmds, "CoAP client over DTLS with a pre-shared key", NULL);
