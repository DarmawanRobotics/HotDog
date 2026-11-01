# FAQ

**Is Dharma safe to run among people?**
Its safety layer is a software channel (protective field, watchdogs, latched e-stop): it is not
certified. A robot in a public space also needs a safety-rated first channel (hardware e-stop,
and a certified scanner or bumper where required, wired to the drive) and a product safety case.
See [Safety](Safety.md).

**Which robots does it support?**
Any legged or wheeled base with velocity control (`omni`: vx, vy, wz; `diff`: vx, wz), a
Livox Mid-360 (or any LiDAR as PointCloud2 with another LiDAR-inertial estimator) and an IMU.
The robot is described by the [robot profile](Robot-Profile.md); the driver is a product package.

**Foxy, Humble or Jazzy?**
All three. Every repository is built and tested on each in CI. Foxy (Ubuntu 20.04, Python 3.8)
is end of life: use it for robots whose vendor SDK needs it. On Foxy a crashed node is not
respawned (its launch has no `respawn`); the health monitor reports it.

**Why does the robot stop when the LiDAR is covered?**
A scan that says nothing is never read as free: perception reports every sector BLOCKED, the mux
stops in AUTO and allows only a creep speed in REMOTE.

**Why does a robot not resume after the e-stop is released?**
On purpose. The operator source must re-arm with neutral commands, and the follower keeps an
`estop` pause until `navigation/resume`.

**Can I use another controller or avoidance algorithm?**
Yes, without forking: six controllers and four avoidance policies are built in, and a product
registers its own through the `dharma.controllers` or `dharma.avoidance` entry point groups. See
[Navigation](Navigation.md) and the manual's development chapter.

**Can I use Nav2 instead?**
Dharma does not use Nav2. Its follower publishes `control/nav_cmd_vel`; any planner or
controller that publishes there passes through the same safety mux.

**Does mapping close loops?**
No. Maps are built at the corrected odometry pose; fiducial tags anchor the frame. Put tags along
long loops.

**Where are the maps?**
In sites under `sites_dir` (`~/dharma/map` by default; the bringup's `sites_dir` argument sets it
for localization, mapping and navigation together). See [Mapping and Sites](Mapping-and-Sites.md).

**How do I check a parameter's unit and range?**
`ros2 param describe /<node> <name>`, the Tuning panel, or the manual's parameter tables.

**Was it tested on a real robot?**
The evaluation in the paper is in simulation (core-level closed-loop runs and the full stack on
dharma_sim). Real-robot trials are future work; measure the braking limits on your robot before
it drives on its own.

**Where are the manual and the paper?**
As PDFs in [`docs/pdf/`](../pdf/); `make -C docs pdf` rebuilds them.
