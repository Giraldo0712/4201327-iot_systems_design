#include <openthread/platform/radio.h>

/* The ESP32-C6 RCP reports TX security, which it does in software, and the
 * frames it encrypts fail the security check on the receiving node. Unsecured
 * MLE still gets through, so a node can attach while the network data is
 * small. Once Wi-Fi is up the Border Router publishes prefixes, routes and
 * services, the Child ID Response no longer fits in one frame, Thread sends the
 * fragments with MAC security, and no node can attach. Hiding the capability
 * from the host's MAC makes the S3 encrypt frames itself. The RCP still reports
 * it, which the host requires from an RCP for Thread 1.2 and later.
 */
otRadioCaps __real_otPlatRadioGetCaps(otInstance *aInstance);

otRadioCaps __wrap_otPlatRadioGetCaps(otInstance *aInstance)
{
	return __real_otPlatRadioGetCaps(aInstance) & ~OT_RADIO_CAPS_TRANSMIT_SEC;
}
