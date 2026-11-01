# Safety

> Dharma's safety functions are a **software channel**. They are not certified and must never be
> the only protection of a robot that drives among people.

## Two channels

| Channel      | What                                                                                                      | Stops the robot by                               |
| ------------ | --------------------------------------------------------------------------------------------------------- | ------------------------------------------------ |
| 1 (hardware) | e-stop buttons and, where required, a safety-rated scanner or bumper wired to the drive's safe torque off | cutting the drive, independently of any software |
| 2 (Dharma)   | speed envelope, protective field, watchdogs, latched software e-stop in `control_mux_node`                | publishing zero on `cmd_vel`                     |

Wire channel 1's state to `control/hw_estop` (Bool, true = pressed): while it is pressed the
software e-stop cannot be released, and after the button comes back out an operator still has to
release the software e-stop explicitly. The robot driver must stop on its own command timeout
(the mux respawns if it dies).

## The pipeline

![Safety pipeline](../diagrams/svg/safety_pipeline.svg)

`control_mux_node` is the **only** publisher of the robot's `cmd_vel`:

1. **Arbitration.** AUTO forwards navigation (`control/nav_cmd_vel`), REMOTE the selected
   operator source (`control/remote/<source>/cmd_vel`, sources `handheld`, `dashboard` by
   default). A silent source gets one zero after its timeout. All timers run on the steady
   clock, so clock jumps and simulated time never disable them.
2. **E-stop latch.** Engaged by `control/estop/engage`, a reason on `control/estop_request`,
   `control/hw_estop` or an internal error; reasons accumulate. Zero is published at once and
   streamed while engaged.
3. **Re-arm.** After a release, at start and after switching to a remote source, the source must
   send a few consecutive neutral commands before anything it sends is forwarded: a stick held
   during the release never moves the robot. The follower pauses itself while the e-stop is
   engaged (a sticky pause: `navigation/resume` after the release).
4. **Envelope.** `robot.limits` speeds, `vy = 0` for diff robots, any non-finite axis makes the
   command zero; optionally the [health](Health.md) speed scale.
5. **Protective field** on the 360° `perception/safety_scan`, with one braking model
   `D(v) = v t_r + v² / 2a`:

   - **translation:** the free distance of the footprint along the motion, minus a margin,
     bounds the speed;
   - **rotation:** the free turning angle of the footprint bounds the yaw rate (a long body
     turning next to a wall);
   - **combined motion:** the footprint is checked along the commanded arc until standstill.

   The field is on in AUTO and, by default, in REMOTE (with its own margin).

## Fail-safe sensing

A scan that says nothing is never read as free:

- perception publishes every sector **BLOCKED** when the LiDAR is blind (too few points, an
  empty quarter), its TF is missing, processing failed or no cloud arrived;
- the mux accepts a safety scan only in the base frame with full coverage and a fresh stamp;
  otherwise the field is **STALE**; any blocked or NaN sector makes it **BLIND**;
- AUTO: STALE or BLIND gives zero. REMOTE: the fastest point of the body is capped at a creep
  speed (`field.remote_degraded_speed`, 0.15 m/s), and moving toward a blocked sector is refused;
- an exception in any mux callback engages the e-stop; on shutdown it publishes zero.

## Navigation's own guards

Before the mux, the follower already stops for stale TF (`TF_STARTING`, `TF_STALE`,
`TF_CLOCK`), stale or blind scans, stale avoidance and emergencies, with a zero command every
tick; its motion guard limits every command along its direction with the 360° scan and the same
braking model. See [Navigation](Navigation.md).

## Known gaps

- **Near-field blind zone:** a Mid-360 sees down to −7°; mounted 0.53 m high it sees a 10 cm
  object only beyond about 3.5 m. Perception remembers objects it saw, but one that appears
  inside the zone is not seen. Use a pitched mount or a near-field sensor where this matters.
- **Negative obstacles** (stairs down, platform edges) are not detected.
- The scan is not deskewed (up to `v · 0.1 s` of distortion): the field margins must cover it.
- The limits are only as good as the measured `max_decel` and `reaction_time`
  ([Robot Profile](Robot-Profile.md#measure-the-braking-limits)).

The manual's safety case lists every hazard, its mitigation and the test that verifies it.
