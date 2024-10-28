#include <Servo.h>

Servo servo_0;
Servo servo_1;
Servo servo_2;
Servo servo_3;
Servo servo_4;
Servo servo_5;

#define trigPin 12
#define echoPin 13

int duration;
int distance;

void setup() {

  pinMode(trigPin, OUTPUT);
  pinMode(echoPin, INPUT);

  Serial.begin(9600);
  servo_0.attach(3);
  servo_1.attach(5);
  servo_2.attach(6);
  servo_3.attach(9);
  servo_4.attach(10);
  servo_5.attach(11);
}

void loop() {
  if (Serial.available() > 0) {
    String input = Serial.readStringUntil('\n');
    int separatorIndex = input.indexOf(' ');
    if (separatorIndex != -1) {
      int servoIndex = input.substring(0, separatorIndex).toInt();
      int servoValue = input.substring(separatorIndex + 1).toInt();
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
    }
  }


  static uint32_t tmr;
  if (millis() - tmr >= 1000) {
    ultra_sonic();
    tmr = millis();
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
  Serial.print("distance: ");
  Serial.println(distance);
}