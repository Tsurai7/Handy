#include <Servo.h>

Servo servo_0;
Servo servo_1;
Servo servo_2;
Servo servo_3;
Servo servo_4;
Servo servo_5;

#define trigPin 12
#define echoPin 13
#define step_delay 15
#define step_size 10
#define max_angle_per_command 40

int duration;
int distance;

int servoPins[] = {3, 5, 6, 9, 10, 11};
bool servoConnected[] = {true, true, true, true, true, true};
const int disconnectThreshold = 1;

bool ultrasonicConnected = true;

int currentPos[6] = {90, 90, 90, 90, 90, 90};
int targetPos[6] = {90, 90, 90, 90, 90, 90};

void setup() {
  pinMode(trigPin, OUTPUT);
  pinMode(echoPin, INPUT);

  Serial.begin(9600);
  servo_0.attach(servoPins[0], 0, 180);
  servo_1.attach(servoPins[1], 0, 180);
  servo_2.attach(servoPins[2], 0, 180);
  servo_3.attach(servoPins[3], 0, 180);
  servo_4.attach(servoPins[4], 0, 180);
  servo_5.attach(servoPins[5],0, 90);
}

void moveServo(int servoIndex, int servoValue) {
    if (servoConnected[servoIndex]) {

    bool angleValid = false;
    if (servoIndex < 5 && servoValue >= 0 && servoValue <= 180) {
    angleValid = true;
    } else if (servoIndex == 5 && servoValue >= 0 && servoValue <= 90) {
    angleValid = true;
    }

    if (angleValid) {
    switch (servoIndex) {
      case 0:
        servo_0.attach(servoPins[0]);
        servo_0.write(servoValue);
        break;
      case 1:
        servo_1.attach(servoPins[1]);
        servo_1.write(servoValue);
        break;
      case 2:
        servo_2.attach(servoPins[2]);
        servo_2.write(servoValue);
        break;
      case 3:
        servo_3.attach(servoPins[3]);
        servo_3.write(servoValue);
        break;
      case 4:
        servo_4.attach(servoPins[4]);
        servo_4.write(servoValue);
        break;
      case 5:
        servo_5.attach(servoPins[5]);
        servo_5.write(servoValue);
        break;
      default:
        break;
    }
    } else {
    Serial.print("Error: Servo ");
    Serial.print(servoIndex);
    Serial.print(" angle out of range. ");
    Serial.println(servoIndex == 5 ? "Allowed: 0-90" : "Allowed: 0-180");
    }

    } else {
    Serial.print("Error: Servo ");
    Serial.print(servoIndex);
    Serial.println(" is not connected.");
    }
}

bool isServoConnected(int pin) {
  pinMode(pin, INPUT);
  int signalValue = digitalRead(pin);
  return (signalValue == LOW);
}

void loop() {
if (Serial.available() > 0) {
    String input = Serial.readStringUntil('\n');
    int separatorIndex = input.indexOf(' ');
    if (separatorIndex != -1) {
      int servoIndex = input.substring(0, separatorIndex).toInt();
      int servoValue = input.substring(separatorIndex + 1).toInt();

      if (servoIndex >= 0 && servoIndex < 6) {
        moveServo(servoIndex, servoValue);
      } else {
        Serial.println("Error: Invalid servo index.");
      }
    }
  }

  static uint32_t tmr;
  if (millis() - tmr >= 1000) {
    ultra_sonic();
    tmr = millis();
  }
  static uint32_t tmr2;
  if (millis() - tmr2 >= 10000) {
    checkServoStatus();
    tmr2 = millis();
  }
}

void ultra_sonic() {
  digitalWrite(trigPin, LOW);
  delayMicroseconds(2);
  digitalWrite(trigPin, HIGH);
  delayMicroseconds(10);
  digitalWrite(trigPin, LOW);

  duration = pulseIn(echoPin, HIGH);
  distance = duration * 0.034 / 2;

  if (duration > 0 && ultrasonicConnected) {
    Serial.print("Distance: ");
    Serial.println(distance);
  } else {
    checkUltrasonicSensor();
  }
}

void checkServoStatus() {
  for (int i = 0; i < 6; i++) {
    int signalValue = isServoConnected(servoPins[i]);
    if (signalValue < disconnectThreshold && servoConnected[i]) {
      servoConnected[i] = false;
      Serial.print("Error: Servo ");
      Serial.print(i);
      Serial.println(" disconnected.");
    }
    else if (signalValue >= disconnectThreshold && !servoConnected[i]) {
      servoConnected[i] = true;
      Serial.print("Message: Servo ");
      Serial.print(i);
      Serial.println(" connected.");
    }
  }
}

void checkUltrasonicSensor() {
  digitalWrite(trigPin, LOW);
  delayMicroseconds(2);
  digitalWrite(trigPin, HIGH);
  delayMicroseconds(10);
  digitalWrite(trigPin, LOW);

  duration = pulseIn(echoPin, HIGH);

  if (duration == 0 && ultrasonicConnected) {
    ultrasonicConnected = false;
    Serial.println("Error: Ultrasonic sensor disconnected.");
  } else if (duration > 0 && !ultrasonicConnected) {
    ultrasonicConnected = true;
    Serial.println("Message: Ultrasonic sensor connected.");
  }
}
