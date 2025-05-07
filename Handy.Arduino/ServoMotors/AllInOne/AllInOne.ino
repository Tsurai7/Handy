#include <Servo.h>

Servo servo_0;
Servo servo_1;
Servo servo_2;
Servo servo_3;
Servo servo_4;
Servo servo_5;

#define trigPin 13
#define echoPin 12

int duration;
int distance;

int servoPins[] = {6, 5, 11, 9, 3, 10};

int currentPos[6] = {90, 90, 90, 90, 90, 90};
int targetPos[6] = {90, 90, 90, 90, 90, 90};

bool ultrasonicConnected = true;

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
}

void moveServo(int servoIndex, int servoValue) {
  if (servoIndex < 5 && servoValue >= 0 && servoValue <= 180) {
    switch (servoIndex) {
      case 0: servo_0.write(servoValue); break;
      case 1: servo_1.write(servoValue); break;
      case 2: servo_2.write(servoValue); break;
      case 3: servo_3.write(servoValue); break;
      case 4: servo_4.write(servoValue); break;
    }
  } else if (servoIndex == 5 && servoValue >= 17 && servoValue <= 90) {
    servo_5.write(servoValue);
  } else {
    Serial.print("Error: Servo ");
    Serial.print(servoIndex);
    Serial.print(" angle out of range. ");
    Serial.println(servoIndex == 5 ? "Allowed: 17-90" : "Allowed: 0-180");
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
}

void ultra_sonic() {
  digitalWrite(trigPin, LOW);
  delayMicroseconds(5);
  digitalWrite(trigPin, HIGH);
  delayMicroseconds(10);
  digitalWrite(trigPin, LOW);

  duration = pulseIn(echoPin, HIGH);
  distance = (duration / 2) / 29.1;

  if (distance > 0) {
    Serial.print("Distance: ");
    Serial.println(distance);
  } else {
    checkUltrasonicSensor();
  }
}

void checkUltrasonicSensor() {
  digitalWrite(trigPin, LOW);
  delayMicroseconds(5);
  digitalWrite(trigPin, HIGH);
  delayMicroseconds(10);
  digitalWrite(trigPin, LOW);

  duration = pulseIn(echoPin, HIGH);
  distance = (duration / 2) / 29.1;

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
