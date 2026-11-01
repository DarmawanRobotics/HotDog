---
title: Site Acceptance Test
header: HotDog Site Acceptance Test
subtitle: Handover tests of HotDog on the Lynx M20 at a substation
version: "1.0"
date: 2026-11-01
audience: >-
  For the commissioning technician and the substation's representative, who run the tests
  together and sign the result.
note: >-
  Run after the commissioning (docs/commissioning.md) is complete, at the substation, with the
  routes the robot will patrol. Pass criteria marked "site" are agreed before the test and
  written into the row. Repeat the test yearly and after a major change (new robot, new
  payload, new routes, a new HotDog version).
revisions:
  - ["1.0", "2026-11-01", "First version"]
---

# About this test

## Purpose

The test shows, at the site, with its routes and its people, that HotDog:

1. stops safely when it must (emergency stops, protective field, the watchdog);
2. repeats the taught routes and stops where it was taught;
3. measures overheating and partial discharge and reports them;
4. tells the crew (reports, alerts) and keeps doing so after failures (network, power).

## Needed

| Item                                                               | For                    |
| ------------------------------------------------------------------ | ---------------------- |
| a laptop on the robot's and the substation's network, SSH, browser | commands, reports      |
| a phone in the crew's Telegram group                               | alerts                 |
| a tape measure, chalk or tape for marks                            | stop point positions   |
| a cardboard box about 40 × 40 × 60 cm                              | protective field       |
| a calibrated contact thermometer or a blackbody source             | thermal check          |
| a known partial discharge source, if available (or a known defect) | acoustic check         |
| this document, a pen                                               | results and signatures |

## Record

Fill in every row: the measured value, **P** (pass) or **F** (fail), and a note. A failed row
is fixed and the row run again; write both runs.

| Site       |     | Robot (serial)                                           |     |
| ---------- | --- | -------------------------------------------------------- | --- |
| Date       |     | HotDog version (`git -C ~/dev/HotDog describe --always`) |     |
| Technician |     | Substation representative                                |     |

# Before the test

| #   | Check                                                 | How                                                | Pass when                    | Result |
| --- | ----------------------------------------------------- | -------------------------------------------------- | ---------------------------- | ------ |
| 1.1 | every component installed                             | `scripts/setup.sh`                                 | every line ok                |        |
| 1.2 | HotDog starts at boot                                 | power cycle the robot; `hotdog status` after 2 min | every line has a value       |        |
| 1.3 | health OK                                             | `hotdog status`                                    | health OK                    |        |
| 1.4 | pod and acoustic camera connected                     | `hotdog status`                                    | pod ok, acoustic ok          |        |
| 1.5 | the clock right, the time zone the site's             | `timedatectl`                                      | within 1 s, zone as the site |        |
| 1.6 | the routes walked: walkways only, safe distances kept | walk each route with the representative            | the representative agrees    |        |
| 1.7 | settings backed up                                    | Technician Guide, Back up                          | archive exists               |        |

# Safety functions

Run in an open part of the site, robot standing, people at a safe distance, the M20 remote
in the technician's hand.

| #    | Test                             | How                                                                                                | Pass when                                                             | Result |
| ---- | -------------------------------- | -------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------- | ------ |
| 2.1  | M20 emergency stop               | during a patrol, press the remote's emergency stop                                                 | the robot stops at once                                               |        |
| 2.2  | HotDog e-stop latches            | during a patrol, `hotdog estop`; wait 30 s                                                         | stops; does not move until `hotdog release` + `hotdog resume`         |        |
| 2.3  | protective field, front          | the box on the route ahead, patrol at cruise speed                                                 | stops or steps around, never touches it                               |        |
| 2.4  | protective field, rear and sides | a person walks slowly towards the standing robot from the back and from each side while it patrols | it stops before the person every time                                 |        |
| 2.5  | a LiDAR lost                     | unplug the rear Airy's network cable while the robot stands in AUTO                                | health WARN/ERROR; the robot does not start moving; plug back: OK     |        |
| 2.6  | operator return                  | mid-route, `hotdog return`                                                                         | walks the route back, no inspections, docks; patrol STOPPED, returned |        |
| 2.7  | low battery return               | `ros2 param set /patrol_node abort.min_battery <current battery + 0.05>` mid-route                 | returns and docks; Telegram: back at the dock (battery); set it back  |        |
| 2.8  | blocked                          | `ros2 param set /patrol_node abort.hold_timeout_sec 30`; the box across a narrow part of the route | after 30 s blocked: returns to the dock; set it back to 180           |        |
| 2.9  | no patrol on a low battery       | `ros2 param set /patrol_node start.min_battery 0.99`; `hotdog patrol`                              | FAILED at checks: battery; set it back to 0.3                         |        |
| 2.10 | REMOTE is never overruled        | mid-route, take the robot with the M20 remote for longer than the hold timeout                     | the watchdog does nothing while the remote has it                     |        |

# Navigation

| #   | Test                             | How                                                                         | Pass when                                                  | Result |
| --- | -------------------------------- | --------------------------------------------------------------------------- | ---------------------------------------------------------- | ------ |
| 3.1 | teach                            | teach each route of the site (User Manual, chapter 4)                       | saved; `hotdog routes` lists it                            |        |
| 3.2 | mark the stop points             | on the first patrol, mark where the robot's centre stops at each stop point | marks on the ground                                        |        |
| 3.3 | repeatability                    | three patrols of the longest route; measure each stop from its mark         | every stop within (site) cm                                |        |
| 3.4 | the end of the route and docking | after each patrol of 3.3                                                    | the robot docks and charges                                |        |
| 3.5 | duration                         | patrol/status elapsed at the end of 3.3                                     | within (site) min; `abort.max_duration_min` about twice it |        |
| 3.6 | scheduled patrol                 | a schedule time 5 minutes ahead in the site file, `hotdog restart`          | the patrol starts at that time                             |        |

# Inspection

| #   | Test                        | How                                                                                                                       | Pass when                                                         | Result |
| --- | --------------------------- | ------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------- | ------ |
| 4.1 | every target measured       | the patrol of 3.3: report pages                                                                                           | every point `done`, every target with its images                  |        |
| 4.2 | thermal against a reference | a target on a warm part measured with the contact thermometer (or a blackbody at a known temperature in front of the pod) | the pod's value within the maker's accuracy of the reference      |        |
| 4.3 | the three phases compared   | a three-phase target with `strips=3` or regions                                                                           | three regions in the report, the hottest compared with the others |        |
| 4.4 | a hot spot found            | a heat source (a hot-air gun at a safe place, a known hot joint) in a target's view                                       | a finding with the right severity; in the report and on Telegram  |        |
| 4.5 | partial discharge           | the known source in an acoustic target's view, or the healthiest equipment                                                | discharge type as the source / noise on healthy equipment         |        |
| 4.6 | ambient                     | `hotdog ambient <today>`; the next patrol                                                                                 | the ambient check uses today's value                              |        |

# Reports and alerts

| #   | Test                           | How                                                                   | Pass when                                                     | Result |
| --- | ------------------------------ | --------------------------------------------------------------------- | ------------------------------------------------------------- | ------ |
| 5.1 | reports reachable              | `http://<robot>:8088/` from the substation network                    | front page, day, patrol pages open; images shown              |        |
| 5.2 | the last round                 | the second patrol of 3.3                                              | every finding shows the value of the first round              |        |
| 5.3 | print                          | print a patrol page to PDF                                            | one point per page, readable                                  |        |
| 5.4 | test alert                     | `hotdog alert-test`                                                   | arrives in the group                                          |        |
| 5.5 | a finding alert with its image | from 4.4                                                              | arrives within a minute, with the thermal image               |        |
| 5.6 | a failed patrol alert          | from 2.8                                                              | arrives with the reason                                       |        |
| 5.7 | offline                        | unplug the robot's uplink; `hotdog alert-test`; wait 2 min; plug back | `hotdog status`: 1 waiting; it arrives after the link is back |        |
| 5.8 | webhook (if used)              | `hotdog alert-test`                                                   | the receiving system shows it                                 |        |

# Resilience

| #   | Test                        | How                                                   | Pass when                                              | Result |
| --- | --------------------------- | ----------------------------------------------------- | ------------------------------------------------------ | ------ |
| 6.1 | power cycle on the dock     | switch the robot off and on                           | `hotdog status` OK within 3 min; the schedule still on |        |
| 6.2 | the service restarts itself | `sudo pkill -f "ros2 launch hotdog"`                  | running again within 30 s                              |        |
| 6.3 | a report missed while off   | stop HotDog right after a patrol ends, start it again | the patrol's page exists                               |        |
| 6.4 | disk                        | `hotdog status`: disk                                 | more than (site) GB free; retention set                |        |

# Handover

| #   | Item                                                                      | Result |
| --- | ------------------------------------------------------------------------- | ------ |
| 7.1 | the operators trained on the User Manual, each ran a patrol and an e-stop |        |
| 7.2 | the robot's address, user and password handed to the substation           |        |
| 7.3 | the Telegram group's members agreed with the substation                   |        |
| 7.4 | the limits (thermal, partial discharge) agreed and in the site file       |        |
| 7.5 | the maintenance schedule (Technician Guide) handed over, first date set   |        |
| 7.6 | the User Manual, Technician Guide and this record handed over             |        |

## Result

| Rows run |     | Passed |     | Failed (fixed and re-run) |     |
| -------- | --- | ------ | --- | ------------------------- | --- |

The robot is accepted for patrols at this site: ☐ yes ☐ yes, with the open points below ☐ no

Open points:

&nbsp;

&nbsp;

|                           | Name | Signature | Date |
| ------------------------- | ---- | --------- | ---- |
| Technician                |      |           |      |
| Substation representative |      |           |      |
