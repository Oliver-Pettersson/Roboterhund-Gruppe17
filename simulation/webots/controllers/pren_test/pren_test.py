from controller import Robot

robot = Robot()
timestep = int(robot.getBasicTimeStep())

# Motoren
left_motor = robot.getDevice("left wheel")
right_motor = robot.getDevice("right wheel")

left_motor.setPosition(float("inf"))
right_motor.setPosition(float("inf"))

# Encoder / PositionSensor
left_encoder = robot.getDevice("left wheel sensor")
right_encoder = robot.getDevice("right wheel sensor")

left_encoder.enable(timestep)
right_encoder.enable(timestep)

# langsam geradeaus fahren
left_motor.setVelocity(2.0)
right_motor.setVelocity(2.0)

while robot.step(timestep) != -1:
    left_position = left_encoder.getValue()
    right_position = right_encoder.getValue()

    print(
        f"Links: {left_position:.3f} rad | "
        f"Rechts: {right_position:.3f} rad"
    )