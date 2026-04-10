# ROS2 Gesture-Controlled Navigation

Gesture-based navigation using the TurtleBot 4 with autonomous execution.

## Project Overview

The robot performs two distinct phases:

1. **Manual Mapping Run** — A human operator drives the TurtleBot 4 through the environment. During this traversal, the robot builds a map using SLAM, recording obstacles and key navigation points. Three tour landmarks are identified and stored.

2. **Autonomous Tour Run** — The robot waits at home for a hand gesture command. A visitor holds up 1, 2, or 3 fingers to send the robot to the corresponding landmark. At each landmark the robot scans the QR code and speaks a description of that stop. A wave gesture sends the robot back home.

## Hand Gesture Commands

| Gesture   | Action                 |
|-----------|------------------------|
| 1 finger  | Navigate to Landmark 1 |
| 2 fingers | Navigate to Landmark 2 |
| 3 fingers | Navigate to Landmark 3 |
| Wave      | Return home            |

## Hardware

- **Robot:** TurtleBot 4
- **Sensors:** RGB Camera (gesture detection, QR codes), LiDAR (SLAM/obstacle avoidance)

---

## First-Time Setup (run once per machine)

### 1. Build the package

```bash
cd ~/robotics/ros2-topological-mapping-navigation/ros2_ws
colcon build --packages-select topological_nav
```

### 2. Set up venv for mediapipe

```bash
cd ~/robotics/ros2-topological-mapping-navigation/ros2_ws
pip install --user --break-system-packages virtualenv
~/.local/bin/virtualenv --system-site-packages venv
venv/bin/pip install -r requirements.txt
venv/bin/pip install ultralytics
venv/bin/pip install "numpy<2"
touch venv/COLCON_IGNORE
```

---

## Quick Start — Shell Scripts

Edit the top 3 lines in each script for your robot before running:

```bash
ROBOT_NAME="snapper"
ROS_DOMAIN_ID="4"
ROS_DISCOVERY_SERVER=";;;;10.194.16.39:11811;"
```

Make executable (once):

```bash
chmod +x ~/robotics/ros2-topological-mapping-navigation/start_mapping.sh
chmod +x ~/robotics/ros2-topological-mapping-navigation/start_person_follow.sh
```

| Script | Purpose | Opens |
|--------|---------|-------|
| `./start_mapping.sh` | Phase 1 — build map, drive around | SLAM + RViz + Teleop |
| `./start_person_follow.sh` | Phase 2 — detect and follow person | Person follow + Speak listener |
| `./start.sh` | All nodes at once | Everything |

---

## Running the System (manual)

### Step 1 — Find your robot's environment settings

Each robot has a different domain ID and discovery server. Run this to get your robot's settings:

```bash
printf "<robot_name>" | robot-setup.sh
```

Example:
```bash
printf "leatherback" | robot-setup.sh
```

Output example:
```
export ROS_DOMAIN_ID=6
export ROS_DISCOVERY_SERVER=";;;;;;10.194.16.40:11811;"
```

Use those exact values in every terminal below.

Valid robot names: `snapper`, `loggerhead`, `testudo`, `galapagos`, `terrapin`, `leatherback`, `hawksbill`, `matamata`, `softshell`

---

### Terminal 1 — Launch SLAM + RViz + all nodes

```bash
cd ~/robotics/ros2-topological-mapping-navigation/ros2_ws
source install/setup.bash
ros2 launch topological_nav topological_nav.launch.xml robot_name:=<robot_name>
```

---

### Terminal 2 — Keyboard teleop

```bash
unset ROS_LOCALHOST_ONLY
export ROS_DOMAIN_ID=<id>
export ROS_DISCOVERY_SERVER="<server>"
export ROS_SUPER_CLIENT=True
ros2 daemon stop && ros2 daemon start
ros2 run teleop_twist_keyboard teleop_twist_keyboard --ros-args -p stamped:=true
```

Teleop keys:
- `i` — forward
- `,` — backward
- `j` — turn left
- `l` — turn right
- `k` — stop

---

### Terminal 3 — Camera feed

```bash
unset ROS_LOCALHOST_ONLY
export ROS_DOMAIN_ID=<id>
export ROS_DISCOVERY_SERVER="<server>"
export ROS_SUPER_CLIENT=True
ros2 daemon stop && ros2 daemon start
ros2 run rqt_image_view rqt_image_view
```

Select `/oakd/rgb/preview/image_raw` from the dropdown.

---

### Terminal 4 — Gesture node (if not started by launch)

```bash
unset ROS_LOCALHOST_ONLY
export ROS_DOMAIN_ID=<id>
export ROS_DISCOVERY_SERVER="<server>"
export ROS_SUPER_CLIENT=True
ros2 daemon stop && ros2 daemon start
source ~/robotics/ros2-topological-mapping-navigation/ros2_ws/install/setup.bash
~/robotics/ros2-topological-mapping-navigation/ros2_ws/venv/bin/python -m topological_nav.gesture_node
```

---

### Terminal 5 — Verify gestures are detected

```bash
unset ROS_LOCALHOST_ONLY
export ROS_DOMAIN_ID=<id>
export ROS_DISCOVERY_SERVER="<server>"
export ROS_SUPER_CLIENT=True
ros2 daemon stop && ros2 daemon start
ros2 topic echo /gesture
```

Show fingers to the camera — you should see numbers printing:
- `1`, `2`, `3` — finger count
- `10` — wave gesture

---

### RViz setup

In RViz:
1. Set **Fixed Frame** to `map`
2. Click **Add** → **By topic** → `/map` → **Map** → OK
3. Click **Add** → **By topic** → `/scan` → **LaserScan** → OK

---

### Save the map when done driving

```bash
unset ROS_LOCALHOST_ONLY
export ROS_DOMAIN_ID=<id>
export ROS_DISCOVERY_SERVER="<server>"
export ROS_SUPER_CLIENT=True
ros2 daemon stop && ros2 daemon start
ros2 run nav2_map_server map_saver_cli -f ~/map
```

This saves `~/map.pgm` and `~/map.yaml`.

---

## Phase 2: Autonomous Tour (after mapping)

### 1. Get landmark coordinates

Drive the robot to each landmark and run:
```bash
ros2 topic echo /odom --once
```

Note the `x`, `y` values from `pose.pose.position` for each landmark.

### 2. Fill in coordinates

Edit `ros2_ws/src/topological_nav/topological_nav/tour_manager.py` lines 17-23:

```python
LANDMARK_POSITIONS = {
    1: (x1, y1, theta1),
    2: (x2, y2, theta2),
    3: (x3, y3, theta3),
}
HOME_POSITION = (x0, y0, theta0)
```

### 3. Rebuild and launch

```bash
cd ~/robotics/ros2-topological-mapping-navigation/ros2_ws
colcon build --packages-select topological_nav
source install/setup.bash
ros2 launch topological_nav topological_nav.launch.xml robot_name:=<robot_name>
```

### 4. Test gestures

Show 1, 2, or 3 fingers to the camera to navigate to landmarks. Wave to return home.

---

## Person Follow Mode

The robot detects people via the OAK-D camera (YOLOv8n) and drives toward them, announcing "feet detected" on the connecting computer.

### Quick start (recommended)

```bash
~/robotics/ros2-topological-mapping-navigation/start_person_follow.sh
```

### Manual start

#### Step 1 — Start the person follow launch (robot)

```bash
unset ROS_LOCALHOST_ONLY && export ROS_DOMAIN_ID=<id> && export ROS_DISCOVERY_SERVER="<server>" && export ROS_SUPER_CLIENT=True
source ~/robotics/ros2-topological-mapping-navigation/ros2_ws/install/setup.bash
ros2 launch topological_nav person_follow.launch.xml robot_name:=<robot_name>
```

#### Step 2 — Start the speak listener (connecting computer — plays audio here)

```bash
source ~/robotics/ros2-topological-mapping-navigation/ros2_ws/install/setup.bash
python3 ~/robotics/ros2-topological-mapping-navigation/ros2_ws/src/topological_nav/topological_nav/speak_listener.py
```

#### Step 3 — Enable following

```bash
unset ROS_LOCALHOST_ONLY && export ROS_DOMAIN_ID=<id> && export ROS_DISCOVERY_SERVER="<server>" && export ROS_SUPER_CLIENT=True
ros2 topic pub /person_follow_active std_msgs/Bool "data: true"
```

To stop following:
```bash
ros2 topic pub --once /person_follow_active std_msgs/Bool "data: false"
```

---

## Paradigm

This project follows a hybrid robotic paradigm:

- **Deliberative:** Uses a map and goal-based planning
- **Reactive:** Responds to gestures and obstacles in real time

## Team

University robotics project — TurtleBot 4 gesture-controlled navigation system.
