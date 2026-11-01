# patrol_node -> patrol/status (latched): the patrol running or the last one, the schedule.

uint8 IDLE = 0            # no patrol yet
uint8 STARTING = 1        # checks, re-anchoring at the dock, standing up, loading the route
uint8 RUNNING = 2         # the follower patrols the route
uint8 DONE = 3            # the route's end was reached
uint8 FAILED = 4          # a start step or the follower failed
uint8 STOPPED = 5         # stopped by an operator (patrol/stop, navigation/stop)
uint8 RETURNING = 6       # walking the route back to the dock (watchdog or patrol/return)

std_msgs/Header header
uint8 state
string site
string route              # the route file (empty: the route loaded last)
float64 started           # unix time, s (0: never)
float32 elapsed_sec
uint32 points             # inspection points inspected on this patrol
uint32 attention          # findings per severity on this patrol
uint32 warning
uint32 critical
uint8 worst               # Finding.NORMAL ... CRITICAL
string report             # the patrol summary on the robot (json)
bool returned             # the patrol ended by walking back to the dock
float32 battery           # fraction, -1: unknown
bool schedule_enabled
string next_scheduled     # local time of the next scheduled patrol, e.g. "14:00" (empty: none)
string message
