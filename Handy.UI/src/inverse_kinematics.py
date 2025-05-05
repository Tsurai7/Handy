# inverse_kinematics.py

import numpy as np
import ikpy.chain
import ikpy.utils.plot as plot_utils
from matplotlib import pyplot as plt
from scipy.spatial.transform import Rotation as R # Optional: for orientation control

# --------------------------------------------------------------------------
# ---             ROBOT ARM PHYSICAL PARAMETERS (MUST BE EDITED)         ---
# --------------------------------------------------------------------------
# Define the lengths of your robot arm's links IN METERS.
# Measure these carefully from axis of rotation to axis of rotation.
# These are crucial for IK accuracy. Replace the example values below.

LINK_BASE_TO_1 = 0.05  # Example: Height from base to axis of servo 0 (along Z)
LINK_1_TO_2 = 0.10   # Example: Length from axis 0 to axis 1 (e.g., along X or Y)
LINK_2_TO_3 = 0.12   # Example: Length from axis 1 to axis 2
LINK_3_TO_4 = 0.08   # Example: Length from axis 2 to axis 3
LINK_4_TO_5 = 0.06   # Example: Length from axis 3 to axis 4 (wrist/gripper base)
LINK_5_TO_TIP = 0.04 # Example: Length from axis 4/5 to the Tool Center Point (TCP)

# --------------------------------------------------------------------------
# ---             ROBOT ARM CHAIN DEFINITION (MUST BE EDITED)            ---
# --------------------------------------------------------------------------
# Define the kinematic chain using ikpy.
# Specify the 'rotation' axis ([1,0,0] for X, [0,1,0] for Y, [0,0,1] for Z)
# and the 'origin_translation' (vector from previous joint's origin to this joint's origin)
# for each link. The structure depends entirely on YOUR robot arm design.

# This is an EXAMPLE structure - ADAPT IT TO YOUR ARM:
robot_chain = ikpy.chain.Chain(name='my_robot_arm', links=[
    ikpy.link.URDFLink( # Link 0: Base -> Servo 0 (e.g., rotation around Z)
      name="base_servo_0",
      origin_translation=[0, 0, LINK_BASE_TO_1], # Example: Move up from base
      origin_orientation=[0, 0, 0],
      rotation=[0, 0, 1], # Example: Rotate around Z
    ),
    ikpy.link.URDFLink( # Link 1: Servo 0 -> Servo 1 (e.g., shoulder pitch around Y)
      name="link1_servo_1",
      origin_translation=[0, 0, 0], # Example: No offset if axes coincide initially
      origin_orientation=[0, 0, 0],
      rotation=[0, 1, 0], # Example: Rotate around Y
    ),
    ikpy.link.URDFLink( # Link 2: Servo 1 -> Servo 2 (e.g., elbow pitch around Y)
      name="link2_servo_2",
      origin_translation=[LINK_1_TO_2, 0, 0], # Example: Move along previous link's X axis
      origin_orientation=[0, 0, 0],
      rotation=[0, 1, 0], # Example: Rotate around Y
    ),
     ikpy.link.URDFLink( # Link 3: Servo 2 -> Servo 3 (e.g., forearm pitch around Y)
      name="link3_servo_3",
      origin_translation=[LINK_2_TO_3, 0, 0], # Example: Move along previous link's X axis
      origin_orientation=[0, 0, 0],
      rotation=[0, 1, 0], # Example: Rotate around Y
    ),
    ikpy.link.URDFLink( # Link 4: Servo 3 -> Servo 4 (e.g., wrist roll around X)
      name="link4_servo_4",
      origin_translation=[LINK_3_TO_4, 0, 0], # Example: Move along previous link's X axis
      origin_orientation=[0, 0, 0],
      rotation=[1, 0, 0], # Example: Rotate around X
    ),
     ikpy.link.URDFLink( # Link 5: Servo 4 -> Servo 5 (e.g., wrist pitch/gripper base around Y)
      name="link5_servo_5",
      origin_translation=[LINK_4_TO_5, 0, 0], # Example: Move along previous link's X axis
      origin_orientation=[0, 0, 0],
      rotation=[0, 1, 0], # Example: Rotate around Y
    ),
    # Add a non-movable link representing the tool tip (TCP)
     ikpy.link.URDFLink(
      name="tcp",
      origin_translation=[LINK_5_TO_TIP, 0, 0], # Example: Move from last servo axis to the actual tip
      origin_orientation=[0, 0, 0],
      rotation=[0, 0, 0], # No rotation associated with this link
    )
])

# --------------------------------------------------------------------------
# ---                    SERVO LIMITS AND MASK                           ---
# --------------------------------------------------------------------------

# Define which links in the chain correspond to actual servos
# Must match the order of movable links defined above. Length should match number of servos (6).
# Example: If the first 6 links defined above are servos, and the last is TCP:
active_link_mask = [True, True, True, True, True, True, False] # True for servo links, False for fixed/TCP

# Servo angle limits in DEGREES [[min, max], [min, max], ...]
# Should match the order of your servos (0 to 5) and Arduino limits
servo_limits_deg = [
  [0, 180], # Servo 0
  [0, 180], # Servo 1
  [0, 180], # Servo 2
  [0, 180], # Servo 3
  [0, 180], # Servo 4
  [17, 90]  # Servo 5 (Gripper)
]

# --------------------------------------------------------------------------
# ---                    CORE IK CALCULATION FUNCTION                    ---
# --------------------------------------------------------------------------

def calculate_inverse_kinematics(target_position, target_orientation_matrix=None, initial_angles_rad=None):
    """
    Calculates the inverse kinematics for a target pose.

    Args:
        target_position (list/np.array): Target [X, Y, Z] coordinates in meters.
        target_orientation_matrix (np.array, optional): 3x3 rotation matrix for target orientation. Defaults to None (position only).
        initial_angles_rad (list/np.array, optional): Initial joint angles in radians (including non-active links).
                                                     Length must match len(robot_chain.links). Defaults to None (uses zero vector).

    Returns:
        np.array: Calculated joint angles in radians (including non-active links), or None if calculation fails.
    """
    if initial_angles_rad is None:
        # Use zero vector matching the chain length if no initial position provided
        initial_angles_rad = [0.0] * len(robot_chain.links)
    elif len(initial_angles_rad) != len(robot_chain.links):
        print(f"Error: Length of initial_angles_rad ({len(initial_angles_rad)}) does not match chain length ({len(robot_chain.links)}).")
        return None

    # Determine orientation mode based on whether target_orientation_matrix is provided
    # 'all': Match position and full orientation
    # 'Z': Match position and the Z-axis orientation of the end-effector
    # None: Match position only
    orientation_mode = "Z" if target_orientation_matrix is not None else None
    # You might want 'all' for full 6-DOF control, but 'Z' is often sufficient and more stable

    try:
        calculated_angles_rad = robot_chain.inverse_kinematics(
            target_position=target_position,
            target_orientation=target_orientation_matrix,
            orientation_mode=orientation_mode,
            initial_position=initial_angles_rad,
            # --- Optional parameters for tuning ---
            # max_iter=10,       # Limit solver iterations
            # tolerance=0.01,    # Position tolerance in meters
            # joint_limits=None # ikpy can use bounds defined in URDFLink, but clipping afterwards is often simpler
        )
        print(f"IK Solver Raw Output (radians): {calculated_angles_rad}")
        return calculated_angles_rad

    except Exception as e:
        print(f"Error during IK calculation: {e}")
        # You might want to check for specific exception types if needed
        return None

# --------------------------------------------------------------------------
# ---          HELPER FUNCTION FOR LIMITS AND DEGREE CONVERSION          ---
# --------------------------------------------------------------------------

def apply_limits_and_convert_to_deg(calculated_angles_rad):
    """
    Applies servo limits and converts active joint angles to degrees.

    Args:
        calculated_angles_rad (np.array): Raw output from calculate_inverse_kinematics
                                          (length must match len(robot_chain.links)).

    Returns:
        list: List of 6 final angles in degrees, constrained by servo_limits_deg,
              or None if input is invalid.
    """
    if calculated_angles_rad is None or len(calculated_angles_rad) != len(robot_chain.links):
        print("Error: Invalid input angles for applying limits.")
        return None

    # 1. Convert all angles to degrees
    all_angles_deg = np.degrees(calculated_angles_rad)

    # 2. Select only the angles corresponding to active links (servos)
    active_angles_deg_raw = [angle for angle, active in zip(all_angles_deg, active_link_mask) if active]

    # 3. Check if we got the expected number of angles (should be 6)
    if len(active_angles_deg_raw) != len(servo_limits_deg):
        print(f"Error: Number of active angles ({len(active_angles_deg_raw)}) doesn't match number of servo limits ({len(servo_limits_deg)}). Check active_link_mask.")
        return None

    # 4. Apply limits to each active angle
    final_angles_deg = []
    print("Applying limits:")
    for i, angle in enumerate(active_angles_deg_raw):
        min_lim, max_lim = servo_limits_deg[i]
        constrained_angle = np.clip(angle, min_lim, max_lim)

        # Optional: Warn if clipping was significant
        if abs(constrained_angle - angle) > 1.0: # More than 1 degree difference
            print(f"  - Servo {i}: Clipped {angle:.2f} -> {constrained_angle:.2f} (Limits: [{min_lim}, {max_lim}])")

        final_angles_deg.append(constrained_angle)

    return final_angles_deg

# --------------------------------------------------------------------------
# ---               OPTIONAL: FORWARD KINEMATICS FUNCTION                ---
# --------------------------------------------------------------------------

def get_forward_kinematics(joint_angles_deg):
    """
    Calculates the forward kinematics (end-effector pose) from joint angles.

    Args:
        joint_angles_deg (list): List of 6 servo angles in degrees.

    Returns:
        tuple: (position (list [x,y,z]), orientation_matrix (3x3 np.array)), or (None, None) if error.
    """
    if len(joint_angles_deg) != active_link_mask.count(True):
         print(f"Error: FK requires {active_link_mask.count(True)} angles, got {len(joint_angles_deg)}.")
         return None, None

    # Create the full angle vector for the chain, including non-active links (set to 0)
    full_angles_rad = np.zeros(len(robot_chain.links))
    active_indices = [i for i, active in enumerate(active_link_mask) if active]

    if len(active_indices) != len(joint_angles_deg):
         print("Error: Mismatch between active link mask and number of input angles for FK.")
         return None, None

    for i, angle_deg in enumerate(joint_angles_deg):
         full_angles_rad[active_indices[i]] = np.radians(angle_deg)

    try:
        # Calculate FK - returns a 4x4 transformation matrix
        fk_matrix = robot_chain.forward_kinematics(full_angles_rad)
        position = fk_matrix[:3, 3].tolist() # Extract position [x, y, z]
        orientation_matrix = fk_matrix[:3, :3] # Extract 3x3 rotation matrix
        return position, orientation_matrix
    except Exception as e:
        print(f"Error during FK calculation: {e}")
        return None, None

# --------------------------------------------------------------------------
# ---                   OPTIONAL: VISUALIZATION FUNCTION                 ---
# --------------------------------------------------------------------------
def visualize_chain(angles_deg=None, target_position=None, ax=None):
    """
    Visualizes the robot chain using matplotlib.

    Args:
        angles_deg (list, optional): List of 6 servo angles in degrees.
                                     If None, uses a default central position. Defaults to None.
        target_position (list, optional): Target [x,y,z] to display. Defaults to None.
        ax (matplotlib.axes._axes.Axes, optional): The 3D axes object to plot onto.
                                                  If None, a new figure and axes are created. Defaults to None.
    """
    show_plot = False # Flag to indicate if we need to call plt.show()

    if angles_deg is None:
        # Default angles if none provided (e.g., 90 deg, gripper centered)
        angles_deg = [90.0] * 6
        if len(servo_limits_deg) >= 6: # Ensure limits are defined
             angles_deg[5] = np.mean(servo_limits_deg[5]) # Center gripper based on its limits
        print("Visualizing with default angles.")

    if len(angles_deg) != active_link_mask.count(True):
        print(f"Error: Visualization requires {active_link_mask.count(True)} angles, got {len(angles_deg)}.")
        return

    # Create the full angle vector in radians for ikpy chain
    full_angles_rad = np.zeros(len(robot_chain.links))
    active_indices = [i for i, active in enumerate(active_link_mask) if active]
    for i, angle_deg in enumerate(angles_deg):
        full_angles_rad[active_indices[i]] = np.radians(angle_deg)

    # --- Check if axes are provided ---
    if ax is None:
        print("No axes provided, creating new figure for visualization.")
        fig, ax = plot_utils.init_3d_figure()
        show_plot = True # Need to show the plot if we created the figure
    # --- End Check ---

    # Plot the robot chain using ikpy's plotting utility
    robot_chain.plot(full_angles_rad, ax, target=target_position)

    # Set labels and limits for clarity
    ax.set_xlabel("X (m)")
    ax.set_ylabel("Y (m)")
    ax.set_zlabel("Z (m)")
    # Calculate approximate reach for setting axis limits dynamically
    max_reach = sum([abs(l) for l in [LINK_BASE_TO_1, LINK_1_TO_2, LINK_2_TO_3, LINK_3_TO_4, LINK_4_TO_5, LINK_5_TO_TIP]]) + 0.05 # Add margin
    ax.set_xlim(-max_reach, max_reach)
    ax.set_ylim(-max_reach, max_reach)
    ax.set_zlim(0, max_reach * 1.1) # Start Z axis from 0
    ax.view_init(elev=30., azim=45) # Adjust initial camera angle if needed

    if show_plot:
        print("Showing robot chain plot...")
        plt.show() # Show the plot only if we created the figure here


# Example usage (for testing this file directly)
if __name__ == "__main__":
    print("Testing Inverse Kinematics Module...")

    # Example Target
    test_target_pos = [0.15, 0.05, 0.10] # meters
    print(f"\nTest Target Position: {test_target_pos} m")

    # --- Test IK ---
    print("\nCalculating IK...")
    # Use current angles (e.g., all 90 deg) as initial guess
    initial_q_deg = [90, 90, 90, 90, 90, 45] # 6 servo angles
    initial_q_full_rad = np.zeros(len(robot_chain.links))
    active_indices = [i for i, active in enumerate(active_link_mask) if active]
    for i, angle_deg in enumerate(initial_q_deg):
         initial_q_full_rad[active_indices[i]] = np.radфians(angle_deg)

    calculated_rad = calculate_inverse_kinematics(test_target_pos, initial_angles_rad=initial_q_full_rad)

    if calculated_rad is not None:
        final_deg = apply_limits_and_convert_to_deg(calculated_rad)
        if final_deg is not None:
            print(f"\nFinal Calculated Angles (degrees): {[f'{a:.2f}' for a in final_deg]}")

            # --- Test FK ---
            print("\nCalculating FK based on result...")
            fk_pos, fk_orient = get_forward_kinematics(final_deg)
            if fk_pos is not None:
                print(f"  - FK Position: [{fk_pos[0]:.4f}, {fk_pos[1]:.4f}, {fk_pos[2]:.4f}] m")
                # Compare with target
                error = np.linalg.norm(np.array(test_target_pos) - np.array(fk_pos))
                print(f"  - Position Error: {error:.4f} m")
                # print("  - FK Orientation Matrix:\n", fk_orient)

            # --- Visualize ---
            print("\nVisualizing result...")
            visualize_chain(final_deg, target_position=test_target_pos)

        else:
            print("\nFailed to apply limits to IK result.")
    else:
        print("\nIK calculation failed (Target might be unreachable or error occurred).")

    print("\nTest complete.")