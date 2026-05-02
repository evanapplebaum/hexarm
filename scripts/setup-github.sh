#!/usr/bin/env bash
# =============================================================================
# setup-github.sh
# One-shot GitHub project setup for hexarm.
# Run AFTER: gh auth login && gh repo create hexarm --public --source=. --push
#
# Usage: bash scripts/setup-github.sh <github-username>
# Example: bash scripts/setup-github.sh evanapplebaum
# =============================================================================

set -e

OWNER="${1:?Usage: $0 <github-username>}"
REPO="hexarm"
R="$OWNER/$REPO"

echo "==> Setting up $R"
echo ""

# =============================================================================
# LABELS
# =============================================================================
echo "--- Creating labels ---"

gh label create "subsystem: cad"         --color "0075ca" --description "Mechanical design and CAD files"         --repo "$R" --force
gh label create "subsystem: firmware"    --color "e4e669" --description "Microcontroller firmware"                --repo "$R" --force
gh label create "subsystem: software"    --color "0e8a16" --description "PC-side kinematics and control"         --repo "$R" --force
gh label create "subsystem: electronics" --color "d93f0b" --description "Schematics, BOM, power design"          --repo "$R" --force
gh label create "subsystem: docs"        --color "5319e7" --description "Documentation and design decisions"     --repo "$R" --force
gh label create "subsystem: build"       --color "b60205" --description "Physical assembly and integration"      --repo "$R" --force
gh label create "type: adr"              --color "c5def5" --description "Architecture Decision Record"           --repo "$R" --force
gh label create "type: bug"              --color "ee0701" --description "Something is broken"                    --repo "$R" --force

echo "Labels created."
echo ""

# =============================================================================
# MILESTONES
# =============================================================================
echo "--- Creating milestones ---"

gh api "repos/$R/milestones" --method POST \
  --field title="M1: CAD Complete" \
  --field description="All individual parts and full assembly modeled in Onshape. STLs exported." \
  --field due_on="2026-05-31T07:00:00Z"

gh api "repos/$R/milestones" --method POST \
  --field title="M2: Electronics & BOM" \
  --field description="Power budget, wiring schematic, and full bill of materials complete. Controller and comms architecture decided." \
  --field due_on="2026-06-21T07:00:00Z"

gh api "repos/$R/milestones" --method POST \
  --field title="M3: Firmware — Servo Control" \
  --field description="ST3215 driver complete. Individual servos controllable by position. Calibration routine working." \
  --field due_on="2026-07-12T07:00:00Z"

gh api "repos/$R/milestones" --method POST \
  --field title="M4: Software — Kinematics" \
  --field description="FK and IK implemented and validated. URDF model created and tested in simulation." \
  --field due_on="2026-08-02T07:00:00Z"

gh api "repos/$R/milestones" --method POST \
  --field title="M5: Physical Build & Integration" \
  --field description="Both arms assembled and wired. End-to-end position control working on real hardware." \
  --field due_on="2026-08-30T07:00:00Z"

gh api "repos/$R/milestones" --method POST \
  --field title="M6: Teleoperation Demo" \
  --field description="Leader-follower teleoperation working. Safety limits in place. Demo video recorded." \
  --field due_on="2026-09-20T07:00:00Z"

echo "Milestones created."
echo ""

# =============================================================================
# ISSUES
# Helper: create_issue <title> <milestone-number> <labels> <body>
# =============================================================================
echo "--- Creating issues ---"

create_issue() {
  local title="$1"
  local milestone="$2"
  local labels="$3"
  local body="$4"
  gh issue create \
    --title "$title" \
    --body "$body" \
    --milestone "$milestone" \
    --label "$labels" \
    --repo "$R"
  sleep 0.5   # avoid rate limiting
}

# --- M1: CAD ---
create_issue \
  "CAD — Design shoulder_pan and shoulder_lift joints" "M1: CAD Complete" \
  "subsystem: cad" \
  "Model the base rotation (shoulder_pan) and first elevation joint (shoulder_lift) in Onshape. Include servo horn interface and any structural brackets. Export STL when done."

create_issue \
  "CAD — Design elbow_flex joint" "M1: CAD Complete" \
  "subsystem: cad" \
  "Model the elbow link and elbow_flex joint. Verify link length matches DH parameter a=112.6mm. Export STL."

create_issue \
  "CAD — Design wrist_flex and wrist_roll joints" "M1: CAD Complete" \
  "subsystem: cad" \
  "Model wrist_flex (a=134.9mm link) and wrist_roll (90° twist joint). Pay attention to the d offsets in the DH table. Export STLs."

create_issue \
  "CAD — Design gripper" "M1: CAD Complete" \
  "subsystem: cad" \
  "Model the gripper end-effector driven by joint 6 (ST3215). Range: -10° to +100°. Should be easy to print and assemble."

create_issue \
  "CAD — Full assembly and collision check" "M1: CAD Complete" \
  "subsystem: cad" \
  "Assemble all parts in Onshape. Check for collisions at joint limits. Verify overall dimensions match expected reach envelope. Export full assembly STL and renders."

create_issue \
  "CAD — Export STLs and renders for repo" "M1: CAD Complete" \
  "subsystem: cad" \
  "Export printable STLs to \`cad/exports/\`. Export at least 2 renders (isometric, side) to \`cad/renders/\` and add a render to the README."

create_issue \
  "Docs — Write hardware-setup.md" "M1: CAD Complete" \
  "subsystem: docs" \
  "Assembly guide: parts list, print settings, assembly order, servo ID assignment, initial wiring. Should be complete enough for someone else to build from."

# --- M2: Electronics ---
create_issue \
  "Electronics — Define servo power budget" "M2: Electronics & BOM" \
  "subsystem: electronics" \
  "Calculate worst-case current draw for 6x ST3215 servos (stall current × derating factor). Size the power supply and any current limiting. Document assumptions."

create_issue \
  "Electronics — Draw wiring schematic" "M2: Electronics & BOM" \
  "subsystem: electronics" \
  "Create schematic covering: power input, voltage regulation, controller, UART/TTL bus to servos, any indicator LEDs or connectors. Save to \`electronics/schematics/\`."

create_issue \
  "Electronics — Create bill of materials (BOM)" "M2: Electronics & BOM" \
  "subsystem: electronics" \
  "Full BOM: servos, fasteners, structural parts, electronics, cables. Include quantity, unit cost, supplier, and part number. Save to \`electronics/bom/\`."

create_issue \
  "ADR-001 — Controller selection" "M2: Electronics & BOM" \
  "subsystem: docs,type: adr" \
  "Document the decision between controller options (bare MCU, Raspberry Pi, laptop over USB, etc.). Cover: real-time requirements, ROS2 compatibility, cost, complexity. Save to \`docs/decisions/adr-001-controller.md\`."

create_issue \
  "ADR-002 — Servo communication topology" "M2: Electronics & BOM" \
  "subsystem: docs,type: adr" \
  "Document the decision on how to talk to 6x ST3215 servos: individual UART lines vs half-duplex bus. Cover: wiring complexity, latency, firmware difficulty, expandability. Save to \`docs/decisions/adr-002-servo-comms.md\`."

# --- M3: Firmware ---
create_issue \
  "Firmware — ST3215 driver (UART register read/write)" "M3: Firmware — Servo Control" \
  "subsystem: firmware" \
  "Implement low-level driver for ST3215 over UART: packet framing, CRC, read/write register functions. At minimum: set goal position, read present position, read present load."

create_issue \
  "Firmware — Position control with joint limits" "M3: Firmware — Servo Control" \
  "subsystem: firmware" \
  "Wrap the ST3215 driver with joint-level position commands that enforce the limits from the DH table. Soft-stop before hard limits."

create_issue \
  "Firmware — Multi-servo synchronization" "M3: Firmware — Servo Control" \
  "subsystem: firmware" \
  "Send position commands to all 6 servos in a synchronized way (sync write or timed sequential). Verify all joints reach their targets within an acceptable latency window."

create_issue \
  "Firmware — Calibration routine (zero position)" "M3: Firmware — Servo Control" \
  "subsystem: firmware" \
  "Implement a routine to set and store each servo's zero/home position. Should be runnable at startup to account for assembly variation."

create_issue \
  "Docs — Write servo-protocol.md" "M3: Firmware — Servo Control" \
  "subsystem: docs" \
  "Document the ST3215 communication protocol: packet format, key registers (goal position, present position, torque enable, etc.), timing requirements. Should serve as quick reference during firmware development."

# --- M4: Software ---
create_issue \
  "Software — Implement forward kinematics" "M4: Software — Kinematics" \
  "subsystem: software" \
  "Implement FK using the Modified DH parameters in \`docs/kinematics.md\`. Input: joint angles (radians). Output: 4×4 homogeneous transform of end-effector. Save to \`software/kinematics/\`."

create_issue \
  "Software — Validate FK against known poses" "M4: Software — Kinematics" \
  "subsystem: software" \
  "Write test cases for at least 3 known configurations (home, fully extended, etc.). Compare FK output against manually computed or simulated ground truth. Document results."

create_issue \
  "Software — Implement geometric IK (joints 1–3)" "M4: Software — Kinematics" \
  "subsystem: software" \
  "Implement closed-form geometric IK for the first 3 joints (position of the wrist center). Handle both elbow-up and elbow-down solutions. Return joint angles and validity flag."

create_issue \
  "Software — Implement wrist decoupling (joints 4–5)" "M4: Software — Kinematics" \
  "subsystem: software" \
  "Implement orientation IK for wrist_flex and wrist_roll given the desired end-effector orientation and the solved joints 1–3."

create_issue \
  "Software — Joint limit enforcement" "M4: Software — Kinematics" \
  "subsystem: software" \
  "Add joint limit checking to IK output. Return an error/flag when the requested pose is unreachable within joint limits. No silent clamping."

create_issue \
  "URDF — Create robot model" "M4: Software — Kinematics" \
  "subsystem: software" \
  "Create a URDF for hexarm based on the DH parameters and CAD geometry. Include visual and collision meshes. Save to \`simulation/urdf/\`."

create_issue \
  "URDF — Validate in RViz / simulation" "M4: Software — Kinematics" \
  "subsystem: software" \
  "Load URDF in RViz (or similar). Verify joint axes, link lengths, and range of motion visually match the physical arm design."

# --- M5: Build ---
create_issue \
  "Build — Print and source all parts" "M5: Physical Build & Integration" \
  "subsystem: build" \
  "3D print all structural parts using settings from hardware-setup.md. Order all BOM components. Verify fit before full assembly."

create_issue \
  "Build — Assemble leader arm" "M5: Physical Build & Integration" \
  "subsystem: build" \
  "Assemble the leader (human-operated) arm following hardware-setup.md. Set servo IDs, run calibration routine, verify range of motion."

create_issue \
  "Build — Assemble follower arm" "M5: Physical Build & Integration" \
  "subsystem: build" \
  "Assemble the follower (robot-controlled) arm. Set servo IDs (different range from leader). Run calibration."

create_issue \
  "Build — Wire electronics" "M5: Physical Build & Integration" \
  "subsystem: build,subsystem: electronics" \
  "Wire both arms to the controller per the schematic. Label all connectors. Verify power rails before powering servos."

create_issue \
  "Integration — End-to-end position control test" "M5: Physical Build & Integration" \
  "subsystem: build,subsystem: firmware,subsystem: software" \
  "Command each joint through its full range via software. Verify actual servo positions match commanded positions. Log any errors."

create_issue \
  "Docs — Write control-loop.md" "M5: Physical Build & Integration" \
  "subsystem: docs" \
  "Document the leader-follower control architecture: data flow, timing, latency budget, how firmware and software communicate. Include a block diagram."

# --- M6: Teleoperation ---
create_issue \
  "Software — Leader-follower control loop" "M6: Teleoperation Demo" \
  "subsystem: software" \
  "Implement the real-time loop that reads leader joint positions and commands the follower to mirror them. Target update rate: ≥20 Hz."

create_issue \
  "Software — Safety limits and emergency stop" "M6: Teleoperation Demo" \
  "subsystem: software,subsystem: firmware" \
  "Implement: joint limit enforcement at software level, torque cutoff on fault, and a keyboard/button emergency stop that disables all servos immediately."

create_issue \
  "Demo — Record demo video and GIF" "M6: Teleoperation Demo" \
  "subsystem: docs" \
  "Record a short demo of the leader-follower system in operation. Export a GIF for the README and a full video for documentation."

echo ""
echo "==> All done! Check your repo at: https://github.com/$R"
echo ""
echo "Next step: set up a GitHub Project board"
echo "  1. Go to https://github.com/$OWNER?tab=projects"
echo "  2. New project → Board template"
echo "  3. Link it to the hexarm repo"
echo "  4. Add columns: Backlog | In Progress | In Review | Done"
echo "  5. Import issues — they'll show up filtered by milestone"
