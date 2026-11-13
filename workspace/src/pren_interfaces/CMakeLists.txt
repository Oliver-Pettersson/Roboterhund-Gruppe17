cmake_minimum_required(VERSION 3.8)
project(pren_interfaces)

find_package(ament_cmake REQUIRED)
find_package(rosidl_default_generators REQUIRED)
find_package(std_msgs REQUIRED)

rosidl_generate_interfaces(${PROJECT_NAME}
  "msg/BoneDetection.msg"
  "msg/DogCommand.msg"
  "msg/DogSignal.msg"
  "msg/Posture.msg"
  "msg/RobotState.msg"
  DEPENDENCIES std_msgs
)

ament_export_dependencies(rosidl_default_runtime)
ament_package()
