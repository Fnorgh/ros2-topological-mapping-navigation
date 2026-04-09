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
touch venv/COLCON_IGNORE
```

---

## Running the System

### Step 1 — Find your robot's environment settings

Each robot has a different domain ID and discovery server. Run this to get your robot's settings:

```bash
printf "<robot_name>" | robot-setup.sh
```

For example:
```bash
printf "leatherback" | robot-setup.sh
```

It will print something like:
```
export ROS_DOMAIN_ID=6
export ROS_DISCOVERY_SERVER=";;;;;;10.194.16.40:11811;"
```

Use those values in all terminals below.

Valid robot names: `snapper`, `loggerhead`, `testudo`, `galapagos`, `terrapin`, `leatherback`, `hawksbill`, `matamata`, `softshell`

---

### Step 2 — Terminal 1: Launch SLAM + RViz + all nodes

```bash
cd ~/robotics/ros2-topological-mapping-navigation/ros2_ws
source install/setup.bash
ros2 launch topological_nav topological_nav.launch.xml robot_name:=<robot_name>
```

Replace `<robot_name>` with your robot, e.g. `robot_name:=leatherback`

---

### Step 3 — Terminal 2: Keyboard teleop (to drive and map)

Use the exact domain ID and discovery server from Step 1:

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

### Step 4 — Terminal 3: View camera feed

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

### Step 5 — Set up RViz to see the map

In RViz:
1. Set **Fixed Frame** to `map`
2. Click **Add** → **By topic** → `/map` → **Map** → OK
3. Click **Add** → **By topic** → `/scan` → **LaserScan** → OK

Drive the robot around slowly to build the map. Cover the full area including all landmarks.

---

### Step 6 — Save the map when done

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

1. Fill in the landmark coordinates in `ros2_ws/src/topological_nav/topological_nav/tour_manager.py` lines 17-23 using positions from the saved map
2. Rebuild:

```bash
cd ~/robotics/ros2-topological-mapping-navigation/ros2_ws
colcon build --packages-select topological_nav
source install/setup.bash
ros2 launch topological_nav topological_nav.launch.xml robot_name:=<robot_name>
```

3. Show 1, 2, or 3 fingers to the camera to navigate to landmarks
4. Wave to return home

---

## Paradigm

This project follows a hybrid robotic paradigm:

- **Deliberative:** Uses a map and goal-based planning
- **Reactive:** Responds to gestures and obstacles in real time

## Team

University robotics project — TurtleBot 4 gesture-controlled navigation system.
