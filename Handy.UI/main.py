import json
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import serial
import serial.tools.list_ports
import pygame
import requests
import numpy as np
from PIL import Image, ImageTk, ImageDraw
import cv2

# Initialize pygame for sound
pygame.mixer.init()
beep_sound = pygame.mixer.Sound("beep.wav")

# Constants
BAUDRATE = 9600
SERIAL_PORT = '/dev/tty.wlan-debug'
OBJECT_SIZE = 20
MAX_DISTANCE = 200
SENSOR_RADIUS = 5
CANVAS_SIZE = 400
camera_url = "http://192.168.0.4/capture"
CLASS_NAMES = ["background", "aeroplane", "bicycle", "bird", "boat", "bottle", "bus", "car", "cat",
               "chair", "cow", "diningtable", "dog", "horse", "motorbike", "person", "pottedplant",
               "sheep", "sofa", "train", "tvmonitor"]

# Global variables
ser = None
last_sound_time = 0
camera_connected = True
net = cv2.dnn.readNetFromCaffe('MobileNetSSD_deploy.prototxt', 'MobileNetSSD_deploy.caffemodel')
sliders = []  # Store all sliders in a list for easier reference

# Define functions
def play_sound():
    global last_sound_time
    current_time = time.time()
    if current_time - last_sound_time >= 1:
        beep_sound.play()
        last_sound_time = current_time

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

def update_serial_port(port):
    """Update serial port and read distance if connected."""
    global ser
    if ser and ser.is_open:
        ser.close()
    try:
        ser = serial.Serial(port, BAUDRATE)
        print(f"Connected to serial port: {port}")
        read_distance()
    except serial.SerialException as e:
        messagebox.showerror("Serial Port Error", f"Could not open serial port {port}: {e}")
        print(f"Could not open serial port {port}: {e}")

def read_distance():
    """Read and update distance from the serial port."""
    if ser and ser.is_open:
        try:
            if ser.in_waiting > 0:
                distance = ser.readline().decode('utf-8').strip()
                if distance.startswith("distance: "):
                    distance_value = int(distance.split(": ")[1])
                    distance_label.config(text=f"Distance: {distance_value} cm")
                    draw_objects(distance_value)
                    play_sound()
        except Exception as e:
            print(f"Error reading distance: {e}")
    root.after(100, read_distance)

def draw_objects(distance):
    """Draw detected objects on the canvas based on distance."""
    canvas.delete("all")
    sensor_x, sensor_y = CANVAS_SIZE / 2, CANVAS_SIZE / 2
    canvas.create_oval(sensor_x - SENSOR_RADIUS, sensor_y - SENSOR_RADIUS,
                       sensor_x + SENSOR_RADIUS, sensor_y + SENSOR_RADIUS,
                       fill="blue", tags="sensor")
    scaled_distance = min(distance, MAX_DISTANCE)
    object_y_position = max(OBJECT_SIZE // 2, min(sensor_y - (scaled_distance / MAX_DISTANCE) * (CANVAS_SIZE / 2),
                                                  CANVAS_SIZE - OBJECT_SIZE // 2))
    canvas.create_oval(sensor_x - (OBJECT_SIZE / 2), object_y_position - (OBJECT_SIZE / 2),
                       sensor_x + (OBJECT_SIZE / 2), object_y_position + (OBJECT_SIZE / 2),
                       fill="red", tags="object")
    object_size_label.config(text=f"Object Size: {OBJECT_SIZE} px")
    for i in range(1, 5):
        wave_radius = (scaled_distance / MAX_DISTANCE) * (CANVAS_SIZE / 2) * i / 4
        canvas.create_oval(sensor_x - wave_radius, sensor_y - wave_radius,
                           sensor_x + wave_radius, sensor_y + wave_radius,
                           outline='lightblue', width=2, tags='wave')


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
        detect_objects(image)
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(image)
    else:
        img = Image.new('RGB', (300, 300), color=(200, 200, 200))
        ImageDraw.Draw(img).text((75, 140), "No camera found", fill=(255, 0, 0))
    imgtk = ImageTk.PhotoImage(image=img)
    camera_label.imgtk = imgtk
    camera_label.configure(image=imgtk)
    root.after(100, update_image)


def detect_objects(image):
    """Detect objects in the image using a pre-trained DNN model."""
    blob = cv2.dnn.blobFromImage(image, 0.007843, (300, 300), 127.5)
    net.setInput(blob)
    detections = net.forward()
    height, width = image.shape[:2]
    for i in range(detections.shape[2]):
        confidence = detections[0, 0, i, 2]
        if confidence > 0.2:
            class_id = int(detections[0, 0, i, 1])
            box = detections[0, 0, i, 3:7] * np.array([width, height, width, height])
            (startX, startY, endX, endY) = box.astype("int")
            label = f"{CLASS_NAMES[class_id]}: {confidence:.2f}"
            cv2.rectangle(image, (startX, startY), (endX, endY), (0, 255, 0), 2)
            cv2.putText(image, label, (startX, startY - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)


def connect_camera():
    """Connect to the camera by updating the URL."""
    global camera_url, camera_connected
    camera_url = camera_url_entry.get()
    camera_connected = True


import json
import time


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

    for item in data.get("commands", []):  # Используем get для предотвращения ошибок
        if "command" in item:
            # Выполнение одиночной команды
            servo_number = item["command"]["servo"]
            angle = item["command"]["angle"]
            execute_command(servo_number, angle)

        elif "repeatable" in item:
            # Выполнение повторяющейся последовательности
            repeat_count = item["repeatable"]["repeats"]
            sequence = item["repeatable"]["sequence"]

            for _ in range(repeat_count):
                for command in sequence:
                    servo_number = command["servo"]
                    angle = command["angle"]
                    execute_command(servo_number, angle)
                    time.sleep(0.5)  # Пауза между командами внутри последовательности

        time.sleep(1)  # Пауза между одиночными командами или группами команд


def increase_slider(slider_number):
    """Increase the specified slider's value by 2, up to a maximum of 180."""
    current_value = sliders[slider_number].get()
    sliders[slider_number].set(min(180, current_value + 7))


def decrease_slider(slider_number):
    """Decrease the specified slider's value by 2, down to a minimum of 0."""
    current_value = sliders[slider_number].get()
    sliders[slider_number].set(max(0, current_value - 7))


# Main GUI setup
root = tk.Tk()
root.geometry('1240x680')
root.title("Handy")
style = ttk.Style()
style.theme_use("aqua")
icon = tk.PhotoImage(file='icon.png')
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

canvas = tk.Canvas(root, width=CANVAS_SIZE, height=CANVAS_SIZE, bg='green')
canvas.grid(row=8, column=0, columnspan=3, padx=10, pady=10)

ttk.Label(root, text="Camera URL:").grid(row=0, column=3, padx=10, pady=10)
camera_url_entry = ttk.Entry(root, width=30)
camera_url_entry.insert(0, camera_url)
camera_url_entry.grid(row=0, column=4, padx=10, pady=10)
ttk.Button(root, text="Connect", command=connect_camera).grid(row=0, column=5, padx=10, pady=10)

camera_label = ttk.Label(root)
camera_label.grid(row=1, column=3, rowspan=8, columnspan=3, padx=10, pady=10)

# Button to load JSON file
ttk.Button(root, text="Load Commands from JSON File", command=load_commands_from_file).grid(row=0, column=2, padx=10, pady=10)

# Create sliders and add to `sliders` list
for i in range(6):
    ttk.Label(root, text=f"Slider {i + 1}").grid(row=i + 1, column=0, padx=10, pady=5)
    slider = create_slider(root, i, i + 1)
    sliders.append(slider)

# Bind keys and start distance reading and camera updating
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


update_image()
read_distance()

# Start main loop and ensure serial port closes on exit
try:
    root.mainloop()
finally:
    if ser and ser.is_open:
        ser.close()
