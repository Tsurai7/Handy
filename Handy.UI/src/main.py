import os
import re
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import serial
import serial.tools.list_ports
import requests
import numpy as np
from PIL import Image, ImageTk, ImageDraw, ImageFont
import cv2
import json

# Constants
current_distance = 0
BAUDRATE = 9600
OBJECT_SIZE = 20
MAX_DISTANCE = 200
SENSOR_RADIUS = 5
CANVAS_SIZE = 400
camera_url = "http://192.168.239.91/capture"

# YOLOv4 model files
YOLO_CONFIG = "../cam.ai/yolov4.cfg"
YOLO_WEIGHTS = "../cam.ai/yolov4.weights"
YOLO_CLASSES = "../cam.ai/coco.names"

# Load YOLOv4 model
net = cv2.dnn.readNet(YOLO_WEIGHTS, YOLO_CONFIG)
layer_names = net.getLayerNames()
output_layers = [layer_names[i - 1] for i in net.getUnconnectedOutLayers()]
with open(YOLO_CLASSES, "r") as f:
    CLASS_NAMES = [line.strip() for line in f.readlines()]

# Global variables
ser = None
last_sound_time = 0
camera_connected = True

sliders = []  # Store all sliders in a list for easier reference

icons = {
    "Info": "warning.png",
    "Error": "error.png"
}

ICON_FOLDER = "../icons"


def get_connected_devices():
    devices = []
    result = subprocess.run(['arp', '-a'], stdout=subprocess.PIPE, text=True)

    # Regular expression to match the IP and MAC address
    pattern = r"\((.*?)\) at (.*?) on"
    matches = re.findall(pattern, result.stdout)

    for ip, mac in matches:
        devices.append((ip, mac))
    return devices


# Function to check if a device is an ESP32 by MAC address prefix
def is_esp32(mac_address):
    # ESP32 MAC address typically starts with one of the following prefixes
    esp32_prefixes = []

    # Check if the MAC address starts with one of these prefixes
    for prefix in esp32_prefixes:
        if mac_address.upper().startswith(prefix.upper()):
            return True
    return False


# Function to check if the device is an ESP32 camera by sending a request
def check_esp32_camera(ip):
    url = f"http://{ip}/capture"
    try:
        # Send a request to the camera URL
        response = requests.get(url, timeout=2)
        if response.status_code == 200:
            return True
    except requests.RequestException:
        pass
    return False


# Main function to find the ESP32 camera
def find_esp32_camera():
    devices = get_connected_devices()

    for ip, mac in devices:
        if is_esp32(mac):
            print(f"Found ESP32 device with IP: {ip} and MAC: {mac}")
            # Verify if it's an ESP32 camera by checking the URL
            if check_esp32_camera(ip):
                camera_url = f"http://{ip}/capture"
                print(f"ESP32 Camera found at: {camera_url}")
                return camera_url
    return None


# Run the function to find the camera
camera_url = find_esp32_camera()
if camera_url:
    print(f"Camera URL: {camera_url}")
else:
    print("No ESP32 camera found.")

camera_url = "http://192.168.239.134/capture"

def load_icon(icon_name):
    """Загружает иконку из указанной папки и возвращает объект PhotoImage."""
    icon_path = os.path.join(ICON_FOLDER, icon_name)
    try:
        img = Image.open(icon_path).resize((24, 24), Image.Resampling.LANCZOS)
        return ImageTk.PhotoImage(img)
    except Exception as e:
        print(f"Не удалось загрузить иконку {icon_name}: {e}")
        return None


slider_history = {}


def on_scale_change(slider_number, val):
    """Send slider change to serial if open and value difference is significant."""
    if ser and ser.is_open:
        value = int(float(val))
        message = f"{slider_number} {value}"

        history = slider_history.get(slider_number, [])

        # if history:
        #     if all(abs(value - prev_value) < 5 for prev_value in history):
        #         print(f"Skipped sending for slider {slider_number} with value {value}")
        #         return

        ser.write((message + '\n').encode())
        print(f"Sent to serial: {message.strip()}")

        history.append(value)
        if len(history) > 3:
            history.pop(0)
        slider_history[slider_number] = history

def create_slider(root, row, slider_number):
    """Create and return a labeled slider with a Tkinter Scale widget."""
    value_label = ttk.Label(root, text=f"Slider {slider_number} - Value: 90")
    value_label.grid(row=row + 1, column=0, padx=5, pady=5)

    if slider_number == 5:
        slider = ttk.Scale(
            root,
            from_=0,
            to=90,
            orient="horizontal",
            length=400,
            command=lambda val: (on_scale_change(slider_number, val),
                                 value_label.config(text=f"Slider {slider_number} - Value: {int(float(val))}"))
        )
        slider.set(45)
    else:
        slider = ttk.Scale(
            root,
            from_=0,
            to=180,
            orient="horizontal",
            length=400,
            command=lambda val: (on_scale_change(slider_number, val),
                                 value_label.config(text=f"Slider {slider_number} - Value: {int(float(val))}"))
        )
        slider.set(90)

    slider.grid(row=row + 1, column=1, padx=10, pady=5)
    return slider


def create_sliders():
    """Create sliders and store them in a list for later reference."""
    for i in range(0, 6):  # assuming you have 6 sliders
        slider = create_slider(root, i, i)
        sliders.append(slider)


def update_serial_port(port):
    """Update serial port and read distance if connected."""
    global ser
    if ser and ser.is_open:
        ser.close()
    try:
        ser = serial.Serial(port, BAUDRATE)
        print(f"Connected to serial port: {port}")
        get_data_from_serial()
    except serial.SerialException as e:
        messagebox.showerror("Serial Port Error", f"Could not open serial port {port}: {e}")
        print(f"Could not open serial port {port}: {e}")


def get_data_from_serial():
    global current_distance
    if ser and ser.is_open:
        try:
            if ser.in_waiting > 0:
                message = ser.readline().decode('utf-8').strip()
                if message.startswith("Distance: "):
                    handle_distance_message(message)
                elif message.startswith("Message: "):
                    handle_info_message(message)
                elif message.startswith("Error: "):
                    handle_error_message(message)
        except Exception as e:
            print(f"Error reading data: {e}")
    root.after(100, get_data_from_serial)


def show_toast(message, message_type="Info", duration=3000):
    toast = tk.Toplevel()
    toast.overrideredirect(True)
    toast.attributes("-topmost", True)

    screen_width = toast.winfo_screenwidth()
    screen_height = toast.winfo_screenheight()
    window_width = 300
    window_height = 60
    x = screen_width - window_width - 20
    y = screen_height - window_height - 60
    toast.geometry(f"{window_width}x{window_height}+{x}+{y}")

    # Create a frame to hold the icon and message
    frame = tk.Frame(toast, bg="black")
    frame.pack(fill=tk.BOTH, expand=True)

    # Load the icon based on message type
    icon_path = icons.get(message_type, "info.png")
    icon = load_icon(icon_path)

    # Display the icon (if loaded) and the message
    if icon:
        icon_label = tk.Label(frame, image=icon, bg="black")
        icon_label.image = icon  # Keep a reference to avoid garbage collection
        icon_label.pack(side=tk.LEFT, padx=10, pady=10)

    label = tk.Label(frame, text=message, bg="black", fg="white", font=("Arial", 12), anchor="w")
    label.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    toast.after(duration, toast.destroy)


def handle_distance_message(message):
    """Обработка сообщения типа Distance"""
    global current_distance
    try:
        distance_value = int(message.split(": ")[1])
        current_distance = distance_value
        distance_label.config(text=f"Distance: {distance_value} cm")
        print(f"Distance: {distance_value} cm")
    except ValueError:
        print("Invalid distance value")


def handle_info_message(message):
    """Handle 'Info' type messages."""
    info = message.split(": ", 1)[1] if ": " in message else "No details"
    print(f"Info Message: {info}")
    show_toast(f"Info: {info}", "Info")


def handle_error_message(message):
    """Handle 'Error' type messages."""
    error_info = message.split(": ", 1)[1] if ": " in message else "No details"
    print(f"Error Message: {error_info}")
    show_toast(f"Error: {error_info}", "Error")


def detect_objects(image, distance):
    """Detect objects in the image using YOLOv4 and display color and distance information."""
    blob = cv2.dnn.blobFromImage(image, 0.00392, (416, 416), (0, 0, 0), True, crop=False)
    net.setInput(blob)
    detections = net.forward(output_layers)

    height, width, channels = image.shape
    boxes, confidences, class_ids = [], [], []

    for out in detections:
        for detection in out:
            scores = detection[5:]
            class_id = np.argmax(scores)
            confidence = scores[class_id]
            if confidence > 0.5:  # Confidence threshold
                center_x = int(detection[0] * width)
                center_y = int(detection[1] * height)
                w = int(detection[2] * width)
                h = int(detection[3] * height)

                x = int(center_x - w / 2)
                y = int(center_y - h / 2)

                boxes.append([x, y, w, h])
                confidences.append(float(confidence))
                class_ids.append(class_id)

    # Apply Non-Maximum Suppression (NMS)
    indices = cv2.dnn.NMSBoxes(boxes, confidences, 0.5, 0.4)

    # Indices is a tuple, so we need to handle it accordingly
    if len(indices) > 0:
        indices = indices.flatten()  # Flatten if it's not empty

        for i in indices:
            x, y, w, h = boxes[i]
            label = f"{CLASS_NAMES[class_ids[i]]}: {confidences[i]:.2f}, Dist: {distance} cm"

            # Draw bounding box and label
            color = (0, 255, 0)
            cv2.rectangle(image, (x, y), (x + w, y + h), color, 2)
            cv2.putText(image, label, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

    return image


def get_image_from_camera():
    """Capture image from the camera URL."""
    global camera_connected
    if not camera_connected:
        return None
    try:
        response = requests.get(camera_url, timeout=5)
        if response.status_code == 200:
            image_array = np.array(bytearray(response.content), dtype=np.uint8)
            return cv2.imdecode(image_array, cv2.IMREAD_COLOR)
    except Exception as e:
        print(f"An error occurred: {e}")
        camera_connected = False
    return None


def update_image():
    """Update the camera image on the UI."""
    image = get_image_from_camera()

    if image is not None:
        # Process the camera image (e.g., detect objects)
        image = detect_objects(image, current_distance)
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)  # Convert from OpenCV BGR to RGB
        img = Image.fromarray(image)
    else:
        # Create a "No Camera Found" placeholder
        width, height = 640, 480
        img = Image.new('RGB', (width, height), color=(240, 240, 240))  # Light gray background
        draw = ImageDraw.Draw(img)

        # Use the default Pillow font
        font_large = ImageFont.load_default()

        # Text to display
        text = "No Camera Found"
        subtext = "Please check your camera connection."

        # Calculate text dimensions using textbbox
        text_bbox = draw.textbbox((0, 0), text, font=font_large)
        subtext_bbox = draw.textbbox((0, 0), subtext, font=font_large)
        text_width, text_height = text_bbox[2] - text_bbox[0], text_bbox[3] - text_bbox[1]
        subtext_width, subtext_height = subtext_bbox[2] - subtext_bbox[0], subtext_bbox[3] - subtext_bbox[1]

        # Center and draw the main text
        draw.text(
            ((width - text_width) // 2, height // 2 - text_height),
            text,
            fill="black",
            font=font_large
        )

        # Center and draw the subtext below the main text
        draw.text(
            ((width - subtext_width) // 2, height // 2 + text_height),
            subtext,
            fill="gray",
            font=font_large
        )

    # Display the image in the Tkinter label
    imgtk = ImageTk.PhotoImage(image=img)
    camera_label.imgtk = imgtk
    camera_label.configure(image=imgtk)
    root.after(10, update_image)  # Schedule the next update


def connect_camera():
    """Connect to the camera by updating the URL."""
    global camera_url, camera_connected
    camera_url = camera_url_entry.get()
    camera_connected = True


def execute_command(servo_number, angle):
    """Sets a specified servo to a given angle and sends the command to the serial port."""
    sliders[servo_number].set(angle)
    print(f"Servo {servo_number} set to angle {angle}")
    on_scale_change(servo_number, angle)


def load_commands_from_file():
    """Open a file dialog to load commands from a JSON file and execute them."""
    filename = filedialog.askopenfilename(
        title="Select a JSON File",
        filetypes=[("JSON Files", "*.json")]
    )
    if filename:
        try:
            load_commands_from_json(filename)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load commands from {filename}:\n{e}")


def load_commands_from_json(filename):
    """Load and execute servo commands and repeatable sequences from a JSON file."""
    with open(filename, 'r') as file:
        try:
            data = json.load(file)
        except json.JSONDecodeError:
            messagebox.showerror("JSON Error", f"Error decoding JSON in file: {filename}")
            return

    # Iterate over the commands in the JSON
    for item in data.get("commands", []):
        if "servo" in item and "angle" in item:
            # Single command for a servo
            servo_number = item["servo"]
            angle = item["angle"]
            execute_command(servo_number, angle)

        elif "repeatable" in item:
            repeat_count = item["repeatable"]["repeats"]
            for _ in range(repeat_count):
                for cmd in item["repeatable"]["sequence"]:
                    # Executing each command in the repeatable sequence
                    execute_command(cmd["servo"], cmd["angle"])


def get_data_from_serial():
    root.after(100, get_data_from_serial)


def handle_distance_message(message):
    """Обработка сообщения типа Distance"""
    global current_distance
    try:
        distance_value = int(message.split(": ")[1])
        current_distance = distance_value
        distance_label.config(text=f"Distance: {distance_value} cm")
        print(f"Distance: {distance_value} cm")
    except ValueError:
        print("Invalid distance value")


def handle_info_message(message):
    """Handle 'Info' type messages."""
    info = message.split(": ", 1)[1] if ": " in message else "No details"
    print(f"Info Message: {info}")
    show_toast(f"Info: {info}", "Info")


def handle_error_message(message):
    """Handle 'Error' type messages."""
    error_info = message.split(": ", 1)[1] if ": " in message else "No details"
    print(f"Error Message: {error_info}")
    show_toast(f"Error: {error_info}", "Error")


def increase_slider(slider_number):
    """Increase the specified slider's value by 2, up to a maximum of 180."""
    current_value = sliders[slider_number].get()
    sliders[slider_number].set(min(180, current_value + 7))


def decrease_slider(slider_number):
    """Decrease the specified slider's value by 2, down to a minimum of 0."""
    current_value = sliders[slider_number].get()
    sliders[slider_number].set(max(0, current_value - 7))


# Create main window
root = tk.Tk()
root.geometry("1000x1180")
root.title("Handy")
icon = tk.PhotoImage(file='../icons/icon.png')
root.iconphoto(True, icon)

# UI elements for serial port, distance, and sliders
ttk.Label(root, text="Select Serial Port:").grid(row=0, column=0, padx=5, pady=5)
available_ports = [port.device for port in serial.tools.list_ports.comports()]
port_combobox = ttk.Combobox(root, values=available_ports, state="readonly")
port_combobox.set("Select a Port")
port_combobox.grid(row=0, column=1, padx=5, pady=5)
port_combobox.bind("<<ComboboxSelected>>", lambda event: update_serial_port(port_combobox.get()))

distance_label = ttk.Label(root, text=f"Distance: {current_distance}", justify="left", anchor="w")
distance_label.grid(row=2, column=2, columnspan=2, padx=5, pady=10)

ttk.Label(root, text="Camera URL:").grid(row=0, column=2, padx=5, pady=10)
camera_url_entry = ttk.Entry(root, width=30)
camera_url_entry.insert(0, camera_url)
camera_url_entry.grid(row=0, column=3, padx=10, pady=10)

camera_label = ttk.Label(root)
camera_label.grid(row=8, column=0, rowspan=8, columnspan=3, padx=5, pady=10)

load_file_button = ttk.Button(root, text="Load Commands from File", command=load_commands_from_file)
load_file_button.grid(row=1, column=3, padx=5, pady=10)


# Add Keybinding Description
keybind_description = (
    "Keybindings for Controls:\n\n"
    " - 'A' / 'D': Decrease/Increase Slider 0\n\n"
    " - 'Ctrl+W' / 'Ctrl+S': Increase/Decrease Slider 1\n\n"
    " - 'Shift+W' / 'Shift+S': Increase/Decrease Slider 2\n\n"
    " - 'W' / 'S': Increase/Decrease Slider 3\n\n"
    " - 'E' / 'Q': Increase/Decrease Slider 4\n\n"
    " - 'Space' / 'Z': Increase/Decrease Slider 5"
)

keybind_label = ttk.Label(root, text=keybind_description, justify="left", anchor="w")
keybind_label.grid(row=8, column=3, rowspan=8, padx=20, pady=10, sticky="nw")


root.bind("d", lambda event: increase_slider(0))
root.bind("a", lambda event: decrease_slider(0))

root.bind("<Control-w>", lambda event: increase_slider(1))
root.bind("<Control-s>", lambda event: decrease_slider(1))

root.bind("<Shift-W>", lambda event: increase_slider(2))
root.bind("<Shift-S>", lambda event: decrease_slider(2))

root.bind("w", lambda event: increase_slider(3))
root.bind("s", lambda event: decrease_slider(3))

root.bind("e", lambda event: increase_slider(4))
root.bind("q", lambda event: decrease_slider(4))

root.bind("<space>", lambda event: increase_slider(5))
root.bind("z", lambda event: decrease_slider(5))

# Create sliders
create_sliders()

update_image()

# Run main loop
root.mainloop()