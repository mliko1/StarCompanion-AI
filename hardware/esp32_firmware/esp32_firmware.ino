/*
 * 星伴AI · ESP32 智能交互盒固件
 * -----------------------------------------
 * 与桌面端 hardware/esp32_controller.py 配套使用。
 *
 * 串口协议（115200 8N1，行尾 \n）：
 *   电脑 -> ESP32:
 *     "LED:ON"    点亮 LED
 *     "LED:OFF"   熄灭 LED
 *     "BUZZ:500"  蜂鸣 500 毫秒
 *   ESP32 -> 电脑（主动上报）:
 *     "BTN:1"     按键按下
 *     "BTN:0"     按键松开
 *
 * 接线（可按实际修改下方引脚定义）：
 *   LED      -> GPIO 2（ESP32 开发板通常板载 LED 也接 2）
 *   蜂鸣器   -> GPIO 13（有源蜂鸣器，高电平响；无源蜂鸣器请自行加 PWM）
 *   大按键   -> GPIO 0（一端接 GPIO0，另一端接 GND，使用内部上拉）
 *
 * 烧录：Arduino IDE 选 "ESP32 Dev Module"，端口选对应 COM 口，编译上传。
 */

#define PIN_LED      2    // LED 输出
#define PIN_BUZZER   13   // 蜂鸣器输出
#define PIN_BUTTON   0    // 按键输入（内部上拉，按下接地）

// 按键去抖
unsigned long lastBtnRead = 0;
const unsigned long DEBOUNCE_MS = 30;
int lastBtnState = HIGH;      // 上拉：松开为 HIGH，按下为 LOW
bool lastReported = false;    // 上一次上报的按下状态

// 蜂鸣计时（非阻塞）
unsigned long buzzUntil = 0;

void setup() {
  Serial.begin(115200);

  pinMode(PIN_LED, OUTPUT);
  pinMode(PIN_BUZZER, OUTPUT);
  pinMode(PIN_BUTTON, INPUT_PULLUP);

  digitalWrite(PIN_LED, LOW);
  digitalWrite(PIN_BUZZER, LOW);

  // 上电握手，便于电脑端确认设备已就绪
  Serial.println("READY");
}

void loop() {
  // ---------- 1. 处理串口命令 ----------
  while (Serial.available() > 0) {
    String line = Serial.readStringUntil('\n');
    line.trim();
    if (line.length() == 0) continue;

    if (line == "LED:ON") {
      digitalWrite(PIN_LED, HIGH);
    } else if (line == "LED:OFF") {
      digitalWrite(PIN_LED, LOW);
    } else if (line.startsWith("BUZZ:")) {
      unsigned long ms = line.substring(5).toInt();
      if (ms > 0) {
        digitalWrite(PIN_BUZZER, HIGH);
        buzzUntil = millis() + ms;
      }
    }
  }

  // ---------- 2. 蜂鸣到时关闭 ----------
  if (buzzUntil > 0 && millis() >= buzzUntil) {
    digitalWrite(PIN_BUZZER, LOW);
    buzzUntil = 0;
  }

  // ---------- 3. 按键检测（带去抖） ----------
  int reading = digitalRead(PIN_BUTTON);
  if (reading != lastBtnState) {
    lastBtnRead = millis();
  }
  if (millis() - lastBtnRead > DEBOUNCE_MS && reading != lastReported) {
    // 状态稳定后确认按下/松开（上拉：LOW=按下）
    bool pressed = (reading == LOW);
    Serial.print("BTN:");
    Serial.println(pressed ? "1" : "0");
    lastReported = reading;
  }
  lastBtnState = reading;

  delay(5);
}
