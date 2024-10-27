import tkinter as tk
from tkinter import ttk
import serial
import serial.tools.list_ports

BAUDRATE = 9600
SERIAL_PORT = '/dev/tty.wlan-debug'

ser = None

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
        command=lambda val: (on_scale_change(slider_number, val), value_label.config(text=f"Slider {slider_number} - Value: {int(float(val))}"))
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
    except serial.SerialException as e:
        print(f"Could not open serial port {port}: {e}")


root = tk.Tk()
root.geometry('800x500')
root.title("Slider Serial Control")

port_label = ttk.Label(root, text="Select Serial Port:")
port_label.grid(row=0, column=0, padx=10, pady=10)

available_ports = [port.device for port in serial.tools.list_ports.comports()]
port_combobox = ttk.Combobox(root, values=available_ports, state="readonly")
port_combobox.set(SERIAL_PORT)
port_combobox.grid(row=0, column=1, padx=10, pady=10)

port_combobox.bind("<<ComboboxSelected>>", lambda event: update_serial_port(port_combobox.get()))

sliders = []
for i in range(6):
    label = ttk.Label(root, text=f"Slider {i + 1}")
    label.grid(row=i + 1, column=0, padx=10, pady=5)
    slider = create_slider(root, i, i + 1)
    sliders.append(slider)

try:
    root.mainloop()
finally:
    if ser and ser.is_open:
        ser.close()
