# SOP-01: MAC Layer Experiments

> **Main Lab Guide:** [Lab 1: Testing Your Wireless Radio](../lab1.md)
> **ISO Domains:** PED (Physical Entity Domain), SCD (Sensing & Controlling)
> **Firmware:** the same `firmware/lab1_radio` as Lab 1. No reflash.

Start from a working A–B link (Lab 1, Task 3.1) with B in the `router` state. Budget
about 30 minutes for Experiments A and B.

## Your instrument: MAC counters

The MAC counts every frame it sends and every problem it hits. Reset, run traffic, read:

```bash
uart:~$ ot counters mac reset
uart:~$ ...                              # traffic
uart:~$ ot counters mac
```

It prints about 30 lines. You need four:

| Counter | Meaning |
|---|---|
| `TxAckRequested` | unicast frames sent that asked for an ACK |
| `TxRetry` | retransmissions (no ACK, or no clear channel) |
| `TxErrCca` | frames dropped because the channel never came clear |
| `RxErrFcs` | frames received with a bad checksum (corrupted in the air) |

## Experiment A: ARQ, the losses you never see

Every unicast frame asks for an ACK. No ACK in time → the MAC retransmits. The
IEEE 802.15.4 default is 3 retries; OpenThread uses 15.

1. On A: `ot counters mac reset`.
2. **Unplug B** (a dead battery).
3. On A: `ot ping <B-RLOC> 64 1`, then `ot counters mac`. One ping, one frame, and
   `TxRetry` jumps by about 15: the frame went out 16 times before the MAC gave up.
4. Set the standard's value, reset and repeat: `ot mac retries direct 3`. `TxRetry` now
   grows by 3.
5. Restore: `ot mac retries direct 15`, plug B back in, wait for `router`.

**Retries vs distance (optional).** At your Lab 1 edge distance, run
`ot ping <partner-RLOC> 64 100 0.2` with retries at 15 and then at 0 (set it on **both**
boards, since the replies are retried too). Record PER and `TxRetry`. With 0 retries the
PER is close to the raw frame loss; with 15 it is what the application sees.

**DDR question:** your Lab 1 PER was measured with 15 retries. What was the real frame loss
at your edge distance, and what did each delivered ping cost in airtime?

## Experiment B: CSMA-CA, listen before talk

Before each attempt the radio listens for 128 µs (CCA). If the channel is busy it waits a
random backoff (0–7 slots of 320 µs, doubling up to 0–31) and listens again. After 5 busy
checks it gives up (`TxErrCca`).

Lab 1 said never to ping in both directions at once. Now do it on purpose, boards 1 m apart:

1. **Sequential.** Both boards: `ot counters mac reset`. A runs
   `ot ping <B-RLOC> 64 200 0.05`, and B runs the same toward A only after A finishes.
   Note the round-trip `avg` from each summary line, then `ot counters mac` on both.
2. **Simultaneous.** Reset counters on both, then start both pings at the same moment.
   Note the same numbers.

| | RTT avg A | RTT avg B | `TxRetry` A+B | `TxErrCca` A+B | PER |
|---|---|---|---|---|---|
| Sequential | | | | | |
| Simultaneous | | | | | |

Expect PER to barely change and RTT to rise: the MAC turns contention into waiting
(backoff) and retransmissions (collisions that CCA couldn't prevent).

**DDR question:** CCA found the channel clear, yet frames still collided. How? (Hint:
two radios that pick the same backoff slot run CCA at the same time, and neither is
transmitting yet.)

## Experiment C (optional): read the air

Promiscuous mode disables the address filter and prints every frame on the channel. It
needs the Thread interface down, so use a **third board** (borrow a neighbour's):

```bash
uart:~$ ot thread stop
uart:~$ ot ifconfig down
uart:~$ ot channel 15                    # your A–B channel
uart:~$ ot promiscuous enable
```

Frames scroll as hex dumps. Pick one and decode the start of the MAC header, which is little-endian:

```
41 d8 | 2c  | cd ab  | ff ff | 1e b9 ba 8a 65 22 63 6b | ...
FCF   | Seq | PAN ID | Dst   | Src (extended address)  | payload
```

`41 d8` is frame control `0xd841`: a data frame, PAN ID compressed, short destination,
extended source. `ff ff` is broadcast, typical of Thread's MLE advertisements. Frames whose
first byte has bit 3 set (`0x08`, e.g. `69 98`) use MAC security: their payload is
encrypted with the network key, which is why a sniffer without the key only sees headers.

Stop with `ot promiscuous disable`.

## DDR update ("Advanced Experiments" section)

- [ ] **ARQ:** `TxRetry` for one lost frame at 15 and 3 retries; your estimate of real
      frame loss at the edge distance.
- [ ] **CSMA-CA:** the sequential vs simultaneous table and your answer to the collision
      question.
- [ ] *(Optional)* **Sniffing:** one decoded frame header.
