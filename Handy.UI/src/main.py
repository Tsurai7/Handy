import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import serial
import serial.tools.list_ports
import requests
import numpy as np
from PIL import Image, ImageTk, ImageDraw
import cv2
import json

# Constants
current_distance = 0
BAUDRATE = 9600
SERIAL_PORT = '/dev/tty.wlan-debug'
OBJECT_SIZE = 20
MAX_DISTANCE = 200
SENSOR_RADIUS = 5
CANVAS_SIZE = 400
camera_url = "http://192.168.0.4/capture"

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


def load_icon(icon_name):
    """Загружает иконку из указанной папки и возвращает объект PhotoImage."""
    icon_path = os.path.join(ICON_FOLDER, icon_name)
    try:
        img = Image.open(icon_path).resize((24, 24), Image.Resampling.LANCZOS)
        return ImageTk.PhotoImage(img)
    except Exception as e:
        print(f"Не удалось загрузить иконку {icon_name}: {e}")
        return None


def on_scale_change(slider_number, val):
    """Send slider change to serial if open."""
    if ser and ser.is_open:
        value = int(float(val))
        message = f"{slider_number-1} {value}"
        ser.write((message + '\n').encode())
        print(f"Sent to serial: {message.strip()}")


def create_slider(root, row, slider_number):
    """Create and return a labeled slider with a Tkinter Scale widget."""
    value_label = ttk.Label(root, text=f"Slider {slider_number} - Value: 90")
    value_label.grid(row=row + 1, column=2, padx=10)

    if slider_number == 6:
        slider = ttk.Scale(
            root,
            from_=0,
            to=90,
            orient="horizontal",
            length=400,
            command=lambda val: (on_scale_change(slider_number, val),
                                 value_label.config(text=f"Slider {slider_number} - Value: {int(float(val))}"))
        )
        slider.set(90)
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
    for i in range(1, 7):  # assuming you have 6 sliders
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
        image = detect_objects(image, current_distance)  # Use the stored global distance
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(image)
    else:
        img = Image.new('RGB', (640, 480), color=(200, 200, 200))
        ImageDraw.Draw(img).text((75, 140), "No camera found", fill=(255, 0, 0))

    imgtk = ImageTk.PhotoImage(image=img)
    camera_label.imgtk = imgtk
    camera_label.configure(image=imgtk)
    root.after(100, update_image)  # Update image every 100ms


def connect_camera():
    """Connect to the camera by updating the URL."""
    global camera_url, camera_connected
    camera_url = camera_url_entry.get()
    camera_connected = True


def execute_command(servo_number, angle):
    """Sets a specified servo to a given angle and sends the command to the serial port."""
    sliders[servo_number - 1].set(angle)
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

    for item in data.get("commands", []):
        if "command" in item:
            servo_number = item["command"]["servo"]
            angle = item["command"]["angle"]
            execute_command(servo_number, angle)

        elif "repeatable" in item:
            repeat_count = item["repeatable"]["repeats"]
            for _ in range(repeat_count):
                for cmd in item["repeatable"]["commands"]:
                    execute_command(cmd["servo"], cmd["angle"])


# Create main window
root = tk.Tk()
root.geometry("1920x1080")
root.title("Handy")
icon = tk.PhotoImage(file='../icon.png')
root.iconphoto(True, icon)

# UI elements for serial port, distance, and sliders
ttk.Label(root, text="Select Serial Port:").grid(row=0, column=0, padx=10, pady=10)
available_ports = [port.device for port in serial.tools.list_ports.comports()]
port_combobox = ttk.Combobox(root, values=available_ports, state="readonly")
port_combobox.set(SERIAL_PORT)
port_combobox.grid(row=0, column=1, padx=10, pady=10)
port_combobox.bind("<<ComboboxSelected>>", lambda event: update_serial_port(port_combobox.get()))

distance_label = ttk.Label(root, text="Distance: ")
distance_label.grid(row=7, column=0, columnspan=3, padx=10, pady=10)

object_size_label = ttk.Label(root, text="Object Size: 20 px")
object_size_label.grid(row=6, column=0, columnspan=3, padx=10, pady=10)

canvas = tk.Canvas(root, width=CANVAS_SIZE, height=CANVAS_SIZE, bg="green")
canvas.grid(row=8, column=0, columnspan=3, padx=10, pady=10)

ttk.Label(root, text="Camera URL:").grid(row=0, column=3, padx=10, pady=10)
camera_url_entry = ttk.Entry(root, width=30)
camera_url_entry.insert(0, camera_url)
camera_url_entry.grid(row=0, column=4, padx=10, pady=10)

camera_label = ttk.Label(root)
camera_label.grid(row=1, column=3, rowspan=8, columnspan=3, padx=10, pady=10)

def increase_slider(slider_number):
    """Increase the specified slider's value by 2, up to a maximum of 180."""
    current_value = sliders[slider_number].get()
    sliders[slider_number].set(min(180, current_value + 7))


def decrease_slider(slider_number):
    """Decrease the specified slider's value by 2, down to a minimum of 0."""
    current_value = sliders[slider_number].get()
    sliders[slider_number].set(max(0, current_value - 7))


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

# Initialize serial connection and image update
update_serial_port(SERIAL_PORT)
update_image()

# Run main loop
root.mainloop()