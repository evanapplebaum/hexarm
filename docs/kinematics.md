# Hexarm — Kinematics

## Overview

Hexarm is a 5-DOF serial manipulator with 1 additional gripper DOF. All joints are revolute. This document covers the kinematic model used for motion planning and control.

---

## Denavit-Hartenberg Parameters

The Modified DH (Craig) convention is used. Each row defines the transform from frame `i-1` to frame `i`.

| Joint | Name | a (mm) | α (°) | d (mm) | θ offset (°) | Limits (°) |
|---|---|---|---|---|---|---|
| 1 | shoulder_pan   |    0.0 |   0 |  62.4 |   0 | −110 to +110 |
| 2 | shoulder_lift  |   38.8 | −90 |   0.0 | −90 | −100 to +100 |
| 3 | elbow_flex     |  112.6 |   0 | −28.0 |   0 |  −97 to  +97 |
| 4 | wrist_flex     |  134.9 |   0 |   5.2 |   0 |  −95 to  +95 |
| 5 | wrist_roll     |    0.0 |  90 |  61.1 |   0 | −157 to +163 |
| 6 | gripper        |   20.2 |  90 |   0.0 |   0 |  −10 to +100 |

> Parameters derived from URDF joint origins. Small off-axis offsets (< 5 mm) are absorbed into nearest DH parameter. See [derivation notes](#derivation-notes) below.

### Parameter Definitions (Modified DH)

- **a** — link length: distance along xᵢ from zᵢ to zᵢ₊₁
- **α** — link twist: angle about xᵢ from zᵢ to zᵢ₊₁
- **d** — link offset: distance along zᵢ₋₁ from xᵢ₋₁ to xᵢ
- **θ** — joint angle (variable for revolute joints; column shows zero-config offset)

---

## Forward Kinematics

The transform from frame `i-1` to frame `i` using Modified DH:

```
T(i-1 → i) = Rx(αᵢ₋₁) · Tx(aᵢ₋₁) · Rz(θᵢ) · Tz(dᵢ)
```

The full end-effector pose (base → EE):

```
T_EE = T₁ · T₂ · T₃ · T₄ · T₅ · T₆
```

*(Implementation: `software/kinematics/`)*

---

## Inverse Kinematics

*(To be written once FK is implemented and validated)*

Planned approach: geometric IK for joints 1–3, decoupled wrist for joints 4–5.

---

## Derivation Notes

Parameters were derived from the SO-100 URDF joint origins (xyz + rpy transforms), converted to Modified DH convention by:

1. Computing each joint's 4×4 homogeneous transform from its URDF `origin` tag
2. Identifying each joint's Z-axis in the previous frame
3. Finding common normals between consecutive Z-axes
4. Reading off a, α, d, θ from the resulting frame assignments

The SO-100 URDF uses non-standard frame orientations (several π rotations) as a modeling convention, which introduces θ offsets at joints 1 and 2.

**Reference:** [TheRobotStudio/SO-ARM100](https://github.com/TheRobotStudio/SO-ARM100)
