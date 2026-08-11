# Driver Controls

Controller: **Xbox controller on USB port 0** in the Driver Station.
Bindings are defined in [`RobotContainer.java`](src/main/java/frc/robot/RobotContainer.java) `configureBindings()`.

## At a glance

| Control | Action | Frame | Notes |
|---|---|---|---|
| Left stick Y | Drive forward / back | Field-centric | Full = `MaxSpeed` (5.0 m/s) |
| Left stick X | Strafe left / right | Field-centric | Full = `MaxSpeed` |
| Right stick X | Rotate CCW / CW | n/a | Full = `MaxAngularRate` (0.75 rot/s) |
| A (hold) | X-lock and brake | n/a | Resist pushing / hold on a slope |
| B (hold) | Point wheels at left stick | n/a | Aim wheels without driving |
| D-pad Up (hold) | Creep straight forward 0.5 m/s | Robot-centric | Precise alignment |
| D-pad Down (hold) | Creep straight back 0.5 m/s | Robot-centric | Precise alignment |
| Left bumper (press) | Reset field-centric heading | n/a | Make "forward" = current facing |
| Back + Y (hold) | SysId dynamic forward | pit only | Characterization |
| Back + X (hold) | SysId dynamic reverse | pit only | Characterization |
| Start + Y (hold) | SysId quasistatic forward | pit only | Characterization |
| Start + X (hold) | SysId quasistatic reverse | pit only | Characterization |

## Everyday driving (default command)

Runs whenever nothing else is commanding the drivetrain.

- **Field-centric**: "forward" is away from your driver station, not wherever the robot is pointed. Push the stick away and the robot moves away from you regardless of how it faces.
- **Left stick** translates (Y = forward/back, X = strafe). **Right stick X** rotates.
- **Speed caps**: full left stick = `MaxSpeed` (currently 5.0 m/s, equal to `kSpeedAt12Volts`); full right stick = `MaxAngularRate` (0.75 rotations/sec).
- **10% deadband** on both sticks so a resting thumb or worn stick will not creep the robot.
- **Open-loop voltage** drive, the right choice for teleop feel.

The negative signs in the code (`-getLeftY()`, etc.) convert the Xbox stick convention (up is negative) to the WPILib convention (forward is positive). Pushing up drives forward.

## Utility buttons

| Button | Action | When to use |
|---|---|---|
| **A** (hold) | Turns all four wheels into an X and brakes | Hold position on a slope, resist being pushed |
| **B** (hold) | Points all wheels toward the left stick direction (no driving) | Pre-align wheels, or debug module direction |
| **D-pad Up** (hold) | Creep straight forward at 0.5 m/s, robot-centric | Precise alignment to a game element |
| **D-pad Down** (hold) | Creep straight back at 0.5 m/s, robot-centric | Precise backing off |
| **Left bumper** (press) | Reset field-centric heading so "forward" is the way the robot faces now | Re-zero if the gyro drifts or you started facing the wrong way |

D-pad creep is **robot-centric**, so it follows the direction the robot is pointed, unlike the sticks.

## Characterization (SysId) — pit use only

These run the automated tests that measure the motors so you can compute real PID gains. Each one sweeps the motors on its own, so run them with room and **not during a match**.

| Combo (hold both) | Test |
|---|---|
| **Back + Y** | Dynamic forward |
| **Back + X** | Dynamic reverse |
| **Start + Y** | Quasistatic forward |
| **Start + X** | Quasistatic reverse |

Run each exactly once per log, then feed the `.hoot` log into the SysId tool. These currently characterize **translation** (drive motors), set by `m_sysIdRoutineToApply` in [`CommandSwerveDrivetrain.java`](src/main/java/frc/robot/subsystems/CommandSwerveDrivetrain.java). Change that field to characterize steer or rotation instead.

## When disabled

The code applies an `Idle` request while disabled, so the drive motors sit in their configured neutral mode (brake or coast) instead of doing anything unexpected.

## Tuning knobs for driver feel

Two lines at the top of `RobotContainer`:

- `MaxSpeed` scales top translation speed (defaults to full `kSpeedAt12Volts`).
- `MaxAngularRate` scales rotation speed (defaults to 0.75 rot/sec).

Some drivers prefer rotation dialed down to about 0.5 for finer aiming. A common addition is a slow / precision mode (for example, hold the right trigger to scale speed down to 30%).
