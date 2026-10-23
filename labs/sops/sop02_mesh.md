# SOP-02: 6LoWPAN and Routing Experiments

> **Main Lab Guide:** [Lab 2: Thread Mesh](../lab2.md)
> **ISO Domains:** SCD (Sensing & Controlling)
> **Firmware:** the same `firmware/lab2_mesh` as Lab 2. No reflash.

Start from the Lab 2 mesh: A (leader), B and C all in `router` or `leader` state, with the
Part 3 MAC filters **cleared** (`ot macfilter rss clear` on A and C) unless an experiment
says otherwise. Budget about 30 minutes for Experiments A and B.

## Experiment A: when does a datagram stop fitting in one frame?

6LoWPAN compresses the IPv6 header and fragments whatever still doesn't fit in 127 bytes.
You can count the fragments: the MAC counts frames, the IP layer counts datagrams.

1. On A: `ot counters mac reset` and `ot counters ip reset`.
2. On A: `ot ping <B-mleid> 16 10 0.5`.
3. On A: `ot counters mac` (note `TxUnicast`) and `ot counters ip` (note `TxSuccess`).
   `TxUnicast / TxSuccess` is frames per datagram; expect 1 here.
4. Repeat with sizes 32, 48, 64, 80, 96, 128, 256, 512 and 1000, resetting both counters
   each time. Narrow down the **largest size that still takes one frame**.

A few extra frames per run are MLE housekeeping; round to the nearest whole number.

| Size (B) | `TxUnicast` | `TxSuccess` | Frames per ping | RTT avg (ms) |
|---|---|---|---|---|
| 16 | | | | |
| 64 | | | | |
| 128 | | | | |
| 512 | | | | |
| 1000 | | | | |

5. Repeat the threshold search toward **B's RLOC** and toward **C with the Lab 2 Part 3
   filters re-applied** (two hops). Does the threshold move?

**DDR questions:**

- Build the byte budget for your one-frame threshold: 127 bytes minus the MAC header,
  security header and MIC, FCS, compressed IPv6 header and ICMPv6 header. Which IPv6 header
  fields made it onto the air?
- Why can the receiver rebuild an RLOC's interface ID from the MAC header but not an
  ML-EID's? What does that do to the threshold?
- OpenThread drops a half-reassembled datagram after 2 s, and one lost fragment loses the
  whole datagram. At your Lab 1 edge PER, estimate the delivery rate of a 1000-byte ping.

## Experiment B: kill the leader

Lab 2 killed a router. The leader has an extra job: it hands out router IDs and holds the
network data. What happens without it?

1. On B: `ot leaderdata` and note the Partition ID and Leader Router ID.
2. Start a ping between the survivors, on B: `ot ping <C-mleid> 64 300 1`.
3. **Unplug A** and note the time.
4. Every 15 s on B and C: `ot state` and `ot leaderdata`. Note when one of them becomes
   `leader` and when the Partition ID changes.
5. Plug A back in. Watch `ot state` on A until it is back in the mesh, and check which
   Partition ID wins.

| Event | Time after unplug (s) |
|---|---|
| B→C pings fail (if at all) | |
| New leader elected (which board?) | |
| New Partition ID on both B and C | |
| A rejoined, single partition again | |

**DDR questions:**

- Did B→C traffic stop while there was no leader? What does that tell you about where the
  routing tables live?
- Why do the routers wait (OpenThread's network-ID timeout is 120 s) instead of electing a
  new leader the moment A goes quiet?
- Compare with the Lab 2 router loss. Which failure is worse for Edwin, and why?

## Experiment C (optional): routers vs end devices

Make C an end device that cannot become a router, then repeat the tractor test from its
side:

```bash
uart:~$ ot routereligible disable        # on C; it detaches and re-attaches as a child
uart:~$ ot parent                        # who C's parent is now
```

Unplug C's parent while C pings A. How long until C finds a new parent, compared with a
router losing a neighbour? Restore with `ot routereligible enable`.

## DDR update ("Advanced Experiments" section)

- [ ] **Fragmentation:** the size table, your one-frame byte budget, RLOC vs ML-EID vs
      2 hops.
- [ ] **Leader loss:** the event timeline and your answers.
- [ ] *(Optional)* **End device:** parent-loss recovery time.

---

## Command reference

| Command | Purpose |
|---|---|
| `ot state` | role: disabled / detached / child / router / leader |
| `ot ipaddr` · `ot ipaddr mleid` · `ot ipaddr rloc` | all unicast addresses · just the ML-EID · just the RLOC |
| `ot ipmaddr` | multicast groups |
| `ot extaddr` · `ot rloc16` | 64-bit MAC address · 16-bit short address |
| `ot neighbor table` | one-hop neighbours with RSSI and LQ |
| `ot router table` | every router: best relay, cost, link quality, direct link |
| `ot leaderdata` | partition ID and leader router ID |
| `ot parent` | an end device's parent |
| `ot counters mac` · `ot counters ip` (`reset`) | frame and datagram counters |
| `ot ping <addr> [size] [count] [interval s]` | e.g. `ot ping <addr> 64 20 0.5` (the interval is in seconds) |
| `ot macfilter rss add-lqi <extaddr> <0-3>` · `ot macfilter rss clear` | force the link quality of one neighbour · undo |
| `ot dataset active -x` · `ot dataset set active <hex>` | export · import the network credentials |
| `ot thread stop` · `ot ifconfig down` · `ot factoryreset` | leave the mesh · radio off · wipe the dataset |

**Troubleshooting:**

- `ot thread start` returns `Error 13: InvalidState`: run `ot ifconfig up` first.
- Stuck in `detached`: the dataset doesn't match. Re-export it with `ot dataset active -x` and
  paste the whole string; typing the channel or PAN ID by hand never gets the key right.
- Stuck in `child` for more than 2 minutes: normal up to 120 s (router selection jitter).
  Beyond that, check `ot routereligible`.
