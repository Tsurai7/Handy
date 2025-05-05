# main_app.py (Your original file with modifications)

import json
import time
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import serial
import serial.tools.list_ports
import requests
import numpy as np
from PIL import Image, ImageTk, ImageDraw, ImageFont
import cv2
import threading

# --- NEW: Import the IK module ---
import inverse_kinematics as ik
# from scipy.spatial.transform import Rotation as R # Import if using orientation

# --- NEW: Matplotlib imports for embedding ---
import matplotlib
matplotlib.use('TkAgg') # Explicitly use Tkinter backend for Matplotlib
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from mpl_toolkits.mplot3d import Axes3D # Required for 3D plotting


# --- Check if these imports are still needed or handled elsewhere ---
try:
    # Assuming globals.py defines paths, maybe slider list initially
    from globals import sliders, YOLO_WEIGHTS, YOLO_CONFIG, YOLO_CLASSES
    print("Loaded variables from globals.py")
except ImportError:
    print("Warning: globals.py not found or error loading. Using placeholders.")
    # Define placeholders if globals.py is missing/problematic
    YOLO_WEIGHTS = 'yolov4.weights' # Placeholder path
    YOLO_CONFIG = 'yolov4.cfg'     # Placeholder path
    YOLO_CLASSES = 'coco.names'    # Placeholder path
    sliders = [] # Initialize slider list here if not in globals

try:
    # Assuming helpers.py contains find_esp32_camera and possibly old slider controls
    import helpers
    print("Loaded helpers.py")
except ImportError:
    print("Warning: helpers.py not found. Some functionality might be missing.")
    # Define placeholder if needed
    class HelpersPlaceholder:
        def find_esp32_camera(self):
            print("helpers.py not found, using default camera URL.")
            return 'http://192.168.1.100' # Default fallback URL
        # Add placeholder methods for increase/decrease_slider if keybindings use them
        def increase_slider(self, slider_num): pass
        def decrease_slider(self, slider_num): pass
    helpers = HelpersPlaceholder()


try:
    # Assuming ui.py contains show_toast
    import ui
    print("Loaded ui.py")
except ImportError:
    print("Warning: ui.py not found. Toast notifications disabled.")
     # Define placeholder if needed
    class UiPlaceholder:
        def show_toast(self, msg, level):
             print(f"Toast ({level}): {msg}") # Print toast to console
    ui = UiPlaceholder()
# --- End Optional Imports Handling ---


# Constants
current_distance = 0.0 # Use float
BAUDRATE = 9600

# --- Load YOLOv4 model (Keep your existing code) ---
yolo_loaded = False
CLASS_NAMES = []
try:
    net = cv2.dnn.readNet(YOLO_WEIGHTS, YOLO_CONFIG)
    layer_names = net.getLayerNames()
    # Correctly get output layer indices
    output_layer_indices = net.getUnconnectedOutLayers()
    if isinstance(output_layer_indices[0], (list, np.ndarray)):
        output_layers = [layer_names[i[0] - 1] for i in output_layer_indices]
    else:
         output_layers = [layer_names[i - 1] for i in output_layer_indices]

    with open(YOLO_CLASSES, "r") as f:
        CLASS_NAMES = [line.strip() for line in f.readlines()]
    yolo_loaded = True
    print("YOLO model loaded successfully.")
except Exception as e:
    print(f"Error loading YOLO model: {e}")
    # Keep the messagebox if desired
    messagebox.showerror("YOLO Error", f"Could not load YOLO model.\nPlease check paths in globals.py or code.\nError: {e}")

# Global variables
ser = None # Initialize ser to None
camera_connected = True
# Get camera URL using helper or default - with validation
raw_camera_url = helpers.find_esp32_camera()
if raw_camera_url == "Camera not found" or not raw_camera_url or not raw_camera_url.startswith(('http://', 'https://')):
    print(f"Camera helper returned invalid URL: '{raw_camera_url}'. Disabling camera.")
    camera_url = None
    camera_connected = False
else:
    camera_url = raw_camera_url
    camera_connected = True


# --- NEW: Global variables for Matplotlib plot ---
mpl_fig = None
mpl_ax = None
mpl_canvas = None
# --- End Matplotlib Globals ---

# --- NEW: Function to send formatted angles ---
def send_angles_to_arduino(angles_deg):
    """Formats angle list [<a0>, <a1>...] and sends to Arduino."""
    global ser # Ensure we're checking the global ser
    if not isinstance(angles_deg, (list, np.ndarray)) or len(angles_deg) != 6:
        print(f"Error: send_angles_to_arduino expects a list/array of 6 angles, got: {angles_deg}")
        return

    # Check if serial port is initialized and open BEFORE trying to use it
    if ser is not None and ser.is_open:
        # Round angles to integers before sending
        angles_str = [str(int(round(a))) for a in angles_deg]
        command = "<" + ",".join(angles_str) + ">\n"
        try:
            ser.write(command.encode('utf-8'))
            print(f"Sent Command: {command.strip()}")
        except serial.SerialException as e:
            print(f"Serial Error on Write: {e}")
            messagebox.showerror("Serial Error", f"Failed to write to serial port: {e}")
            # Consider closing the port or attempting reconnection
        except Exception as e:
            print(f"Unexpected error during serial write: {e}")
    else:
        # print("Serial port not connected. Cannot send angles.") # Reduce console spam
        pass # Silently do nothing if port isn't ready

# --- MODIFY create_slider ---
# Keep track of value labels separately
slider_value_labels = {}

def create_slider(root_widget, row, slider_number): # Renamed root -> root_widget for clarity
    """Creates a slider mainly for displaying IK results."""
    global slider_value_labels # Ensure we modify the global dict

    # Use limits from the IK module
    try:
        min_val, max_val = ik.servo_limits_deg[slider_number]
    except IndexError:
        print(f"Error: Slider number {slider_number} out of range for ik.servo_limits_deg.")
        min_val, max_val = 0, 180 # Fallback limits

    # Calculate a safe initial value within limits
    initial_val = np.clip(90, min_val, max_val)
    if slider_number == 5: # Special case for gripper
        initial_val = np.clip(45, min_val, max_val)

    # Label to display the current value
    value_label = ttk.Label(root_widget, text=f"Servo {slider_number}: {int(initial_val)}°")
    value_label.grid(row=row, column=0, padx=5, pady=2, sticky="w") # Use row directly
    slider_value_labels[slider_number] = value_label # Store the label widget

    slider = ttk.Scale(
        root_widget,
        from_=min_val,
        to=max_val,
        orient="horizontal",
        length=250, # Adjusted length slightly
        # Command only updates the visual label, does NOT send serial commands
        command=lambda val, sn=slider_number, lbl=value_label: lbl.config(text=f"Servo {sn}: {int(float(val))}°")
    )
    slider.set(initial_val)
    slider.grid(row=row, column=1, padx=5, pady=2, sticky="ew")
    # Make the column containing the slider expand within its parent frame
    root_widget.grid_columnconfigure(1, weight=1)
    return slider


def create_sliders(parent_frame):
    """Create sliders within the specified parent frame."""
    # This assumes sliders is defined globally or passed correctly
    global sliders
    # Clear previous slider widgets if they exist in the list
    for s in sliders:
        if s.winfo_exists():
            s.destroy()
    sliders.clear()
    # Clear labels as well
    global slider_value_labels
    for lbl in slider_value_labels.values():
         if lbl.winfo_exists():
              lbl.destroy()
    slider_value_labels.clear()

    print(f"Creating {len(ik.servo_limits_deg)} sliders...")
    for i in range(len(ik.servo_limits_deg)): # Create based on limits defined in IK module
        slider = create_slider(parent_frame, i, i) # Pass parent frame, use index for row
        sliders.append(slider)


# --- Serial Port Handling ---
def update_serial_port(portName):
    """Update serial port connection."""
    global ser
    if ser and ser.is_open:
        try:
            ser.close()
            print("Previous serial port closed.")
        except Exception as e:
            print(f"Error closing previous serial port: {e}")
    ser = None # Reset ser variable

    if portName and portName != "Select a Port":
        try:
            # Added timeout for non-blocking reads
            ser = serial.Serial(portName, BAUDRATE, timeout=0.1)
            print(f"Connected to serial port: {portName}")
            # Clear any lingering error messages about serial port (optional)
        except serial.SerialException as e:
            ser = None # Ensure ser is None on failure
            messagebox.showerror("Serial Port Error", f"Could not open serial port {portName}: {e}")
            print(f"Could not open serial port {portName}: {e}")
            if 'port_combobox' in globals() and port_combobox.winfo_exists():
                 port_combobox.set("Select a Port") # Reset dropdown on error
        except Exception as e:
             ser = None # Ensure ser is None on failure
             messagebox.showerror("Error", f"An unexpected error occurred opening {portName}: {e}")
             print(f"An unexpected error occurred opening {portName}: {e}")
             if 'port_combobox' in globals() and port_combobox.winfo_exists():
                  port_combobox.set("Select a Port")
    else:
        print("Serial port disconnected or not selected.")


def get_data_from_serial():
    """Reads data from serial and handles messages."""
    global ser # Declare intention to use the global 'ser'
    global current_distance

    # Check if 'ser' exists globally and is not None and is open before trying to access attributes
    if 'ser' in globals() and ser is not None and ser.is_open:
        try:
            while ser.in_waiting > 0: # Process all available lines
                line = ser.readline()
                if not line: continue
                message = line.decode('utf-8', errors='ignore').strip()
                if not message: continue

                # Minimal console logging for received messages
                # print(f"Serial RX: {message}")

                if message.startswith("Distance: "):
                    handle_distance_message(message)
                elif message.startswith("Message: "):
                    handle_info_message(message)
                elif message.startswith("Error: "):
                    handle_error_message(message)
                # Add handling for other specific messages from Arduino if needed

        except serial.SerialException as e:
            print(f"Serial read error: {e}. Closing port.")
            # ui.show_toast(f"Serial Error: {e}. Disconnecting.", "Error") # Use your UI method
            if ser: # Check again before closing
                try:
                     ser.close()
                except Exception as close_err:
                     print(f"Error closing serial port after read error: {close_err}")
            ser = None # Assign None to the global variable
            if 'port_combobox' in globals() and port_combobox.winfo_exists(): # Check if GUI element exists
                 port_combobox.set("Select a Port") # Reset dropdown
        except Exception as e:
            # Catch other potential errors like decode errors if 'ignore' fails
            print(f"Error processing serial data: {e}")
    # else: # Optional: Handle cases where ser is None or closed
    #     pass

    # Reschedule the check regardless of connection status
    # Check if root exists before scheduling
    if 'root' in globals() and root.winfo_exists():
         root.after(100, get_data_from_serial) # Check every 100ms

def handle_distance_message(message):
    """Handles 'Distance:' messages, converting value to float."""
    global current_distance
    try:
        # Extract digits and decimal point for robust float conversion
        distance_str = message.split(":", 1)[1]
        value_part = ''.join(filter(lambda x: x.isdigit() or x == '.', distance_str))
        if value_part: # Check if we extracted something
            distance_value = float(value_part)
            current_distance = distance_value
            # Update label, ensure label exists
            if 'distance_label' in globals() and distance_label.winfo_exists():
                distance_label.config(text=f"Distance: {distance_value:.1f} cm")
        else:
             print(f"Could not parse float from distance message: '{message}'")
    except (ValueError, IndexError) as e:
        print(f"Error parsing distance message: '{message}'. Error: {e}")


def handle_info_message(message):
    """Handles 'Message:' messages."""
    info = message.split(": ", 1)[1] if ": " in message else message
    print(f"Arduino Info: {info}")
    # ui.show_toast(f"Info: {info}", "Info") # Use your UI method


def handle_error_message(message):
    """Handles 'Error:' messages."""
    error_info = message.split(": ", 1)[1] if ": " in message else message
    print(f"Arduino Error: {error_info}")
    # ui.show_toast(f"Error: {error_info}", "Error") # Use your UI method


# --- Camera and Object Detection Functions ---
def detect_objects(image, distance):
    """Detect objects in the image using YOLOv4 (ensure yolo_loaded check)."""
    if not yolo_loaded:
        return image # Return original image if model isn't loaded

    blob = cv2.dnn.blobFromImage(image, 0.00392, (416, 416), (0, 0, 0), True, crop=False)
    net.setInput(blob)
    try:
        detections = net.forward(output_layers)
    except Exception as e:
         print(f"Error in YOLO forward pass: {e}")
         return image # Return original on error

    height, width, _ = image.shape
    boxes, confidences, class_ids = [], [], []

    for out in detections:
        for detection in out:
            scores = detection[5:]
            class_id = np.argmax(scores)
            confidence = scores[class_id]
            if confidence > 0.5: # Confidence threshold
                center_x = int(detection[0] * width)
                center_y = int(detection[1] * height)
                w = int(detection[2] * width)
                h = int(detection[3] * height)
                x = int(center_x - w / 2)
                y = int(center_y - h / 2)

                boxes.append([x, y, w, h])
                confidences.append(float(confidence))
                class_ids.append(class_id)

    indices = cv2.dnn.NMSBoxes(boxes, confidences, 0.5, 0.4)

    # Handle different return types/shapes of indices from NMSBoxes
    processed_indices = []
    if isinstance(indices, np.ndarray):
         processed_indices = indices.flatten()
    elif isinstance(indices, tuple) and len(indices) > 0: # Older OpenCV might return tuple
         processed_indices = np.array(indices).flatten()

    if len(processed_indices) > 0:
        for i in processed_indices:
            if i < len(boxes): # Bounds check for safety
                x, y, w, h = boxes[i]
                label_text = "Unknown"
                try:
                    if class_ids[i] < len(CLASS_NAMES):
                         label_text = CLASS_NAMES[class_ids[i]]
                except IndexError:
                     print(f"Warning: class_id {class_ids[i]} out of range for CLASS_NAMES.")

                # Format distance to one decimal place
                label = f"{label_text}: {confidences[i]:.2f}, Dist: {distance:.1f} cm"
                color = (0, 255, 0)
                cv2.rectangle(image, (x, y), (x + w, y + h), color, 2)
                cv2.putText(image, label, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

    return image


def get_image_from_camera():
    """Capture image from the camera URL, improved error handling."""
    global camera_connected, camera_url

    # Check if URL is set and seems valid before trying
    if not camera_url or not isinstance(camera_url, str) or not camera_url.startswith(('http://', 'https://')):
        if camera_connected: # Print only once when becoming disconnected
             print(f"Invalid or missing camera URL: '{camera_url}'")
             camera_connected = False
        return None

    if not camera_connected:
        return None # Don't try if already marked as disconnected

    try:
        response = requests.get(camera_url, timeout=5) # 5 second timeout
        response.raise_for_status() # Check for HTTP errors (4xx, 5xx)

        image_array = np.array(bytearray(response.content), dtype=np.uint8)
        img = cv2.imdecode(image_array, cv2.IMREAD_COLOR)

        if img is None:
            print("Error: Failed to decode image from camera stream.")
            # Consider it a temporary failure, don't immediately set camera_connected to False
            return None

        # If we get here, connection is working (or working again)
        if not camera_connected:
             print("Camera reconnected successfully.")
             camera_connected = True # Explicitly mark as connected on success after failure

        return img

    except requests.exceptions.Timeout:
        if camera_connected: # Log only on transition to disconnected
             print(f"Timeout connecting to camera URL: {camera_url}")
             camera_connected = False
        return None
    except requests.exceptions.RequestException as e:
        if camera_connected:
             print(f"Error connecting to camera URL '{camera_url}': {e}")
             camera_connected = False
        return None
    except Exception as e:
        if camera_connected:
             print(f"Unexpected error getting camera image: {e}")
             camera_connected = False
        return None

def create_placeholder_image(text, subtext="Check connection or URL"):
     """Creates a placeholder image with text."""
     width, height = 640, 480 # Standard size or adjust as needed
     img = Image.new('RGB', (width, height), color=(220, 220, 220)) # Light gray
     draw = ImageDraw.Draw(img)
     # Use default font which should always be available
     font_large = ImageFont.load_default()
     font_small = ImageFont.load_default() # Use default for subtext too

     # Simple centered text using textlength for older PIL/Pillow or textbbox
     try:
         # Modern method using textbbox
         text_bbox = draw.textbbox((0, 0), text, font=font_large)
         subtext_bbox = draw.textbbox((0, 0), subtext, font=font_small)
         text_width = text_bbox[2] - text_bbox[0]
         text_height = text_bbox[3] - text_bbox[1]
         subtext_width = subtext_bbox[2] - subtext_bbox[0]
     except AttributeError:
         # Fallback for older versions using textsize/textlength
         text_width, text_height = draw.textlength(text, font=font_large), 20 # Approximate height
         subtext_width, _ = draw.textlength(subtext, font=font_small), 15

     draw.text(((width - text_width) / 2, (height / 2) - text_height), text, fill="black", font=font_large)
     draw.text(((width - subtext_width) / 2, (height / 2) + 5), subtext, fill="gray", font=font_small)
     return img

def update_image_in_thread():
    """Captures, processes image in thread, updates UI."""
    global camera_connected # Allow modification
    last_connect_attempt_time = 0
    reconnect_interval = 10 # Seconds between reconnect attempts

    while True:
        # Check if the root window still exists before doing anything
        if not root.winfo_exists():
             print("Root window closed, stopping image thread.")
             break

        current_time = time.time()
        img_to_display = None

        if camera_connected:
            image = get_image_from_camera() # Tries to get image, updates camera_connected on failure
            if image is not None:
                try:
                    image_processed = detect_objects(image, current_distance) # Use global distance
                    image_rgb = cv2.cvtColor(image_processed, cv2.COLOR_BGR2RGB)
                    img_to_display = Image.fromarray(image_rgb)
                except Exception as e:
                    print(f"Error processing image: {e}")
                    img_to_display = create_placeholder_image("Processing Error")
            # If get_image_from_camera returned None, camera_connected might be False now.

        # This block executes if camera was already disconnected OR failed in the attempt above
        if not camera_connected:
            img_to_display = create_placeholder_image("Camera Disconnected")
            # Try reconnecting periodically ONLY if URL is set
            if camera_url and (current_time - last_connect_attempt_time > reconnect_interval):
                 print("Attempting to reconnect camera...")
                 last_connect_attempt_time = current_time
                 # Setting camera_connected True allows get_image_from_camera to try
                 # It will be set back to False immediately if it fails again
                 camera_connected = True

        if img_to_display is None: # Should not happen with current logic, but as a fallback
             img_to_display = create_placeholder_image("No Image Source")


        # --- Update UI safely ---
        try:
            # Resize image before converting to Tkinter format? (Optional)
            # max_disp_w, max_disp_h = 640, 480
            # img_to_display.thumbnail((max_disp_w, max_disp_h))

            tk_image = ImageTk.PhotoImage(image=img_to_display)
            # Schedule UI update in main thread only if root exists
            if root.winfo_exists():
                root.after(0, update_ui_image, tk_image)

        except Exception as e:
            print(f"Error updating UI with image: {e}")
            # Don't break the loop for UI errors unless the window is gone

        time.sleep(0.1) # ~10 FPS target


def update_ui_image(tk_image):
    """Safely updates the camera label widget in the main thread."""
    # Check if the label widget still exists before configuring it
    if 'camera_label' in globals() and camera_label.winfo_exists():
        camera_label.imgtk = tk_image # Keep reference
        camera_label.configure(image=tk_image)


# --- JSON Command Loading ---
def execute_command(servo_number, angle):
    """Sets a single servo angle (used by JSON loader). Sends ALL current angles."""
    global sliders, slider_value_labels # Ensure access to globals

    if not sliders: return # Don't do anything if sliders aren't created

    if 0 <= servo_number < len(sliders):
        # Apply limits defined in the IK module
        min_lim, max_lim = ik.servo_limits_deg[servo_number]
        angle = np.clip(float(angle), min_lim, max_lim) # Ensure angle is float for np.clip

        sliders[servo_number].set(angle) # Update the display slider
        # Update the corresponding label if it exists
        if servo_number in slider_value_labels and slider_value_labels[servo_number].winfo_exists():
            slider_value_labels[servo_number].config(text=f"Servo {servo_number}: {int(round(angle))}°")

        print(f"Direct Angle Command: Servo {servo_number} -> {angle:.1f}°")

        # CRITICAL: Send the complete set of current angles from all sliders
        current_angles_all = [s.get() for s in sliders]
        send_angles_to_arduino(current_angles_all)
    else:
        print(f"Error: Invalid servo number {servo_number} in execute_command")


def load_commands_from_json(filename):
    """Load and execute commands from a JSON file."""
    global root # Need root for messagebox parent
    print(f"Loading commands from: {filename}")
    try:
        with open(filename, 'r') as file:
            data = json.load(file)
    except FileNotFoundError:
        messagebox.showerror("File Error", f"File not found: {filename}", parent=root)
        return
    except json.JSONDecodeError as e:
        messagebox.showerror("JSON Error", f"Error decoding JSON in {filename}:\n{e}", parent=root)
        return
    except Exception as e:
        messagebox.showerror("File Error", f"Could not read file {filename}:\n{e}", parent=root)
        return

    command_list = data.get("commands", [])
    if not command_list:
        messagebox.showinfo("Info", "No 'commands' found in JSON file.", parent=root)
        return

    # Use a flag for aborting the sequence (can be set by other parts of app if needed)
    abort_sequence = threading.Event()

    def run_sequence(cmds):
        """Recursively runs command sequences."""
        for item in cmds:
            if abort_sequence.is_set(): return False # Check for abort signal

            # Check serial connection before command (optional, depends on desired behavior)
            # if ser is None or not ser.is_open:
            #      print("Warning: Serial port disconnected during script execution.")
                 # messagebox.showwarning("Serial Error", "Serial port disconnected. Aborting script.", parent=root)
                 # abort_sequence.set()
                 # return False

            cmd_type = list(item.keys())[0] # Get the first key as command type
            cmd_data = item[cmd_type]

            if cmd_type == "servo":
                if "id" in cmd_data and "angle" in cmd_data:
                    execute_command(cmd_data["id"], cmd_data["angle"])
                    delay = cmd_data.get("delay_after", 0.5)
                    time.sleep(delay)
                else: print(f"Warning: Invalid 'servo' command format: {item}")
            elif cmd_type == "repeatable":
                count = cmd_data.get("repeats", 1)
                seq = cmd_data.get("sequence", [])
                delay_rep = cmd_data.get("delay_after_repeat", 0.5)
                for _ in range(count):
                    if not run_sequence(seq): return False # Abort if sub-sequence aborts
                    time.sleep(delay_rep)
            elif cmd_type == "comment":
                print(f"Script Comment: {cmd_data}")
            elif cmd_type == "coordinate_target":
                 coords = cmd_data.get("position", None)
                 orient_euler = cmd_data.get("orientation_euler_xyz_deg", None)
                 if coords and len(coords) == 3:
                      print(f"Script IK Target: Pos={coords}, Orient={orient_euler}")
                      target_orient_matrix = None
                      # --- Optional: Convert Euler to Matrix ---
                      # if orient_euler and len(orient_euler) == 3:
                      #     try:
                      #         from scipy.spatial.transform import Rotation as R
                      #         target_orient_matrix = R.from_euler('xyz', orient_euler, degrees=True).as_matrix()
                      #         print("  - Orientation Matrix created.")
                      #     except Exception as e:
                      #         print(f"  - Error converting Euler angles: {e}")
                      # --- End Optional ---

                      # Use wrapper to call IK trigger safely in main thread
                      trigger_ik_from_script(coords, target_orient_matrix)

                      delay = cmd_data.get("delay_after", 1.0) # Allow time for move
                      time.sleep(delay)
                 else:
                      print(f"Warning: Invalid 'coordinate_target' format: {item}")
            else:
                print(f"Warning: Unknown command type '{cmd_type}' in script: {item}")

            # Allow GUI to update slightly during long scripts
            if 'root' in globals() and root.winfo_exists():
                 root.update_idletasks()

        return True # Sequence part completed successfully

    print("Starting JSON script execution...")
    success = run_sequence(command_list) # Run the main sequence

    if success:
        print("JSON script finished.")
        # Optional: Show completion message
        # messagebox.showinfo("Script", "Command script finished.", parent=root)
    else:
        print("JSON script aborted.")
        # Optional: Show aborted message
        # messagebox.showwarning("Script", "Command script aborted.", parent=root)


def load_commands_from_file():
    """Opens file dialog and starts JSON execution in a new thread."""
    filename = filedialog.askopenfilename(
        title="Select JSON Command File",
        filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")],
        parent=root # Make dialog appear over the main window
    )
    if filename:
        # Run the potentially long-running load_commands_from_json in a thread
        script_thread = threading.Thread(target=load_commands_from_json, args=(filename,), daemon=True)
        script_thread.start()


def update_visualization(angles_deg, target_position=None):
    """Clears and redraws the 3D robot arm visualization."""
    # Используем глобальные переменные для графика
    global mpl_ax, mpl_canvas, root

    # Проверяем, инициализированы ли элементы графика и существует ли окно
    if mpl_ax is None or mpl_canvas is None or not root.winfo_exists():
        # print("Visualization axes/canvas not ready or root window closed.")
        return

    # Проверяем корректность входных углов
    if angles_deg is None or len(angles_deg) != ik.active_link_mask.count(True):
        print(f"Invalid angles provided for visualization: {angles_deg}")
        # Рисуем дефолтное положение при ошибке
        angles_deg = [90.0] * ik.active_link_mask.count(True)
        if len(angles_deg) >= 6: angles_deg[5] = np.mean(ik.servo_limits_deg[5])

    # print(f"Updating visualization with angles: {[f'{a:.1f}' for a in angles_deg]}")

    try:
        # Очищаем предыдущее содержимое осей
        mpl_ax.cla()

        # Вызываем функцию визуализации из модуля ik, передавая оси Matplotlib
        ik.visualize_chain(angles_deg=angles_deg, target_position=target_position, ax=mpl_ax)

        # Можно переустановить заголовок или другие элементы осей после cla()
        mpl_ax.set_title("Robot Arm Visualization")

        # Перерисовываем холст Tkinter
        # draw_idle() лучше подходит для GUI, чтобы не блокировать интерфейс
        mpl_canvas.draw_idle()
        # print("Visualization updated.") # Уменьшим спам в консоль

    except Exception as e:
        print(f"Error updating visualization: {e}")


# --- IK Trigger Function ---
def trigger_ik_calculation(target_pos_m, target_orient_matrix=None):
     """Handles the process of calculating IK and updating the robot/visualization."""
     global root, sliders, slider_value_labels # Ensure access to globals needed
     print("-" * 20)
     print(f"Triggering IK for Target: Pos={target_pos_m}, Orient={'Provided' if target_orient_matrix is not None else 'None'}")

     # 1. Get current angles from sliders (degrees) for initial guess
     if not sliders:
          if root.winfo_exists(): messagebox.showerror("GUI Error", "Slider widgets not initialized.", parent=root)
          return
     # Ensure sliders still exist before getting values
     current_angles_deg = []
     for s in sliders:
          if s.winfo_exists():
               current_angles_deg.append(s.get())
          else:
               print("Warning: A slider widget was destroyed.")
               # Handle missing slider - maybe use default or abort? Using 90 for now.
               current_angles_deg.append(90.0)

     if len(current_angles_deg) != ik.active_link_mask.count(True):
         print(f"Warning: Number of sliders ({len(current_angles_deg)}) doesn't match expected active links ({ik.active_link_mask.count(True)}). Using defaults.")
         # Fallback to default angles if slider count is wrong
         current_angles_deg = [90.0] * ik.active_link_mask.count(True)
         if len(current_angles_deg) >= 6: current_angles_deg[5] = np.mean(ik.servo_limits_deg[5])


     # 2. Convert current angles to radians and format for IK solver input
     initial_q_full_rad = np.zeros(len(ik.robot_chain.links))
     active_indices = [i for i, active in enumerate(ik.active_link_mask) if active]
     if len(active_indices) != len(current_angles_deg):
          if root.winfo_exists(): messagebox.showerror("IK Setup Error", "Mismatch between active links mask and number of angles.", parent=root)
          return
     for i, angle_deg in enumerate(current_angles_deg):
          initial_q_full_rad[active_indices[i]] = np.radians(angle_deg)
     # print(f"Initial Guess (rad): {[f'{a:.3f}' for a in initial_q_full_rad]}")


     # 3. Call the IK calculation function from the kinematics module
     calculated_rad = ik.calculate_inverse_kinematics(
         target_position=target_pos_m,
         target_orientation_matrix=target_orient_matrix,
         initial_angles_rad=initial_q_full_rad
     )

     # 4. Process the result
     if calculated_rad is not None:
          # 5. Apply limits and convert to degrees
          final_angles_deg = ik.apply_limits_and_convert_to_deg(calculated_rad)

          if final_angles_deg is not None:
               print(f"IK Success. Final Angles (deg): {[f'{a:.1f}' for a in final_angles_deg]}")
               # 6. Update GUI Sliders & Labels
               for i, angle in enumerate(final_angles_deg):
                    if i < len(sliders) and sliders[i].winfo_exists():
                         sliders[i].set(angle)
                         if i in slider_value_labels and slider_value_labels[i].winfo_exists():
                              slider_value_labels[i].config(text=f"Servo {i}: {int(round(angle))}°")

               # 7. Send angles to Arduino (if connected)
               send_angles_to_arduino(final_angles_deg) # Function already checks connection

               # 8. Update Visualization
               update_visualization(final_angles_deg, target_pos_m)

               # 9. Optional: Calculate and print FK for verification
               fk_pos, _ = ik.get_forward_kinematics(final_angles_deg)
               if fk_pos:
                    error = np.linalg.norm(np.array(target_pos_m) - np.array(fk_pos))
                    print(f"FK Verification: Pos={fk_pos}, Error={error:.4f}m")

          else:
               # Failed during limit application/conversion
               if root.winfo_exists(): messagebox.showerror("IK Error", "Failed processing IK result (limits/conversion).", parent=root)
     else:
          # IK calculation itself failed
          if root.winfo_exists(): messagebox.showwarning("IK Warning", "Inverse kinematics failed.\nTarget may be unreachable or outside joint limits.", parent=root)
     print("-" * 20)


# --- Wrapper for GUI Button Click ---
def on_go_button_click():
    """Reads target from GUI entries and calls the main IK trigger function."""
    global root, entry_x, entry_y, entry_z # Ensure access to GUI elements
    try:
        # Read values from entry fields, convert to float (METERS)
        target_x = float(entry_x.get())
        target_y = float(entry_y.get())
        target_z = float(entry_z.get())
        target_pos_m = [target_x, target_y, target_z]

        # TODO: Add reading and conversion for orientation if implemented
        target_orient = None # Placeholder

        # Call the main trigger function
        trigger_ik_calculation(target_pos_m, target_orient)

    except ValueError:
        if root.winfo_exists(): messagebox.showerror("Input Error", "Please enter valid numeric values for X, Y, Z coordinates (in meters).", parent=root)
    except Exception as e:
        if root.winfo_exists(): messagebox.showerror("Error", f"An unexpected error occurred: {e}", parent=root)
        print(f"Error in on_go_button_click: {e}")


# --- Wrapper to call IK trigger from script thread safely ---
def trigger_ik_from_script(target_pos_m, target_orient_matrix=None):
     """Schedules the IK trigger function to run in the main GUI thread."""
     global root
     if root.winfo_exists():
          # Use root.after to ensure thread safety for GUI updates and serial commands
          root.after(0, trigger_ik_calculation, target_pos_m, target_orient_matrix)


# --- GUI Setup ---
root = tk.Tk()
root.geometry("1200x800") # Adjusted size
root.title("Handy IK Controller v2 + Visualization")
try:
    # Make sure the path is relative to where you run the script, or use absolute path
    icon = tk.PhotoImage(file='./icons/icon.png') # Example: relative path
    root.iconphoto(True, icon)
except tk.TclError:
    print("Warning: Could not load application icon './icons/icon.png'.")

# --- GUI Frames ---
# Frame for left panel (IK + Servo)
left_panel = ttk.Frame(root, padding="5")
left_panel.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

# Frame for right panel (Camera + Visualization)
right_panel = ttk.Frame(root, padding="5")
right_panel.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)

# Configure grid weights for resizing
root.grid_columnconfigure(0, weight=1) # Allow left panel to expand slightly if needed
root.grid_columnconfigure(1, weight=3) # Right panel takes more space
root.grid_rowconfigure(0, weight=1) # Allow rows to expand vertically


# --- Left Panel Widgets ---
# Top controls (Serial, Load) Frame
top_controls_frame = ttk.Frame(left_panel)
top_controls_frame.pack(side=tk.TOP, fill=tk.X, pady=5)

ttk.Label(top_controls_frame, text="Serial Port:").pack(side=tk.LEFT, padx=(0, 5))
available_ports = ["Select a Port"] + [port.device for port in serial.tools.list_ports.comports()]
port_combobox = ttk.Combobox(top_controls_frame, values=available_ports, state="readonly", width=15)
port_combobox.pack(side=tk.LEFT, padx=5)
port_combobox.set("Select a Port")
port_combobox.bind("<<ComboboxSelected>>", lambda event: update_serial_port(port_combobox.get()))

load_file_button = ttk.Button(top_controls_frame, text="Load Script", command=load_commands_from_file, width=12)
load_file_button.pack(side=tk.LEFT, padx=5)

# IK Control Frame
ik_control_frame = ttk.LabelFrame(left_panel, text="IK Control", padding="10")
ik_control_frame.pack(side=tk.TOP, fill=tk.X, pady=(10, 5))
# Grid layout inside IK frame
ik_control_frame.grid_columnconfigure(1, weight=1) # Allow entry widgets to expand slightly

ttk.Label(ik_control_frame, text="Target X (m):").grid(row=0, column=0, padx=5, pady=3, sticky="w")
entry_x = ttk.Entry(ik_control_frame, width=8)
entry_x.grid(row=0, column=1, padx=5, pady=3, sticky="ew")
try: # Set default based on calculated reach if possible
     entry_x.insert(0, f"{ik.LINK_1_TO_2 + ik.LINK_2_TO_3:.2f}")
except Exception: entry_x.insert(0, "0.15") # Fallback default

ttk.Label(ik_control_frame, text="Target Y (m):").grid(row=1, column=0, padx=5, pady=3, sticky="w")
entry_y = ttk.Entry(ik_control_frame, width=8)
entry_y.grid(row=1, column=1, padx=5, pady=3, sticky="ew")
entry_y.insert(0, "0.00")

ttk.Label(ik_control_frame, text="Target Z (m):").grid(row=2, column=0, padx=5, pady=3, sticky="w")
entry_z = ttk.Entry(ik_control_frame, width=8)
entry_z.grid(row=2, column=1, padx=5, pady=3, sticky="ew")
try: # Set default based on calculated reach if possible
     entry_z.insert(0, f"{ik.LINK_BASE_TO_1:.2f}")
except Exception: entry_z.insert(0, "0.10") # Fallback default


go_button = ttk.Button(ik_control_frame, text="Go to Target", command=on_go_button_click)
go_button.grid(row=4, column=0, columnspan=2, pady=10)

# Servo Display Frame
servo_display_frame = ttk.LabelFrame(left_panel, text="Servo Angles", padding="10")
servo_display_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, pady=(5, 0))
# Create sliders inside this frame AFTER the frame exists
create_sliders(servo_display_frame)


# --- Right Panel Widgets ---
# Camera Feed Frame
camera_frame = ttk.LabelFrame(right_panel, text="Camera Feed & Info", padding="10")
# Use grid for camera frame within right_panel for better weight control
camera_frame.grid(row=0, column=0, sticky="nsew", pady=(0, 5))

# Visualization Frame
vis_frame = ttk.LabelFrame(right_panel, text="3D Visualization", padding="10")
vis_frame.grid(row=1, column=0, sticky="nsew", pady=(5, 0))

# Configure right panel grid weights
right_panel.grid_rowconfigure(0, weight=1) # Camera takes initial space
right_panel.grid_rowconfigure(1, weight=1) # Visualization takes initial space
right_panel.grid_columnconfigure(0, weight=1) # Allow frames to expand horizontally

# Widgets inside Camera Frame
cam_info_subframe = ttk.Frame(camera_frame)
cam_info_subframe.pack(side=tk.TOP, fill=tk.X, pady=(0, 5)) # Info bar at the top

ttk.Label(cam_info_subframe, text="URL:").pack(side=tk.LEFT, padx=(0, 2))
camera_url_entry = ttk.Entry(cam_info_subframe, width=25)
camera_url_entry.insert(0, camera_url if camera_url else "")
camera_url_entry.pack(side=tk.LEFT, padx=(0, 5))
# Function to update URL when entry loses focus or Enter is pressed
def update_camera_url(event=None):
    global camera_url, camera_connected, camera_url_entry # Ensure access
    new_url = camera_url_entry.get()
    # Basic validation
    if new_url and new_url.startswith(('http://', 'https://')):
        if new_url != camera_url:
             camera_url = new_url
             camera_connected = True # Reset connection status on URL change
             print(f"Camera URL set to: {camera_url}")
    elif not new_url:
         if camera_url is not None:
              print("Camera URL cleared.")
         camera_url = None
         camera_connected = False
    else:
         print(f"Invalid camera URL entered: {new_url}")
         # Optionally revert entry to old URL or show error
         if camera_url: camera_url_entry.insert(0, camera_url)
         else: camera_url_entry.delete(0, tk.END)

camera_url_entry.bind("<FocusOut>", update_camera_url)
camera_url_entry.bind("<Return>", update_camera_url)

connect_camera_button = ttk.Button(cam_info_subframe, text="Reconnect", command=lambda: globals().update(camera_connected=True), width=10)
connect_camera_button.pack(side=tk.LEFT, padx=5)

distance_label = ttk.Label(cam_info_subframe, text="Distance: --- cm", font=('Segoe UI', 10), width=15, anchor='e')
distance_label.pack(side=tk.RIGHT, padx=5)

camera_label = ttk.Label(camera_frame, anchor="center", background="lightgrey") # Placeholder bg
camera_label.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=5, pady=5)


# Widgets inside Visualization Frame
# Create Matplotlib Figure and Axes
try:
    mpl_fig = Figure(figsize=(5, 4), dpi=100) # Adjust size as needed
    mpl_ax = mpl_fig.add_subplot(111, projection='3d')
    mpl_ax.set_title("Robot Arm") # Initial title

    # Embed the figure in the Tkinter window
    mpl_canvas = FigureCanvasTkAgg(mpl_fig, master=vis_frame)
    mpl_canvas_widget = mpl_canvas.get_tk_widget()
    mpl_canvas_widget.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

    # Add Navigation Toolbar
    toolbar = NavigationToolbar2Tk(mpl_canvas, vis_frame, pack_toolbar=False) # Don't pack automatically
    toolbar.update()
    toolbar.pack(side=tk.BOTTOM, fill=tk.X) # Pack toolbar at the bottom

    # Draw initial state AFTER canvas exists
    # Ensure sliders are created before getting their values
    initial_angles_vis = [s.get() for s in sliders] if sliders else [90.0]*5 + [ik.servo_limits_deg[5][0]] # Use min gripper angle
    # Schedule the initial drawing slightly after mainloop starts
    root.after(100, update_visualization, initial_angles_vis)

except Exception as e:
    print(f"Error initializing Matplotlib canvas: {e}")
    messagebox.showerror("Plot Error", f"Failed to create 3D visualization canvas.\nError: {e}", parent=root)


# --- Keybindings (Now apply to root window) ---
step = 0.01 # 1 cm step for IK target control

def move_target_key(axis, direction):
    global entry_x, entry_y, entry_z # Ensure access
    entries = {'x': entry_x, 'y': entry_y, 'z': entry_z}
    if axis not in entries or not entries[axis].winfo_exists(): return # Check if entry exists
    entry = entries[axis]
    try:
        current_val = float(entry.get())
        new_val = current_val + direction * step
        entry.delete(0, tk.END)
        entry.insert(0, f"{new_val:.3f}") # Format to 3 decimal places
    except ValueError:
        print(f"Invalid value in Entry for axis {axis}") # Log error

# Bind keys to the root window
root.bind("<Left>", lambda event: move_target_key('y', -1))  # Move Y negative
root.bind("<Right>", lambda event: move_target_key('y', 1))   # Move Y positive
root.bind("<Up>", lambda event: move_target_key('x', 1))     # Move X positive
root.bind("<Down>", lambda event: move_target_key('x', -1))   # Move X negative
root.bind("<Prior>", lambda event: move_target_key('z', 1))   # Move Z positive (PageUp)
root.bind("<Next>", lambda event: move_target_key('z', -1))    # Move Z negative (PageDown)
# Bind Enter key globally to trigger calculation if focus is not on a button etc.
root.bind("<Return>", lambda event: on_go_button_click())


# --- Start Background Threads ---
# Video update thread
# Ensure the target function exists before starting the thread
if 'update_image_in_thread' in globals():
    video_thread = threading.Thread(target=update_image_in_thread, daemon=True)
    video_thread.start()
else:
    print("Error: update_image_in_thread function not defined.")

# Start the first serial check (if function exists)
if 'get_data_from_serial' in globals():
    # Ensure root exists before scheduling the first call
    if 'root' in globals() and root.winfo_exists():
        root.after(100, get_data_from_serial)
    else:
        print("Error: Root window destroyed before scheduling serial check.")
else:
     print("Error: get_data_from_serial function not defined.")

# --- Run Main Loop ---
print("Starting Handy IK Controller GUI with Visualization...")
root.mainloop()

# --- Cleanup ---
print("Exiting application...")
if 'ser' in globals() and ser is not None and ser.is_open:
    try:
        ser.close()
        print("Serial port closed.")
    except Exception as e:
        print(f"Error closing serial port on exit: {e}")

print("Application finished.")