# SOP-08: The Golden Master — Consolidation, Hardening & the Chaos Drills

> **Main Lab Guide:** [Lab 8: The Golden Master](../lab8.md)
> **ISO placement:** the six-viewpoint DDR closes — **Business viewpoint** (§6.3) re-answered with evidence, **Construction viewpoint** (§6.7) IoT System Pattern filled from the running system.
> **GreenField Context:** the pilot is Monday. Samuel flashes your binary and runs the chaos script. If anyone touches a reset button, the pilot fails.

## Objectives

Freeze the system you built in Labs 1–7 into the **Golden Master v1.0**: a release build with no secrets in the repo (Part A), a hardened actuation path — rate limiting and a fail-safe valve (Part B), proven hands-off recovery under the six chaos drills (Part C), and an automated end-to-end test report plus mini pentest (Part D). The optional stretch closes pillar 2: a managed signed OTA over the Lab 7 egress path (Part E).

**No new features.** The starting point is your end-of-Lab-7 system: Node A (the `/env/temp` CoAPS server + OMD telemetry), the Lab 3 SED valve (`/act/valve`), Node B (CLI client), the Lab 5 OTBR, and the Lab 7 bridge + broker + dashboard. Everything below hardens what already runs.

---

## Part A — Harden the build

Apply to **both** firmware projects (Node A and the valve node).

### A.1 — Release configuration

`idf.py menuconfig` (ESP-IDF v5.x option names):

```
CONFIG_COMPILER_OPTIMIZATION_SIZE=y          # "Release" (-Os) instead of the default -Og
CONFIG_COMPILER_STACK_CHECK_MODE_NORM=y      # stack canaries on vulnerable functions
CONFIG_ESP_TASK_WDT_EN=y                     # task watchdog — on by default; verify it stayed on
```

Rebuild and re-run your normal Lab 7 flow once before continuing — an optimization change that breaks something is exactly the kind of week-8 surprise this lab exists to catch.

### A.2 — Stamp the version

In the **top-level** `CMakeLists.txt`, before `project(...)`:

```cmake
set(PROJECT_VER "1.0.0")
```

At the top of `app_main`:

```c
#include "esp_app_desc.h"

ESP_LOGI(TAG, "SoilSense Golden Master v%s", esp_app_get_description()->version);
```

The version now lives in the image header (it's what the OTA stretch in Part E compares) and in the boot log (it's what the demo video shows).

### A.3 — Secrets out of the repository

The rubric says **no hardcoded secrets in the repo**. Two are sitting in your tree from Lab 6: the PSK pair in `coap_demo.c`, and the Thread network key if you ever committed a dataset. Move them to a header git never sees:

```c
// main/secrets.h — gitignored. Copy from secrets.h.example and fill in.
#pragma once
#define COAP_PSK_IDENTITY "iotlab2024"
#define COAP_PSK_KEY      "secretkey123456"
```

```bash
echo "main/secrets.h" >> .gitignore
git rm --cached main/secrets.h        # if it was already tracked
```

Replace the `#define`s in `coap_demo.c` with `#include "secrets.h"`, and commit a `secrets.h.example` containing placeholders only. Note in ADR-008 what production would do instead — NVS with flash encryption, or a secure element — because the header trick keeps the secret out of *git*, not out of the *flash image*.

> If the real key was ever pushed, rewriting git history is not worth it for the lab — **rotate the secret** (pick a new PSK, reflash, note the rotation in ADR-008). That's also the production answer.

---

## Part B — Harden the actuation path

### B.1 — Rate limiting on Node A (4.29 Too Many Requests)

A fixed window per source address, small table, stalest-slot eviction. Add to `coap_demo.c`:

```c
#include <string.h>
#include "esp_timer.h"

#define RL_WINDOW_MS 10000      // window length
#define RL_MAX_REQ   8          // requests allowed per peer per window
#define RL_SLOTS     4          // distinct peers tracked

typedef struct {
    struct in6_addr peer;
    int64_t window_start_us;
    int count;
} rl_slot_t;

static rl_slot_t s_rl[RL_SLOTS];

static bool check_rate_limit(coap_session_t *session)
{
    const coap_address_t *remote = coap_session_get_addr_remote(session);
    const struct in6_addr *peer = &remote->addr.sin6.sin6_addr;
    int64_t now = esp_timer_get_time();

    rl_slot_t *slot = NULL, *stalest = &s_rl[0];
    for (int i = 0; i < RL_SLOTS; i++) {
        if (memcmp(&s_rl[i].peer, peer, sizeof(*peer)) == 0) { slot = &s_rl[i]; break; }
        if (s_rl[i].window_start_us < stalest->window_start_us) stalest = &s_rl[i];
    }
    if (!slot) {                                  // unseen peer: evict the stalest slot
        slot = stalest;
        memcpy(&slot->peer, peer, sizeof(*peer));
        slot->window_start_us = now;
        slot->count = 0;
    }
    if (now - slot->window_start_us > (int64_t)RL_WINDOW_MS * 1000) {
        slot->window_start_us = now;              // window expired: reset
        slot->count = 0;
    }
    return ++slot->count <= RL_MAX_REQ;
}
```

Gate each handler with it — first line of `hnd_env_temp_get` (and `hnd_health_get` if you chose the separate `/sys/health` resource in Lab 7):

```c
if (!check_rate_limit(session)) {
    coap_pdu_set_code(response, COAP_RESPONSE_CODE_TOO_MANY_REQUESTS);  // 4.29 (RFC 8516)
    return;
}
```

**Tune against your own consumers.** Observe notifications also pass through the GET handler, so the Lab 7 bridge counts against its slot — at one notification per report interval it sits far below 8-per-10 s, but if you set `RL_MAX_REQ` aggressively low you will rate-limit your own dashboard. The drill-4 flood should trip it; normal operation must not.

### B.2 — The fail-safe valve (fail closed)

The dangerous state is water *flowing*, not water stopped: if the valve node loses contact with the network while open, it must close itself. The Lab 6 ethics checkpoint promised this; now it's firmware. In the valve node's `valve_server_task` loop (SOP-04), replace `while (1) coap_io_process(ctx, 1000);` with:

```c
#include "esp_openthread_lock.h"
#include "openthread/thread.h"
#include "esp_timer.h"

#define FAILSAFE_DETACH_S 30    // grace period before fail-safe fires

    int64_t detached_since_us = 0;
    while (1) {
        coap_io_process(ctx, 1000);

        esp_openthread_lock_acquire(portMAX_DELAY);
        otDeviceRole role = otThreadGetDeviceRole(esp_openthread_get_instance());
        esp_openthread_lock_release();

        bool attached = (role == OT_DEVICE_ROLE_CHILD ||
                         role == OT_DEVICE_ROLE_ROUTER ||
                         role == OT_DEVICE_ROLE_LEADER);
        if (attached) {
            detached_since_us = 0;
        } else if (detached_since_us == 0) {
            detached_since_us = esp_timer_get_time();
        } else if (g_valve_state &&
                   esp_timer_get_time() - detached_since_us >
                       (int64_t)FAILSAFE_DETACH_S * 1000000) {
            ESP_LOGW(TAG, "FAILSAFE: detached > %d s — closing valve", FAILSAFE_DETACH_S);
            apply_valve_state(0);
        }
    }
```

The grace period matters: a SED routinely sees brief parent churn during mesh healing (Lab 2), and closing the valve on every blip would make the fail-safe itself an availability problem. 30 s rides out churn; a real detachment outlasts it.

**Demo (this is drill 3's no-parent case):** open the valve (`PUT {"v":1}` from Node B), power off **every** FTD, watch the valve node's monitor: role drops to `detached`, and ~30 s later the `FAILSAFE` line fires and GPIO goes low — with nobody sending a command.

### B.3 — ADR-008: securing the actuation path

The valve still speaks plain CoAP. Decide — on paper, no implementation required — and record in ADR-008:

| Option | What it buys | What it costs |
|---|---|---|
| **Leave plain** | zero energy/complexity | trusts Thread's link-layer AES-CCM (network key); any *on-mesh* device can actuate |
| **CoAPS on the SED** | end-to-end auth to the valve itself | DTLS handshake energy on a battery node — cite your Lab 6 handshake measurement, and the session-reuse policy it forces |
| **Gateway policy** | only the OTBR/bridge may originate valve commands | the enforcement point is off the device; a rogue on-mesh node bypasses it |

There is no free option — that's why it's an ADR, not a checklist item.

---

## Part C — The chaos drills (self-audit before Samuel's script)

Run all six. Hands off: watching the CLI and the Lab 7 dashboard is allowed; touching hardware is not — except the power switches, which *are* the drill. Record every number in the Lab 8 measurements table.

| # | Drill | Procedure | Pass condition |
|---|---|---|---|
| 1 | **Cold start** | Power everything off. Power on in the worst order: nodes first, OTBR last. | Mesh re-forms, dashboard green, **< 2 min** from last power-on |
| 2 | **Blackout** | Kill the OTBR for 10 min, then restore it. | Mesh keeps running meanwhile (local-first — the Lab 5/7 ADR claim, now proven); bridge + dashboard recover without restarting anything |
| 3 | **Parent loss** | Power off the valve's parent FTD only. | SED reattaches to another FTD if one exists; with none left, the B.2 fail-safe closes the valve |
| 4 | **Flood** | Run the Part D suite (stress + burst) during normal operation. | ≥ 80% success, 4.29s under burst, no reboot, dashboard keeps updating |
| 5 | **Random reboot** | Power-cycle each node once, ~30 s apart, random order. | Every node rejoins unaided; the dashboard shows the uptime resets (the Lab 7 telemetry signal doing its job) |
| 6 | **Overnight soak** | ≥ 12 h unattended with telemetry reporting. | 0 crashes, uptime monotonic, free heap stable |

For drill 6, a one-line heap probe in Node A's update task makes memory creep visible:

```c
ESP_LOGI(TAG, "free heap: %lu B", (unsigned long)esp_get_free_heap_size());
```

Log it on a slow cadence (e.g. every ~10 min); a steady downward staircase across the soak is a leak you want to find before Samuel does.

---

## Part D — The automated e2e suite + mini pentest

### D.1 — Run the suite

[`tools/test_e2e.py`](../../tools/test_e2e.py) drives the whole system from your laptop — **off-mesh**, so every passing test also re-proves the Lab 5 OTBR path end to end.

```bash
pip install aiocoap cbor2                  # same venv as Lab 7
python tools/test_e2e.py <node_a_global_ipv6> [valve_global_ipv6]
```

Use the **global (OMR) addresses** from `ipaddr` on each node, not the mesh-local `fd..` ones. What it checks:

1. **Security posture** — is plaintext :5683 locked out (Lab 6) or deliberately open for the bridge (Lab 7)? Reported either way; your ADRs must match what it finds.
2. **DTLS** — a CoAPS GET with the Lab 6 PSK succeeds and a wrong key fails the handshake (needs `coap-client` from `libcoap2-bin`; skipped with a note otherwise — override credentials with `--psk-identity` / `--psk-key`).
3. **Telemetry contract** — the CBOR payload still carries the Lab 7 keys.
4. **Actuation round-trip** — `/act/valve` PUT 1 → GET → PUT 0 with the exact 4-byte CBOR map (expect SED poll-period latency — that's Lab 3 physics, not a bug).
5. **Invalid inputs** — unknown path → 4.04, malformed valve payload → 4.00.
6. **Stress** — 20 sequential GETs: success ratio (≥ 80%) + min/avg/max latency.
7. **Burst** — 12 parallel GETs: at least one 4.29 proves B.1 is live.

Keep the printed report — the success ratio and latency stats are a named deliverable.

### D.2 — Manual pentest items

1. **Unauthorized join.** On a spare node (or Node B, temporarily), commission a *wrong* network key and try to join:

   ```
   dataset networkkey 00112233445566778899aabbccddeeff
   dataset commit active
   ifconfig up
   thread start
   state          # must report 'detached' — never 'child'
   ```

   Restore the real dataset afterwards. (This is the Thread network credential doing its job — Lab 2's commissioning, audited.)

2. **Wrong PSK, watched from the dashboard.** The suite already fires a wrong-key handshake; do it again by hand while watching the Lab 7 failed-handshake telemetry — Edward's "is anyone attacking us right now?" signal lighting up on a real probe is the best 30 seconds of the demo video.

3. **Malformed actuation.** `PUT` garbage to `/act/valve` and confirm 4.00 — the strict 4-byte decoder from SOP-04 rejects anything that isn't `{"v": 0|1}`.

---

## Part E (optional stretch) — Pillar 2: the managed signed OTA

Lab 6 left pillar 2 (*signed code*) as a preview; Lab 7 built the egress path and promised "watching becomes acting." Close the loop:

1. Follow [SOP-06 Part B](sop06_security.md) for MCUboot + `imgtool` signing, bumping `PROJECT_VER` to `1.1.0`.
2. Serve the signed image with [`tools/ota_server.py`](../../tools/ota_server.py).
3. Make it *managed*: publish the announcement on the broker — `mosquitto_pub -t soilsense/fleet/ota -m '{"version":"1.1.0","url":"https://<host>:8070/v1.1.0.bin"}'` — and trigger `perform_ota()` on the node from it (or by hand, documenting where the subscriber would live).
4. Watch the Lab 7 dashboard report the new version string and an uptime reset — the update went *down* the same path the telemetry comes *up*.

Not on the rubric; if you skip it, write it into DDR §9 as a **documented gap with a plan** — an auditor respects a named gap and distrusts a blank one.

---

## Verification

1. Both boot logs show `SoilSense Golden Master v1.0.0`; `git grep secretkey` matches only `secrets.h.example`.
2. A burst of more than 8 requests in 10 s draws a 4.29, and the dashboard keeps updating regardless.
3. With the valve open and every FTD powered off, the `FAILSAFE` line fires within ~35 s and the valve GPIO goes low.
4. `test_e2e.py` reports ≥ 80% stress success, the actuation round-trip passes, and the security posture matches your ADRs.
5. All six chaos drills pass hands-off, numbers recorded in the Lab 8 measurements table.

---

## Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| Every e2e test times out | Wrong address family — use each node's **global (OMR)** address from `ipaddr`, not the mesh-local `fd..` one; confirm the OTBR is up and your laptop is on its LAN (Lab 5 checks). |
| `esp_app_get_description` implicit declaration | `#include "esp_app_desc.h"` (component `esp_app_format`, ESP-IDF ≥ 5.1). |
| Boot log still says `v0.0.0` / project name | `set(PROJECT_VER ...)` must be in the **top-level** `CMakeLists.txt` *before* `project()`, then a full rebuild. |
| 4.29 never appears under burst | If Node A is CoAPS-only, each `coap-client` call re-handshakes (~seconds) and the burst lands slower than the window — burst the plain endpoint if your posture keeps one, or shrink `RL_WINDOW_MS` for the test and note it. |
| Dashboard goes red during normal operation after B.1 | Rate limiter tuned below your own consumers — the bridge's Observe notifications count against its slot; raise `RL_MAX_REQ` or slow the report interval. |
| `FAILSAFE` never fires in drill 3 | Another FTD was still up and the SED reattached — that's the drill passing the *other* way; to force the fail-safe, power off **all** FTDs. Also check the valve was actually open (`g_valve_state == 1`). |
| Valve e2e test gets 4.00 | The payload must be exactly the 4-byte CBOR map `A1 61 76 0X` (SOP-04 decoder); the suite sends it — your own scripts must too. |
| Node reboots during the flood | That's the watchdog catching starvation — exactly what drill 4 exists to find. Check the backtrace, the CoAP task stack size (6144 in SOP-04), and anything blocking inside a handler. |
| Stress success < 80% against the valve | It's a SED — back-to-back CON requests queue at the parent across poll periods and time out (Lab 3 physics). Run stress against Node A; measure the valve with single round-trips. |
