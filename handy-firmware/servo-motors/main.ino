#include <Servo.h>
#include "INA3221.h"

Servo servo_0;
Servo servo_1;
Servo servo_2;
Servo servo_3;
Servo servo_4;
Servo servo_5;
INA3221 INA(0x40);

#define trigPin 13
#define echoPin 12

int duration;
int distance;

int servoPins[] = {6, 5, 11, 9, 3, 10};
bool servoConnected[] = {true, true, true, true, true, true};

bool ultrasonicConnected = true;

int currentPos[6] = {90, 90, 90, 90, 90, 90};
int targetPos[6] = {90, 90, 90, 90, 90, 90};

void setup() {
  pinMode(trigPin, OUTPUT);
  pinMode(echoPin, INPUT);

  Serial.begin(9600);
  servo_0.attach(servoPins[0]);
  servo_1.attach(servoPins[1]);
  servo_2.attach(servoPins[2]);
  servo_3.attach(servoPins[3]);
  servo_4.attach(servoPins[4]);
  servo_5.attach(servoPins[5]);

  INA.setShuntR(0, 0.100);
  INA.setShuntR(1, 0.102);
  INA.setShuntR(2, 0.099);
}

void moveServo(int servoIndex, int servoValue) {
  if (servoConnected[servoIndex]) {
    bool angleValid = false;
    if (servoIndex < 5 && servoValue >= 0 && servoValue <= 180) {
      angleValid = true;
    } else if (servoIndex == 5 && servoValue >= 17 && servoValue <= 90) {
      angleValid = true;
    }

    if (angleValid) {
      switch (servoIndex) {
        case 0:
          servo_0.write(servoValue);
          break;
        case 1:
          servo_1.write(servoValue);
          break;
        case 2:
          servo_2.write(servoValue);
          break;
        case 3:
          servo_3.write(servoValue);
          break;
        case 4:
          servo_4.write(servoValue);
          break;
        case 5:
          servo_5.write(servoValue);
          break;
        default:
          break;
      }
    } else {
      Serial.print("Error: Servo ");
      Serial.print(servoIndex);
      Serial.print(" angle out of range. ");
      Serial.println(servoIndex == 5 ? "Allowed: 17-90" : "Allowed: 0-180");
    }
  } else {
    Serial.print("Error: Servo ");
    Serial.print(servoIndex);
    Serial.println(" is not connected.");
  }
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
  if (millis() - tmr >= 5000) {
    ultra_sonic();
    tmr = millis();
  }
  static uint32_t tmr2;
  if (millis() - tmr2 >= 10000) {
    checkServoStatus();
    //writeInaInfo();
    tmr2 = millis();
  }
}

void ultra_sonic() {
  digitalWrite(trigPin, LOW);
  delayMicroseconds(5);
  digitalWrite(trigPin, HIGH);
  delayMicroseconds(10);
  digitalWrite(trigPin, LOW);

  duration = pulseIn(echoPin, HIGH);
  distance = (duration / 2) / 29.1;;

  if (distance > 0 && ultrasonicConnected) {
    Serial.print("Distance: ");
    Serial.println(distance);
  } else {
    checkUltrasonicSensor();
  }
}

void checkServoStatus() {
  float averagePower[3] = {70.0, 200.0, 65.0}; // Set average power for each channel

  for (int ch = 0; ch < 3; ch++) {
    float currentPower = INA.getPower_mW(ch);
    if (currentPower < averagePower[ch] / 2.5) {
      if (ch == 0) {
        servoConnected[0] = false;
        servoConnected[5] = false;
        Serial.println("Error: Both servos in channel 0 (servos 0 and 5) disconnected due to low power.");
      } else if (ch == 1) {
        servoConnected[1] = false;
        servoConnected[4] = false;
        Serial.println("Error: Both servos in channel 1 (servos 1 and 4) disconnected due to low power.");
      } else if (ch == 2) {
        servoConnected[2] = false;
        servoConnected[3] = false;
        Serial.println("Error: Both servos in channel 2 (servos 2 and 3) disconnected due to low power.");
      }
    } else if (currentPower < averagePower[ch] / 1.5) {
      if (ch == 0) {
        servoConnected[0] = false;
        servoConnected[5] = false;
        Serial.println("Error: One servo in channel 0 (servos 0 and 5) disconnected due to low power.");
      } else if (ch == 1) {
        servoConnected[1] = false;
        servoConnected[4] = false;
        Serial.println("Error: One servo in channel 1 (servos 1 and 4) disconnected due to low power.");
      } else if (ch == 2) {
        servoConnected[2] = false;
        servoConnected[3] = false;
        Serial.println("Error: One servo in channel 2 (servos 2 and 3) disconnected due to low power.");
      }
    } else if (currentPower > averagePower[ch]) {
      if (ch == 0 && !(servoConnected[0] || servoConnected[5])) {
        servoConnected[0] = true;
        servoConnected[5] = true;
        Serial.println("Message: Both servos in channel 0 (servos 0 and 5) connected.");
      } else if (ch == 1 && !(servoConnected[1] || servoConnected[4])) {
        servoConnected[1] = true;
        servoConnected[4] = true;
        Serial.println("Message: Both servos in channel 1 (servos 1 and 4) connected.");
      } else if (ch == 2 && !(servoConnected[2] || servoConnected[3])) {
        servoConnected[2] = true;
        servoConnected[3] = true;
        Serial.println("Message: Both servos in channel 2 (servos 2 and 3) connected.");
      }
    }
  }
}

void checkUltrasonicSensor() {
  digitalWrite(trigPin, LOW);
  delayMicroseconds(5);
  digitalWrite(trigPin, HIGH);
  delayMicroseconds(10);
  digitalWrite(trigPin, LOW);

  duration = pulseIn(echoPin, HIGH);
  distance =  (duration / 2) / 29.1;;

  static int debounceCounter = 0;
  const int debounceThreshold = 3;

  if (distance == 0) {
    debounceCounter++;
    if (debounceCounter >= debounceThreshold) {
      ultrasonicConnected = false;
      Serial.println("Error: Ultrasonic sensor disconnected.");
      debounceCounter = 0;
    }
  } else {
    debounceCounter = 0;
    if (!ultrasonicConnected) {
      ultrasonicConnected = true;
      Serial.println("Message: Ultrasonic sensor connected.");
    }
  }
  Serial.println("Message: Ultrasonic checked.");
}

void writeInaInfo() {
  for (int ch = 0; ch < 3; ch++) {
    Serial.print("Channel: ");
    Serial.print(ch);
    Serial.print(" | Bus Voltage: ");
    Serial.print(INA.getBusVoltage(ch), 3);
    Serial.print(" V | Shunt Voltage: ");
    Serial.print(INA.getShuntVoltage_mV(ch), 3);
    Serial.print(" mV | Current: ");
    Serial.print(INA.getCurrent_mA(ch), 3);
    Serial.print(" mA | Power: ");
    Serial.print(INA.getPower_mW(ch), 3);
    Serial.println(" mW");

}