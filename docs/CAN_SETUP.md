# CAN Bus Setup Sheet (print me)

Assign each device the CAN ID below in **Phoenix Tuner X**, set its **device name** to match,
and physically label the device and its wire. All devices go on the **CANivore bus named `canivore`**.

If any device ends up on the roboRIO CAN bus instead, either move it or change `kCANBus` in
`TunerConstants.java` from `"canivore"` to `"rio"`.

## Devices

| Position | Device | Tuner device name | CAN ID | ID set | FW updated | Labeled |
|---|---|---|---|:---:|:---:|:---:|
| IMU (center) | Pigeon 2.0 | `Pigeon2` | **1** | [ ] | [ ] | [ ] |
| Front Left | Kraken X60 (drive) | `FL-Drive` | **2** | [ ] | [ ] | [ ] |
| Front Left | Kraken X44 (steer) | `FL-Steer` | **3** | [ ] | [ ] | [ ] |
| Front Left | CANcoder | `FL-Encoder` | **4** | [ ] | [ ] | [ ] |
| Front Right | Kraken X60 (drive) | `FR-Drive` | **5** | [ ] | [ ] | [ ] |
| Front Right | Kraken X44 (steer) | `FR-Steer` | **6** | [ ] | [ ] | [ ] |
| Front Right | CANcoder | `FR-Encoder` | **7** | [ ] | [ ] | [ ] |
| Back Left | Kraken X60 (drive) | `BL-Drive` | **8** | [ ] | [ ] | [ ] |
| Back Left | Kraken X44 (steer) | `BL-Steer` | **9** | [ ] | [ ] | [ ] |
| Back Left | CANcoder | `BL-Encoder` | **10** | [ ] | [ ] | [ ] |
| Back Right | Kraken X60 (drive) | `BR-Drive` | **11** | [ ] | [ ] | [ ] |
| Back Right | Kraken X44 (steer) | `BR-Steer` | **12** | [ ] | [ ] | [ ] |
| Back Right | CANcoder | `BR-Encoder` | **13** | [ ] | [ ] | [ ] |

## How to do it without ID collisions

Every new CTRE device ships as **CAN ID 0**. If you power up all four drive Krakens at once,
they are all ID 0 and Tuner cannot tell them apart. So:

1. Connect and power **one device at a time** (or use Tuner's **Blink** button to confirm which
   physical device you have selected before changing its ID).
2. Set its **CAN ID** and **device name** from the table.
3. **Update firmware** while you are in there (all devices should match the season's firmware).
4. Physically **label** the device and its CAN wire (masking tape and a marker is fine).
5. Check the three boxes and move to the next device.

## MK5n A/B layout caution

MK5n modules are not symmetric: they come in mirrored **A** and **B** layouts, two of each on a
typical drivetrain. Make sure the module in each corner is the correct layout before you wire it,
and keep the CAN ID with the corner (not the specific module) so a swapped module keeps its ID.

## After all 13 are set

- In Tuner, open the CAN bus view and confirm you see **13 devices, no red/duplicate IDs**.
- When the robot is assembled, run the **Swerve Project Generator** in Tuner. It writes these
  IDs (plus measured encoder offsets and inverts) into `TunerConstants.java` automatically.
