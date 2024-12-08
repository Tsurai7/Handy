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


from globals import sliders, YOLO_WEIGHTS, YOLO_CONFIG, YOLO_CLASSES
import helpers
import ui

# Constants
current_distance = 0
BAUDRATE = 9600


# Load YOLOv4 model
net = cv2.dnn.readNet(YOLO_WEIGHTS, YOLO_CONFIG)
layer_names = net.getLayerNames()
output_layers = [layer_names[i - 1] for i in net.getUnconnectedOutLayers()]
with open(YOLO_CLASSES, "r") as f:
    CLASS_NAMES = [line.strip() for line in f.readlines()]

# Global variables
ser = None
camera_connected = True

camera_url = helpers.find_esp32_camera()

slider_history = {}


def on_scale_change(slider_number, val):
    """Send slider change to serial if open and value difference is significant."""
    if ser and ser.is_open:
        value = int(float(val))
        message = f"{slider_number} {value}"

        history = slider_history.get(slider_number, [])

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


def update_serial_port(portName):
    """Update serial port and read distance if connected."""
    global ser
    if ser and ser.is_open:
        ser.close()
    try:
        ser = serial.Serial(portName, BAUDRATE)
        print(f"Connected to serial port: {portName}")
        get_data_from_serial()
    except serial.SerialException as e:
        messagebox.showerror("Serial Port Error", f"Could not open serial port {portName}: {e}")
        print(f"Could not open serial port {portName}: {e}")


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


def handle_distance_message(message):
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
    ui.show_toast(f"Info: {info}", "Info")


def handle_error_message(message):
    """Handle 'Error' type messages."""
    error_info = message.split(": ", 1)[1] if ": " in message else "No details"
    print(f"Error Message: {error_info}")
    ui.show_toast(f"Error: {error_info}", "Error")


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


def update_image_in_thread():
    """Обрабатывает изображения в отдельном потоке и отправляет их в UI-поток."""
    while True:
        image = get_image_from_camera()
        if image is not None:
            # Обработка изображения
            image = detect_objects(image, current_distance)
            image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)  # Конвертация из OpenCV BGR в RGB
            img = Image.fromarray(image)
        else:
            # Создаем заглушку "No Camera Found"
            width, height = 640, 480
            img = Image.new('RGB', (width, height), color=(240, 240, 240))  # Серый фон
            draw = ImageDraw.Draw(img)
            font_large = ImageFont.load_default()
            text = "No Camera Found"
            subtext = "Please check your camera connection."

            # Рассчитываем координаты для текста
            text_bbox = draw.textbbox((0, 0), text, font=font_large)
            subtext_bbox = draw.textbbox((0, 0), subtext, font=font_large)
            text_width, text_height = text_bbox[2] - text_bbox[0], text_bbox[3] - text_bbox[1]
            subtext_width, subtext_height = subtext_bbox[2] - subtext_bbox[0], subtext_bbox[3] - subtext_bbox[1]

            draw.text(
                ((width - text_width) // 2, height // 2 - text_height),
                text,
                fill="black",
                font=font_large
            )
            draw.text(
                ((width - subtext_width) // 2, height // 2 + text_height),
                subtext,
                fill="gray",
                font=font_large
            )

        # Обновляем UI через основной поток
        tk_image = ImageTk.PhotoImage(image=img)
        root.after(0, update_ui_image, tk_image)  # Передача изображения в UI
        time.sleep(0.1)  # Задержка, чтобы уменьшить нагрузку на CPU


def update_ui_image(tk_image):
    """Обновляет изображение в виджете Tkinter."""
    camera_label.imgtk = tk_image
    camera_label.configure(image=tk_image)


def execute_command(servo_number, angle):
    """Sets a specified servo to a given angle and sends the command to the serial port."""
    sliders[servo_number].set(angle)
    print(f"Servo {servo_number} set to angle {angle}")
    on_scale_change(servo_number, angle)


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
                    time.sleep(1)


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


# Create main window
root = tk.Tk()
root.geometry("1080x1080")
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
distance_label.grid(row=2, column=2, padx=5, pady=10)

ttk.Label(root, text="Camera URL:").grid(row=0, column=2, padx=5, pady=10)
camera_url_entry = ttk.Entry(root, width=30)
camera_url_entry.insert(0, camera_url)
camera_url_entry.grid(row=0, column=3, padx=10, pady=10)

camera_label = ttk.Label(root)
camera_label.grid(row=8, column=0, rowspan=8, columnspan=3, padx=5, pady=10)

connect_camera_button = ttk.Button(root, text="Try to reconnect", command=get_image_from_camera)
connect_camera_button.grid(row=1, column=2, padx=5, pady=10)

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

root.bind("<d>", lambda event: helpers.increase_slider(0))
root.bind("<a>", lambda event: helpers.decrease_slider(0))

root.bind("<Control-w>", lambda event: helpers.increase_slider(1))
root.bind("<Control-s>", lambda event: helpers.decrease_slider(1))

root.bind("<Shift-W>", lambda event: helpers.increase_slider(2))
root.bind("<Shift-S>", lambda event: helpers.decrease_slider(2))

root.bind("<w>", lambda event: helpers.increase_slider(3))
root.bind("<s>", lambda event: helpers.decrease_slider(3))

root.bind("<e>", lambda event: helpers.increase_slider(4))
root.bind("<q>", lambda event: helpers.decrease_slider(4))

root.bind("<space>", lambda event: helpers.increase_slider(5))
root.bind("z", lambda event: helpers.decrease_slider(5))

# Create sliders
create_sliders()

video_thread = threading.Thread(target=update_image_in_thread, daemon=True)
video_thread.start()

# Run main loop
root.mainloop()