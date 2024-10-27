import tkinter as tk
from tkinter import ttk
import serial
import serial.tools.list_ports
import pygame
import time
import requests
import numpy as np
from PIL import Image, ImageTk
import cv2

pygame.mixer.init()
beep_sound = pygame.mixer.Sound("beep.wav")

BAUDRATE = 9600
SERIAL_PORT = '/dev/tty.wlan-debug'

ser = None
OBJECT_SIZE = 20
MAX_DISTANCE = 200
SENSOR_RADIUS = 5
CANVAS_SIZE = 400

ESP32_IP = "http://192.168.0.4/capture"

last_sound_time = 0

CLASS_NAMES = ["background", "aeroplane", "bicycle", "bird", "boat", "bottle", "bus",
               "car", "cat", "chair", "cow", "diningtable", "dog", "horse", "motorbike",
               "person", "pottedplant", "sheep", "sofa", "train", "tvmonitor"]

net = cv2.dnn.readNetFromCaffe('MobileNetSSD_deploy.prototxt', 'MobileNetSSD_deploy.caffemodel')


def play_sound():
    global last_sound_time
    current_time = time.time()
    if current_time - last_sound_time >= 1:
        beep_sound.play()
        last_sound_time = current_time


def on_scale_change(slider_number, val):
    if ser and ser.is_open:
        value = int(float(val))
        message = f"{slider_number} {value}\n"
        ser.write(message.encode())
        print(f"Sent to serial: {message.strip()}")


def create_slider(root, row, slider_number):
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
    global ser
    if ser and ser.is_open:
        ser.close()
    try:
        ser = serial.Serial(port, BAUDRATE)
        print(f"Connected to serial port: {port}")
        read_distance()  # Start reading distance when connected
    except serial.SerialException as e:
        print(f"Could not open serial port {port}: {e}")


def read_distance():
    if ser and ser.is_open:
        try:
            if ser.in_waiting > 0:
                distance = ser.readline().decode('utf-8').strip()
                try:
                    distance_value = int(distance)
                    distance_label.config(
                        text=f"Distance: {distance_value} cm")
                    draw_objects(distance_value)
                    play_sound()
                except ValueError:
                    print(f"Invalid distance received: {distance}")
        except Exception as e:
            print(f"Error reading distance: {e}")
    root.after(100, read_distance)


def draw_objects(distance):
    canvas.delete("all")

    sensor_x = CANVAS_SIZE / 2
    sensor_y = CANVAS_SIZE / 2
    canvas.create_oval(
        sensor_x - SENSOR_RADIUS,  # x1
        sensor_y - SENSOR_RADIUS,  # y1
        sensor_x + SENSOR_RADIUS,  # x2
        sensor_y + SENSOR_RADIUS,  # y2
        fill="blue",
        tags="sensor"
    )

    scaled_distance = min(distance, MAX_DISTANCE)

    object_y_position = sensor_y - (scaled_distance / MAX_DISTANCE) * (CANVAS_SIZE / 2)  # Scale to canvas height

    object_y_position = max(OBJECT_SIZE // 2, min(object_y_position, CANVAS_SIZE - OBJECT_SIZE // 2))

    canvas.create_oval(
        sensor_x - (OBJECT_SIZE / 2),  # x1
        object_y_position - (OBJECT_SIZE / 2),  # y1
        sensor_x + (OBJECT_SIZE / 2),  # x2
        object_y_position + (OBJECT_SIZE / 2),  # y2
        fill="red",
        tags="object"
    )

    object_size_text = f"Object Size: {OBJECT_SIZE} px"
    object_size_label.config(text=object_size_text)

    for i in range(1, 5):
        wave_radius = (scaled_distance / MAX_DISTANCE) * (CANVAS_SIZE / 2) * i / 4
        canvas.create_oval(
            sensor_x - wave_radius, sensor_y - wave_radius,
            sensor_x + wave_radius, sensor_y + wave_radius,
            outline='lightblue', width=2, tags='wave'
        )


def get_image_from_camera():
    try:
        response = requests.get(ESP32_IP)
        if response.status_code == 200:
            image_array = np.array(bytearray(response.content), dtype=np.uint8)
            image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
            return image
        else:
            print(f"Failed to get image. Status code: {response.status_code}")
    except Exception as e:
        print(f"An error occurred: {e}")
    return None


def update_image():
    image = get_image_from_camera()
    if image is not None:
        detect_objects(image)

        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

        img = Image.fromarray(image)
        imgtk = ImageTk.PhotoImage(image=img)

        camera_label.imgtk = imgtk
        camera_label.configure(image=imgtk)

    root.after(100, update_image)


def detect_objects(image):
    blob = cv2.dnn.blobFromImage(image, 0.007843, (300, 300), 127.5)
    net.setInput(blob)
    detections = net.forward()

    height, width = image.shape[:2]

    for i in range(detections.shape[2]):
        confidence = detections[0, 0, i, 2]
        if confidence > 0.2:  # Filter out weak detections
            class_id = int(detections[0, 0, i, 1])
            box = detections[0, 0, i, 3:7] * np.array([width, height, width, height])
            (startX, startY, endX, endY) = box.astype("int")

            # Draw the bounding box and label on the image
            label = f"{CLASS_NAMES[class_id]}: {confidence:.2f}"
            cv2.rectangle(image, (startX, startY), (endX, endY), (0, 255, 0), 2)
            cv2.putText(image, label, (startX, startY - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

root = tk.Tk()
root.geometry('1200x600')
root.title("Slider Serial Control with Distance Visualization and Camera Feed")

port_label = ttk.Label(root, text="Select Serial Port:")
port_label.grid(row=0, column=0, padx=10, pady=10)

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

canvas.create_oval(0, 0, CANVAS_SIZE, CANVAS_SIZE, fill='green', outline='black')

for i in range(6):
    label = ttk.Label(root, text=f"Slider {i + 1}")
    label.grid(row=i + 1, column=0, padx=10, pady=5)
    create_slider(root, i, i + 1)

camera_label = ttk.Label(root)
camera_label.grid(row=0, column=3, rowspan=9, padx=10, pady=10)

update_image()

read_distance()

try:
    root.mainloop()
finally:
    if ser and ser.is_open:
        ser.close()
