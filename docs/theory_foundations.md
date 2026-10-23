# Theory Foundations: First-Principles IoT
**Document Type**: Technical Reference
**Audience**: IoT Systems Engineers (Students)
**Purpose**: Deep understanding of the "why" behind IoT protocols and design choices

---

## Introduction

> Don't just use technology—understand the physics and math underneath.

This document provides first-principles explanations for the technologies you'll use in each lab. Samuel expects you to understand **why** protocols work the way they do, not just **how** to configure them.

Each section includes:
- **The Problem**: What challenge does this technology solve?
- **The Physics/Math**: Fundamental principles at work
- **The Trade-offs**: What are we gaining and losing?
- **Discussion Questions**: Test your understanding

---

## Lab 1: IEEE 802.15.4 Physical Layer

### 1.1 Why O-QPSK Modulation?

**The Problem**: IoT devices need long battery life, which requires efficient power amplifiers (PAs).

**Modulation Comparison**:

| Modulation | Envelope | PA Efficiency | Complexity | Data Rate |
|------------|----------|---------------|------------|-----------|
| ASK | Varying | Low (20-30%) | Simple | Low |
| FSK | Constant | Medium (40-50%) | Medium | Medium |
| QPSK | Varying | Low (20-30%) | Medium | High |
| **O-QPSK** | **Constant** | **High (60-70%)** | Medium | High |

**Key Insight**: **Constant envelope modulation** allows use of non-linear (Class C/E) power amplifiers.

**Why O-QPSK?**
- **Offset QPSK** staggers I and Q transitions by half a symbol period
- Eliminates 180° phase transitions (which cause amplitude peaks in QPSK)
- Result: **Constant envelope** = efficient PA = longer battery life

**The Math**:
```
O-QPSK: I(t) delayed by Ts/2 relative to Q(t)
Phase transitions: Only 0°, ±90° (never 180°)
Amplitude variation: <3 dB (vs QPSK's >10 dB)
PA efficiency gain: 60-70% vs 20-30% = 3× improvement
```

**Energy Impact**:
```
Linear PA @ 20% efficiency:   100 mW TX power requires 500 mW input
Non-linear PA @ 60% efficiency: 100 mW TX power requires 167 mW input

Battery life improvement: 3× for the same TX power
```

---

### 1.2 Link Budget Fundamentals

**Goal**: Determine maximum communication range given TX power and receiver sensitivity.

**Friis Transmission Equation**:
```
Received Power (dBm) = TX Power (dBm) - Path Loss (dB) + Antenna Gain (dBi)
```

**Free-Space Path Loss** (FSPL):
```
FSPL (dB) = 20 log₁₀(d) + 20 log₁₀(f) - 27.55

Where:
- d = distance in meters
- f = frequency in MHz
- 27.55 is a constant for metric units
```

**Example Calculation** (IEEE 802.15.4 @ 2.4 GHz, 10 meters):
```
TX Power:     +5 dBm (ESP32-C6)
Frequency:    2400 MHz
Distance:     10 meters
Antenna Gain: 0 dBi (omnidirectional)

Path Loss = 20 log₁₀(10) + 20 log₁₀(2400) - 27.55
          = 20 + 67.6 - 27.55
          = 60.05 dB

Received Power = +5 dBm - 60.05 dB + 0 dBi = -55.05 dBm

Receiver Sensitivity: -100 dBm (ESP32-C6)

Link Margin = Received Power - Sensitivity
            = -55.05 - (-100)
            = 44.95 dB ✓
```

**Interpretation**:
- **Positive margin**: Link closes (communication possible)
- **44.95 dB margin**: Sufficient for obstacles, fading, interference

**Factors Reducing Margin**:
| Factor | Loss | Result at 10m |
|--------|------|---------------|
| Drywall (1) | -5 to -10 dB | -60 to -65 dBm |
| Concrete wall | -10 to -20 dB | -65 to -75 dBm |
| Metal barrier | -20 to -40 dB | -75 to -95 dBm |
| Human body | -3 to -5 dB | -58 to -60 dBm |
| Vegetation | -10 to -30 dB | -65 to -85 dBm |

**Practical Range**:
```
Indoor (residential):     30-50 meters
Outdoor (line-of-sight):  100-200 meters
Through 2-3 walls:        10-20 meters
```

---

### 1.3 CSMA/CA Collision Avoidance

**The Problem**: Multiple devices sharing the same channel can collide.

**Why Not CSMA/CD** (Ethernet's approach)?
- CSMA/CD listens while transmitting, detects collision by voltage spike
- **RF limitation**: Cannot listen while transmitting (half-duplex radio)
- **Solution**: CSMA/CA (Collision Avoidance) - prevent collisions before they happen

**CSMA/CA Algorithm** (IEEE 802.15.4):
```
1. Listen (CCA - Clear Channel Assessment)
   - Measure RSSI (Received Signal Strength Indicator)
   - If RSSI < threshold (e.g., -75 dBm): channel is clear
   - If RSSI ≥ threshold: channel is busy

2. If busy:
   - Wait for random backoff period (0 to 2^BE - 1 slots)
   - BE (Backoff Exponent) starts at 3, max 5
   - Each slot = 320 µs

3. If clear:
   - Transmit frame
   - Wait for ACK
   - If ACK received: success
   - If no ACK: collision likely, retry (up to 3 retries)
```

**Binary Exponential Backoff**:
```
Attempt 1: Random(0, 2³-1) = 0-7 slots   → 0-2.24 ms
Attempt 2: Random(0, 2⁴-1) = 0-15 slots  → 0-4.8 ms
Attempt 3: Random(0, 2⁵-1) = 0-31 slots  → 0-9.92 ms
```

**Why Exponential?**
- Light load: Low backoff, minimal delay
- Heavy load: Higher backoff, reduces collision probability
- **Trade-off**: Latency vs throughput

---

### 1.4 Energy per Bit

**TX Energy Calculation**:
```
Energy (Joules) = Power (Watts) × Time (seconds)

For ESP32-C6:
TX Power: 100 mW (20 dBm)
TX Time:  32 bytes @ 250 kbps = (32 × 8) / 250,000 = 1.024 ms
Energy =  0.1 W × 0.001024 s = 102.4 µJ

Energy per bit = 102.4 µJ / 256 bits = 0.4 µJ/bit
```

**Battery Impact**:
```
Battery: 2× AA = 2500 mAh @ 3V = 9000 mWh = 32,400 J

Number of TX frames = 32,400 J / 0.0001024 J = 316 million frames

If transmitting once per second:
Lifetime = 316M seconds ÷ (60 × 60 × 24) = 3,657 days ≈ 10 years
```

**Reality Check**: Why don't batteries last 10 years?
- RX consumes power (listening for ACKs, mesh routing)
- CPU active time (processing, crypto)
- Sleep mode isn't zero power (leakage current)
- Self-discharge of battery (~5% per year)

**Practical lifetime with duty cycling**: 6-12 months

---

### Lab 1 Discussion Questions

1. **Why does increasing TX power not linearly increase range?**
   - Hint: Path loss scales logarithmically with distance

2. **What happens if two devices start transmission at exactly the same time?**
   - Collision → no ACK → backoff and retry
   - Why is this rare? Backoff randomization

3. **Why does IEEE 802.15.4 use 250 kbps instead of higher data rates?**
   - Higher rate = less time per bit = less energy per bit (good)
   - But: Higher rate = less processing gain, worse sensitivity (bad)
   - 250 kbps balances energy efficiency and range

---

## Lab 2: 6LoWPAN and IPv6

### 2.1 The MTU Problem

**MTU** (Maximum Transmission Unit): Largest packet sent in one frame.

| Protocol | MTU |
|----------|-----|
| Ethernet | 1500 bytes |
| IEEE 802.15.4 | **127 bytes** |

**IPv6 Header** (uncompressed): **40 bytes**
```
┌────────────────────────────────────────────┐
│ Version (4) | Traffic Class (8) | Flow (20)│  4 bytes
├────────────────────────────────────────────┤
│ Payload Length (16) | Next Header (8) |    │  4 bytes
│ Hop Limit (8)                              │
├────────────────────────────────────────────┤
│ Source Address (128 bits)                  │ 16 bytes
├────────────────────────────────────────────┤
│ Destination Address (128 bits)             │ 16 bytes
└────────────────────────────────────────────┘
Total: 40 bytes
```

**Problem**: 40-byte IPv6 header + 17-byte 802.15.4 overhead = **57 bytes** before any payload!
- Leaves only 127 - 57 = **70 bytes** for application data
- Add UDP (8 bytes) → Only **62 bytes** for payload
- Efficiency: 62 / 127 = **49%**

---

### 2.2 6LoWPAN Header Compression (IPHC)

**Key Observations**:
1. Most IPv6 fields are predictable in a local network
2. Addresses can be derived from 802.15.4 addresses
3. Many fields have common values (e.g., Hop Limit = 64)

**Compression Results**:
```
Uncompressed IPv6: 40 bytes
Compressed (IPHC):  2-3 bytes

Savings: 37-38 bytes!
```

**Address Compression Example**:
```
Uncompressed:
Source: fe80::0200:5eef:1234:5678 (16 bytes)
Dest:   fe80::0200:5eef:abcd:ef01 (16 bytes)
Total: 32 bytes

Compressed (using 802.15.4 addresses):
Source: Derived from MAC layer (0 bytes in IPv6 header)
Dest:   Derived from MAC layer (0 bytes in IPv6 header)
Total: 0 bytes in IPv6 header!
```

**Efficiency Comparison**:

| Protocol Stack | Header Overhead | 50-byte Payload | Efficiency |
|----------------|-----------------|-----------------|------------|
| **Uncompressed** | 65 bytes | 115 bytes | 43% |
| **6LoWPAN** | 24 bytes | 74 bytes | **68%** |
| **Savings** | 41 bytes | 41 bytes | +25 pp |

**Energy Impact**:
```
Uncompressed: 115 bytes @ 250 kbps = 3.68 ms TX time
Compressed:    74 bytes @ 250 kbps = 2.37 ms TX time

TX energy savings: 35% per packet
```

---

### 2.3 Fragmentation

**Problem**: Even with compression, packets can exceed 127 bytes.

**6LoWPAN Fragmentation**:
```
200-byte payload → 2 fragments:

Fragment 1:
┌────────────────────────────────┐
│ Fragmentation Header (4 bytes) │
│ IPv6 + UDP headers (7 bytes)   │
│ Payload chunk 1 (110 bytes)    │
└────────────────────────────────┘
Total: 121 bytes

Fragment 2:
┌────────────────────────────────┐
│ Fragmentation Header (5 bytes) │
│ Payload chunk 2 (90 bytes)     │
└────────────────────────────────┘
Total: 95 bytes
```

**Challenges**:
- **Packet loss**: If any fragment lost, entire datagram retransmitted
- **Buffering**: Receiver must buffer fragments
- **Timeout**: Incomplete datagrams discarded (RFC 4944 allows up to 60 s; OpenThread uses 2 s)

**Recommendation**: Keep payloads small to avoid fragmentation.

---

### Lab 2 Discussion Questions

1. **Why does 6LoWPAN compress headers but not payload data?**
   - Headers are predictable (known structure), payload is arbitrary
   - Application-layer compression (CBOR) handles payload

2. **What happens if the Border Router doesn't support compression?**
   - It must! Border Router decompresses before forwarding to IP network

3. **Why not use bigger frames (increase MTU)?**
   - Larger frames = longer TX time = higher collision probability
   - 127 bytes @ 250 kbps = 4 ms (acceptable)
   - 1500 bytes @ 250 kbps = 48 ms (too long)

---

## Lab 3: Thread Mesh Networking

### 3.1 Why Mesh Topology?

**Star Topology** (classic WiFi):
```
Device A    Device B    Device C
     ↘         ↓         ↙
         Access Point
```
- **Pros**: Simple, centralized control
- **Cons**: Single point of failure, limited range (max 1 hop)

**Mesh Topology** (Thread):
```
[Router A] ←→ [Router B] ←→ [Router C]
     ↕            ↕            ↕
[End Dev 1]  [End Dev 2]  [End Dev 3]
```
- **Pros**: Self-healing, extended range (multi-hop)
- **Cons**: Complex routing, leader election overhead

**Range Extension**:
```
Star:           Max range = 1 × radio range (50m)
Mesh (3 hops):  Max range = 3 × radio range (150m)
```

---

### 3.2 Routing Algorithms

**Distance Vector Routing** (Thread uses a variant):

Each router maintains a routing table:
```
┌─────────────┬──────────┬──────────┐
│ Destination │ Next Hop │   Cost   │
├─────────────┼──────────┼──────────┤
│ Router A    │ Direct   │    1     │
│ Router B    │ Router A │    2     │
│ Router C    │ Router B │    3     │
└─────────────┴──────────┴──────────┘
```

**Route Cost Calculation**:
```
Link margin = average RSS − noise floor
  > 20 dB → link quality 3 → link cost 1
  > 10 dB → link quality 2 → link cost 2
  >  2 dB → link quality 1 → link cost 4
  else    → link quality 0 → no link
Two-way link quality = min(LQ in, LQ out)
Path cost = sum of link costs along the route

Example:
A–B: LQ 3 → cost 1      B–C: LQ 3 → cost 1      A–C direct: LQ 1 → cost 4
Best route: A → B → C (cost 2) beats A → C (cost 4)
```

Thread rates links by **link margin**, not by the raw 802.15.4 LQI byte (0–255), whose
meaning varies between radio vendors. `ot neighbor table` and `ot router table` show the
resulting LQ 0–3 per link.

**Failure detection**:
- **Traffic-driven:** after 4 consecutive unicast frames to a neighbouring router go
  unacknowledged (each already retried by the MAC), the link is dropped at once.
- **Timer-driven:** a neighbouring router that sends no MLE advertisement for 100 s is
  dropped. Advertisements follow a Trickle timer, 1 s after a change, backing off to ~32 s.
- With traffic flowing, a mesh with a backup path heals in seconds; an idle link takes up
  to ~100 s to notice.

---

### 3.3 Leader Election

**Why a Leader?**
- Centralized network parameters (PAN ID, channel, keys)
- Assign Router IDs (6-bit IDs, 0–62; at most 32 active routers)
- Handle network-wide decisions

**No vote, just partitions:**
```
1. The first device to start a network becomes leader of a new partition
   (a random 32-bit Partition ID).

2. Routers track the leader through the network data in MLE advertisements.

3. If a router hears nothing from its leader for 120 s (network-ID timeout),
   it starts a new partition with itself as leader. Others attach to it.

4. When two partitions hear each other, they compare weight (leader weight,
   default 64), then Partition ID. The lower one's devices re-attach to the
   higher one: the partitions merge.
```

Routing keeps working until that timeout: route tables live in every router. What
stops is router-ID assignment and network-data updates. `ot leaderdata` shows the current
Partition ID and leader; SOP-02 Experiment B watches a partition form and merge.

---

### 3.4 Network Partitions

**Scenario**: Network splits due to interference or node failure.

```
Before:
[Leader A] ←→ [Router B] ←→ [Router C] ←→ [Router D]

After (link B-C fails):
Partition 1: [Leader A] ←→ [Router B]
Partition 2: [Router C] ←→ [Router D]
```

**What Happens**:
1. Partition 1: Leader A still in charge
2. Partition 2: after the 120 s network-ID timeout, Router C or D starts a new partition as leader
3. Two independent networks form
4. When link restored: partitions compared (weight, then Partition ID), the lower one re-attaches → merge

**Partition Detection Time**: ~120 s (network-ID timeout)

---

### 3.5 Latency Analysis

**Single-Hop Latency**:
```
Components:
1. Queue delay:       1-10 ms
2. CSMA/CA backoff:   1-5 ms
3. TX time:           1.6 ms (50 bytes)
4. RX processing:     1 ms
5. ACK delay:         0.5 ms

Total: ~5-20 ms per hop
```

**Multi-Hop Latency**:
| Hops | Typical Latency |
|------|-----------------|
| 1 | 10-30 ms |
| 3 | 30-100 ms |
| 5 | 50-200 ms |

**Implication**: Thread suitable for monitoring (100-1000 ms), not real-time control (< 10 ms).

---

### Lab 3 Discussion Questions

1. **Why does Thread limit routers to 32?**
   - Routing table size: 32 entries = manageable memory
   - Convergence time: More routers = longer convergence

2. **What happens if two leaders have the same weight?**
   - Tie-breaker: Compare Router ID (deterministic)

3. **Can mesh have zero latency increase per hop?**
   - No: Each hop adds queuing + TX time (fundamental limit)

---

## Lab 3: CoAP Application Protocol

### 4.1 Why REST for IoT?

**REST Constraints**:
1. **Client-Server**: Separation of concerns
2. **Stateless**: Each request contains all information
3. **Cacheable**: Responses can be cached
4. **Uniform Interface**: Standard methods (GET, POST, PUT, DELETE)

**HTTP vs CoAP**:

| Feature | HTTP | CoAP |
|---------|------|------|
| Transport | TCP | UDP |
| Header size | 200-500 bytes | **4-10 bytes** |
| Methods | GET, POST, PUT, DELETE | GET, POST, PUT, DELETE |
| Reliability | TCP guarantees | Optional CON messages |
| Observe | Server-Sent Events | Native (RFC 7641) |

---

### 4.2 CoAP Message Format

**Header** (4 bytes minimum):
```
┌───┬───┬─────┬──────────┬────────────────┐
│Ver│ T │ TKL │   Code   │   Message ID   │
│2b │2b │ 4b  │   8b     │      16b       │
└───┴───┴─────┴──────────┴────────────────┘
```

**Fields**:
- **Ver**: Version (always 1)
- **T**: Type (CON, NON, ACK, RST)
- **TKL**: Token Length (0-8 bytes)
- **Code**: Method (GET=0.01) or Status (2.05=Content)
- **Message ID**: For duplicate detection

**Example GET**:
```
CoAP: 18 bytes
HTTP: 100-150 bytes

Savings: 5-8× smaller
```

---

### 4.3 Reliability Without TCP

**CON (Confirmable) Messages**:
```
Client                          Server
   | CON [MsgID=0x1234]            |
   | GET /sensors/temp             |
   |------------------------------>|
   |       ACK [MsgID=0x1234]      |
   |       2.05 Content "23.5°C"   |
   |<------------------------------|
```

**If ACK not received** (exponential backoff):
```
Send:           wait random(2-3 s)
Retransmit 1:   wait 4-6 s
Retransmit 2:   wait 8-12 s
Retransmit 3:   wait 16-24 s
Retransmit 4:   wait 32-48 s
Last retransmission after 30-45 s; give up after 62-93 s
```

**When to use CON vs NON**:

| Use Case | Type | Rationale |
|----------|------|-----------|
| Critical sensor reading | CON | Must ensure delivery |
| Periodic telemetry | NON | Occasional loss OK |
| Actuator command | CON | Must confirm execution |
| Observe heartbeat | CON | Proves the observer is still listening (RFC 7641 §4.5) |

---

### 4.4 Idempotency in Lossy Networks

**Idempotent**: Can apply multiple times, same result.

```
Idempotent:
- GET /sensors/temp     → Same result always
- PUT /led {"on":true}  → LED is on, repeated = still on

Non-Idempotent:
- POST /counter/inc     → Different result each time
```

**Why It Matters** (ACK lost scenario):
```
Client sends PUT → Server executes → ACK lost → Client retransmits

Idempotent (PUT): LED still "on" ✓
Non-Idempotent (POST counter++): Counter incremented twice ✗
```

**Solution**: Use idempotent operations. Duplicate detection in the server is optional in RFC 7252, and the Zephyr CoAP server used in Lab 3 doesn't do it: every retransmission reaches the handler.

---

### 4.5 CoAP Observe (Pub/Sub)

**Polling** (inefficient):
```
Client sends GET every second
Server responds every second
Even when data hasn't changed → wasted bandwidth
```

**Observe** (RFC 7641):
```
Client                          Server
   | GET /sensors/temp             |
   | Observe: 0 (register)         |
   |------------------------------>|
   |       2.05 "23.5°C"           |
   |       Observe: 1              |
   |<------------------------------|
   |                               | (data changes)
   |       2.05 "24.0°C"           |
   |       Observe: 2              |
   |<------------------------------|
```

**Energy savings**: 10-100× reduction in traffic.

---

### Lab 3 Discussion Questions

1. **Why does CoAP use UDP instead of TCP?**
   - TCP overhead: 3-way handshake, state maintenance
   - CoAP adds reliability only when needed

2. **What if server restarts and loses Observe registrations?**
   - Client detects timeout, re-registers

3. **Is CoAP suitable for real-time control?**
   - Typical latency: 60-250 ms (Thread + CoAP)
   - OK for HVAC, lighting; not for motor control

---

## Lab 5: Border Router

### 5.1 The Gateway Function

**Problem**: Thread network (IPv6, 802.15.4) must communicate with external networks (IPv4/IPv6, Ethernet/WiFi).

**Border Router Responsibilities**:
1. **Protocol translation**: 6LoWPAN ↔ IPv6
2. **NAT64**: IPv6-only Thread devices reach IPv4 internet
3. **Routing**: Forward packets between Thread and external networks
4. **Commissioning**: Securely add new devices to Thread network

---

### 5.2 NAT64 Translation

**Problem**: Thread devices only speak IPv6, but many services are IPv4.

**NAT64 Prefix**: `64:ff9b::/96`
```
Thread device wants to reach 8.8.8.8:
1. Constructs IPv6: 64:ff9b::808:808 (8.8.8.8 embedded)
2. Sends to Border Router
3. Border Router extracts IPv4: 8.8.8.8
4. Forwards via IPv4 to destination
5. Response reverse-translated
```

**Latency overhead**: 10-20 ms

---

## Lab 6: Security and Cryptography

### 6.1 Why RSA-2048?

**RSA Security** based on difficulty of factoring N = p × q:

| Key Size | Security Level | Status |
|----------|----------------|--------|
| RSA-1024 | ~80-bit | Breakable by nation-states |
| **RSA-2048** | ~112-bit | NIST recommended through 2030 |
| RSA-4096 | ~140-bit | Future-proof, but slow |

**Math**:
```
RSA-1024: 2^80 operations to break
RSA-2048: 2^112 operations to break

Difference: 2^112 / 2^80 = 2^32 = 4 billion times harder
```

**Trade-off**: RSA-2048 signature verification ~2-3 seconds on ESP32 (acceptable for OTA).

---

### 6.2 Signing vs Encryption

| Property | Signing | Encryption |
|----------|---------|------------|
| Purpose | Prove authenticity | Hide content |
| Threat mitigated | Tampering | Eavesdropping |
| OTA use case | Verify firmware is genuine | (Usually not needed) |

**Why sign firmware?**
- Without signature: Attacker replaces firmware with malicious version
- With signature: Bootloader verifies, rejects tampered firmware
- Encryption alone: Attacker can't read but CAN replace

---

### 6.3 DTLS Overhead

**DTLS Handshake** (simplified):
```
6 flights of packets
~2-6 KB of data exchanged
500-3000 ms to complete
```

**Session Resumption**: After initial handshake, can resume with ~200 ms.

**Energy cost**: Significant! Minimize handshake frequency.
- Cache sessions
- Use pre-shared keys (simpler than certificates)
- Keep connections open when possible

---

### Lab 6 Discussion Questions

1. **Why sign firmware instead of just encrypting it?**
   - Encryption hides content but doesn't prevent replacement
   - Signature proves authenticity

2. **What's the cost of security on battery life?**
   - DTLS handshake: ~500-3000 ms of crypto operations
   - AES encryption: ~1 ms per KB (efficient)
   - Solution: Handshake rarely, encrypt always

---

## Lab 7: Power Management

### 7.1 Sleep Modes

**ESP32-C6 Power Consumption**:

| Mode | Current | Use Case |
|------|---------|----------|
| Active (TX) | 80-100 mA | Transmitting |
| Active (RX) | 25-30 mA | Listening |
| Light sleep | ~700 µA | RAM retained, fast wake |
| Deep sleep | ~5-7 µA | RTC only, slow wake |

**Energy Calculation**:
```
Active:  P = 3.3V × 80mA = 264 mW
Deep sleep: P = 3.3V × 7µA = 0.023 mW

Ratio: 264 / 0.023 = 11,500× less power in deep sleep!
```

---

### 7.2 Duty Cycling

**Strategy**: Sleep most of the time, wake briefly to transmit.

```
10% duty cycle:
- Active 6 seconds per minute
- Sleep 54 seconds per minute

Average power = (0.1 × 264 mW) + (0.9 × 0.023 mW) = 26.4 mW
Savings: 264 / 26.4 = 10× battery life extension
```

**Trade-off**: Higher duty cycle = faster response, shorter battery life.

---

### 7.3 Sleepy End Devices (SED)

**Thread SED behavior**:
```
1. Send "I'm going to sleep" to parent router
2. Sleep for poll interval
3. Wake, poll parent: "Any messages for me?"
4. Parent delivers buffered packets
5. Return to sleep
```

**Poll Interval Trade-offs**:

| Interval | Latency | Battery Impact |
|----------|---------|----------------|
| 100 ms | Low | High (frequent wake) |
| 1 second | Medium | Medium |
| 10 seconds | High | Low |

---

## Lab 8: System Integration

### 8.1 End-to-End Latency Breakdown

```
Component                      Latency     % of Total
─────────────────────────────────────────────────────
1. Sensor reading (ADC)        2 ms        2%
2. Format CoAP notification    1 ms        1%
3. Thread mesh (3 hops)        60 ms       60%
4. Border Router processing    5 ms        5%
5. Server processing           5 ms        5%
6. WebSocket transmission      5 ms        5%
7. Browser rendering           10 ms       10%
─────────────────────────────────────────────────────
Total                          ~88 ms

Bottleneck: Thread mesh (60%)
Optimization: Reduce hops, improve link quality
```

---

### 8.2 System Availability

**Target**: 99% uptime (< 1.68 hours downtime per week)

**Failure Modes**:
- Node failure → Mesh self-heals (30-60s)
- Border Router failure → Need redundant BR
- Cloud failure → Local-first design continues operation

**MTBF/MTTR**:
- **MTBF** (Mean Time Between Failures): Target > 168 hours
- **MTTR** (Mean Time To Recover): Target < 60 seconds

---

## Summary: First Principles Checklist

For each lab, ask:

1. **What?** What technology are we using?
2. **How?** How do we configure it?
3. **Why?** Why was it designed this way? ← **This is first-principles thinking!**

**Document your "why" answers in DDR Section 5: First Principles Reflections.**

---

## Further Reading

| Lab | Reference |
|-----|-----------|
| Lab 1 | IEEE 802.15.4 Standard |
| Lab 2 | RFC 6282 (6LoWPAN compression) |
| Lab 3 | Thread Specification |
| Lab 4 | RFC 7252 (CoAP), RFC 7641 (Observe) |
| Lab 6 | "Introduction to Modern Cryptography" - Katz & Lindell |

---

_This document supports ISO/IEC 30141:2024 Functional and Construction Viewpoint implementation._
