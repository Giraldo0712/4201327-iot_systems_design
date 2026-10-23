# SOP-06: DTLS (CoAPS) & Secure OTA

> **Main Lab Guide:** [Lab 6: Securing the Channel — DTLS & the Trustworthiness Viewpoint](../lab6.md)
> **Lecture:** [lab6_lecture.md](../../lectures/lab6_lecture.md)
> **ISO lens:** Trustworthiness viewpoint (§6.6, cross-cutting) realised as the RAID access-management control (Figure A.5)
> **GreenField Context:** Fixing Edward's penetration test findings — stopping an attacker from sniffing soil data and injecting a forged "OPEN valve" into Daniela's greenhouse

## Objectives

**Part A — DTLS (the graded lab):**
- Basic STRIDE threat model (assets, threats, controls) — Lab 6 Task A.
- Upgrade the Lab 3 `/env/temp` server to CoAPS (DTLS/PSK) on port 5684 — Task B.
- Verify plain CoAP (5683) is locked out and the wrong PSK fails the handshake — Task B.
- Confirm the payload is encrypted on the air and measure the handshake cost — Task C.

**Part B — Secure OTA (optional stretch, not graded):**
- Integrate MCUboot and image signing; perform a signed v1 → v2 update. Pairs with Lab 8's supplemental management concerns.

## Context
This implementation guide provides step-by-step technical instructions. **Part A is the body of Lab 6** — the firmware paste for the CoAPS server, the three client tests, and the handshake-timing measurement. **Part B is an optional stretch** (secure OTA with MCUboot); it is not on the Lab 6 rubric and can be skipped. It complements the [main lab guide](../lab6.md), which covers the STRIDE model, the Trustworthiness §6.6 audit, and the ethics of security decisions. The work happens on your **Lab 3 `/env/temp` server (Node A)**; the Lab 2 mesh, the Lab 4 valve, and the Lab 5 OTBR stay as they were.

---

## Part A: DTLS Implementation (CoAPS) — the graded lab

### 1. Basic Threat Model

Before implementing security measures, document your threat model in the DDR:

**Assets:**
- Sensor data (temperature, humidity)
- Control commands (valve open/close)
- Device firmware
- Thread network credentials

**Threats (STRIDE):**
- **Spoofing:** Attacker impersonates a legitimate sensor
- **Tampering:** Attacker modifies sensor readings or commands
- **Repudiation:** Cannot prove who sent a command
- **Information Disclosure:** Eavesdropping on unencrypted CoAP traffic
- **Denial of Service:** Flooding the network with fake packets
- **Elevation of Privilege:** Unauthorized access to admin functions

**Initial Controls:**
- DTLS encryption for CoAP (addresses Spoofing, Tampering, Info Disclosure)
- Pre-Shared Keys (PSK) for authentication
- Rate limiting (addresses DoS)
- Firmware signing (addresses Tampering of firmware)

### 2. Enable DTLS in libcoap

**Modify `sdkconfig`** to enable DTLS support:
```bash
# CoAP with DTLS
CONFIG_COAP_MBEDTLS_PSK=y
CONFIG_COAP_MBEDTLS_PKI=n
CONFIG_MBEDTLS_PSK_MODES=y
CONFIG_MBEDTLS_KEY_EXCHANGE_PSK=y
```

**Update `main/CMakeLists.txt`** to include mbedTLS:
```cmake
idf_component_register(SRCS "main.c" "coap_demo.c"
                        INCLUDE_DIRS "."
                        REQUIRES openthread libcoap esp_openthread_cli mbedtls)
```

### 3. Implement CoAPS Server with PSK

**Modify `main/coap_demo.c`** to add DTLS support:

```c
#include "coap3/coap.h"

// Pre-Shared Key (PSK) - In production, store in Secure Element
#define COAP_PSK_IDENTITY "iotlab2024"
#define COAP_PSK_KEY "secretkey123456"

static int verify_psk_callback(const uint8_t *identity, size_t identity_len,
                                 coap_session_t *session,
                                 const uint8_t **key, size_t *key_len)
{
    // Verify client identity
    if (identity_len == strlen(COAP_PSK_IDENTITY) &&
        memcmp(identity, COAP_PSK_IDENTITY, identity_len) == 0) {

        *key = (const uint8_t *)COAP_PSK_KEY;
        *key_len = strlen(COAP_PSK_KEY);

        ESP_LOGI(TAG, "PSK client authenticated: %.*s", (int)identity_len, identity);
        return 0;
    }

    ESP_LOGW(TAG, "PSK authentication failed for: %.*s", (int)identity_len, identity);
    return -1;
}

static void coap_server_task(void *pvParameters)
{
    coap_context_t *ctx = NULL;
    coap_address_t dst;

    // ... previous initialization code ...

    // Enable DTLS with PSK
    coap_dtls_pki_t dtls_pki;
    memset(&dtls_pki, 0, sizeof(dtls_pki));
    dtls_pki.version = COAP_DTLS_PKI_SETUP_VERSION;

    ctx = coap_new_context(NULL);
    if (!ctx) {
        ESP_LOGE(TAG, "Failed to create CoAP context");
        return;
    }

    // Register PSK callback
    coap_context_set_psk(ctx, COAP_PSK_IDENTITY,
                         (const uint8_t *)COAP_PSK_KEY,
                         strlen(COAP_PSK_KEY));

    // Create DTLS endpoint (port 5684 for CoAPS)
    coap_address_init(&dst);
    dst.addr.sin6.sin6_family = AF_INET6;
    dst.addr.sin6.sin6_port = htons(5684);  // CoAPS port
    dst.addr.sin6.sin6_addr = in6addr_any;

    coap_new_endpoint(ctx, &dst, COAP_PROTO_DTLS);

    ESP_LOGI(TAG, "CoAPS server started on port 5684 with DTLS/PSK");

    // ... rest of server code (resource registration, etc.) ...
}
```

### 4. Test DTLS Encryption

**On client device** (or PC with coap-client):

```bash
# Install coap-client with DTLS support
# Ubuntu/Debian: sudo apt install libcoap2-bin

# Test CoAPS GET with PSK
coap-client -m get -u iotlab2024 -k secretkey123456 \
    coaps://[fd11:22:33::1]:5684/sensor

# Test CoAPS PUT with PSK
echo -n "1" | coap-client -m put -u iotlab2024 -k secretkey123456 \
    coaps://[fd11:22:33::1]:5684/light -f -
```

**Verify encryption with packet capture:**
```bash
# On the ESP32-C6, enable Thread sniffer
# Observe that CoAP payload is now "Encrypted Application Data"
# No plaintext sensor values visible
```

### 5. Performance Impact Analysis

**Measure DTLS handshake overhead:**

```c
// Add timing code in coap_demo.c
static void log_dtls_handshake_time(coap_session_t *session)
{
    uint32_t handshake_start = esp_log_timestamp();
    // ... DTLS handshake occurs here ...
    uint32_t handshake_end = esp_log_timestamp();

    ESP_LOGI(TAG, "DTLS handshake completed in %u ms",
             handshake_end - handshake_start);
}
```

**For your DDR (Lab 6 Task C table):**
- Measure handshake time (target < 3 s) — first connect only.
- Compare per-reading bytes: plain CoAP (Lab 3 baseline) vs CoAPS record overhead.
- Energy impact: DTLS adds ~200–300 ms radio time **per handshake**. Multiply by RX current (≈ 75 mA) for the per-handshake energy, then divide by readings-per-session — this is why session reuse, not per-reading handshakes, is what keeps DTLS affordable on a battery node.

> **Session-reuse policy.** Establish one DTLS session and reuse it across many CoAP exchanges. If you tear down and re-handshake per reading, the handshake energy dominates and the battery math from Lab 3/4 breaks. Hold the session open for the lifetime of the Observe registration.

---

## Part B: Secure OTA Updates (optional stretch — not graded)

> **This part is a stretch goal.** It is not on the Lab 6 rubric. Secure firmware update is revisited as a Lab 8 supplemental concern. Attempt it only after Tasks A–C are complete. It pairs naturally with DTLS because both answer "who is allowed to change this device," but it is independent of the graded work.

### 1. Create Project from ESP-IDF Example

Use the ESP-IDF extension in VS Code:
1. Press `Ctrl+Shift+P` to open the command palette.
2. Search for and run `ESP-IDF: Show Examples` selecting your ESP-IDF version.
3. Select `protocols/https_server/advanced_https_ota` (Advanced HTTPS OTA Example).
4. Select the folder to create the project.

### 2. Configure MCUboot and Image Signing

**Enable MCUboot** in the project:
```bash
# Install dependencies if needed
pip install imgtool

# Generate RSA key for signing
imgtool keygen -k signing_key.pem -t rsa-2048

# Configure MCUboot in menuconfig
idf.py menuconfig
# Component config → MCUboot Config → Enable MCUboot
# Security → Enable signature verification
# Configure partitions for OTA (bootloader, primary, secondary)
```

**Add visible version** in `main/main.c` (modify app_main):
```c
void app_main(void) {
    ESP_LOGI(TAG, "IoT Lab Firmware Version: 1.0.0");
    // ... rest of code
}
```

### 3. Generate Signed Images

**Build v1 image:**
```bash
idf.py build
imgtool sign --key signing_key.pem --header-size 0x200 --align 4 --version 1.0.0 --pad-header build/iot_lab_base.bin build/iot_lab_base_v1_signed.bin
```

**For v2, change version in code:**
```c
ESP_LOGI(TAG, "IoT Lab Firmware Version: 2.0.0");
```
```bash
idf.py build
imgtool sign --key signing_key.pem --header-size 0x200 --align 4 --version 2.0.0 --pad-header build/iot_lab_base.bin build/iot_lab_base_v2_signed.bin
```

**Flash v1 image:**
```bash
idf.py set-target esp32c6
idf.py flash --bin build/iot_lab_base_v1_signed.bin
idf.py monitor
```

**For OTA, upload v2 to HTTPS server and trigger update from device.**

### 4. Configure HTTPS OTA Server

**Use the OTA server from `tools/ota_server.py`** (already included in the repository).

**Install dependencies:**
```bash
pip install flask
```

**Run server:**
```bash
python tools/ota_server.py
```

### 5. Implement OTA Client on Device

**Add OTA code** in `main/main.c`:

```c
#include "esp_https_ota.h"
#include "esp_http_client.h"

// OTA function
static void perform_ota(const char *url)
{
    ESP_LOGI(TAG, "Starting OTA from: %s", url);

    esp_http_client_config_t config = {
        .url = url,
        .cert_pem = NULL, // In production use certificate
        .timeout_ms = 5000,
    };

    esp_err_t ret = esp_https_ota(&config);
    if (ret == ESP_OK) {
        ESP_LOGI(TAG, "OTA successful, restarting...");
        esp_restart();
    } else {
        ESP_LOGE(TAG, "OTA failed: %s", esp_err_to_name(ret));
    }
}

// CoAP endpoint to trigger OTA
static void handle_ota(coap_context_t *ctx, coap_resource_t *resource,
                       coap_session_t *session, coap_pdu_t *request,
                       coap_binary_t *token, coap_string_t *query,
                       coap_pdu_t *response)
{
    if (request->code != COAP_REQUEST_POST) {
        response->code = COAP_RESPONSE_CODE_METHOD_NOT_ALLOWED;
        return;
    }

    // Extract URL from payload (simplified)
    char url[256] = "http://192.168.1.100:8080/firmware/v2"; // OTA server IP

    response->code = COAP_RESPONSE_CODE_CHANGED;
    // Trigger OTA in separate task
    xTaskCreate(ota_task, "ota", 4096, (void *)url, 5, NULL);
}

static void ota_task(void *param)
{
    const char *url = (const char *)param;
    vTaskDelay(1000 / portTICK_PERIOD_MS); // Delay to respond CoAP
    perform_ota(url);
    vTaskDelete(NULL);
}

// Register /ota resource
ota_resource = coap_resource_init(coap_make_str_const("ota"), 0);
coap_register_handler(ota_resource, COAP_REQUEST_POST, handle_ota);
coap_add_resource(ctx, ota_resource);
```

### 6. Perform v1→v2 Upgrade

**From PC, trigger OTA:**
```bash
# Trigger upgrade from PC
python tools/coap_client.py --host [Thread node IPv6] post /ota "upgrade"

# Or from Thread CLI on another node
coap post [Server IPv6] /ota upgrade
```

**Verify upgrade:**
- Logs will show "IoT Lab Firmware Version: 1.0.0" initially
- After OTA: "IoT Lab Firmware Version: 2.0.0"
- MCUboot logs will show signature verification and upgrade

### 7. Basic Threat Model

**Assets:**
- Device firmware
- Sensor data
- Thread network credentials

**Threats:**
- Man-in-the-middle attack on OTA
- Malicious firmware
- Physical access to device

**Controls:**
- Cryptographic firmware signing
- Integrity verification with MCUboot
- Updates only from authorized sources

## Deliverables

### Part A: DTLS Security
- Completed STRIDE threat model table in DDR
- Functional CoAPS server with PSK authentication on port 5684
- Test logs showing successful DTLS handshake with correct PSK
- Test logs showing failed authentication with incorrect PSK
- Packet capture showing encrypted CoAP payload
- Performance measurements: DTLS handshake time (target: < 3 seconds)

### Part B: Secure OTA
- Signed firmware images v1 and v2 with RSA-2048 key
- MCUboot logs showing signature verification
- Successful OTA upgrade logs v1→v2 with visible version change
- Secure update pipeline documentation
- ADR-006 documenting choice of PSK vs Certificates for DTLS
