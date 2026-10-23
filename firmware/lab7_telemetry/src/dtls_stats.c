/* Counts failed DTLS handshakes, for /sys/health. Zephyr's socket layer frees a
 * failed session without telling the CoAP server, so the count comes from
 * wrapping Mbed TLS's handshake step (-Wl,--wrap=mbedtls_ssl_handshake): a
 * wrong key, for one, ends in a timeout once the server gives up waiting.
 */
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <mbedtls/ssl.h>

#include "app.h"

LOG_MODULE_REGISTER(dtls_stats, LOG_LEVEL_INF);

static atomic_t failed;

int __real_mbedtls_ssl_handshake(mbedtls_ssl_context *ssl);

int __wrap_mbedtls_ssl_handshake(mbedtls_ssl_context *ssl)
{
	int r = __real_mbedtls_ssl_handshake(ssl);

	switch (r) {
	case 0:
	case MBEDTLS_ERR_SSL_WANT_READ:
	case MBEDTLS_ERR_SSL_WANT_WRITE:
	case MBEDTLS_ERR_SSL_HELLO_VERIFY_REQUIRED:
		break;
	default:
		atomic_inc(&failed);
		LOG_WRN("DTLS handshake failed (-0x%04x), %ld so far", -r, atomic_get(&failed));
	}
	return r;
}

uint32_t dtls_handshakes_failed(void)
{
	return atomic_get(&failed);
}
