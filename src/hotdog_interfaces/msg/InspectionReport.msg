# inspection_node -> inspection/report: everything measured at one inspection point.

uint8 DONE = 0            # every target measured
uint8 PARTIAL = 1         # some targets could not be measured (pod or camera missing, timeout)
uint8 FAILED = 2          # nothing could be measured
uint8 NO_TARGETS = 3      # no inspection point here: nothing to do

std_msgs/Header header
string site
string point              # inspection point name
float64 x                 # m, map frame: where the robot stood
float64 y
uint8 state
uint8 severity            # the highest severity of the findings (Finding.NORMAL ... CRITICAL)
Finding[] findings
string directory          # the report on the robot: report.json and the images
float32 duration_sec
string message
