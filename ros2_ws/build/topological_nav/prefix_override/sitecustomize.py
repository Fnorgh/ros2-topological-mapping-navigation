import sys
if sys.prefix == '/usr':
    sys.real_prefix = sys.prefix
    sys.prefix = sys.exec_prefix = '/home/louq0001/robotics/ros2-topological-mapping-navigation/ros2_ws/install/topological_nav'
