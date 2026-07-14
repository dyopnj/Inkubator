/**************************************************
 * INKUBATOR IKI-3b — DT+PID + MQTT + OLED + PWM
 *
 * Sensor : DHT22 (pin 17) — suhu & kelembapan
 * Heater : AC Dimmer — ZC pin 18, TRIAC trigger pin 5
 * Fan    : DC PWM — pin 26
 * Motor  : Relay — pin 25 (ON/OFF manual via OLED)
 * Buzzer : pin 27 (active HIGH)
 * OLED   : 128x64 I2C — SDA=21, SCL=22 (opsional)
 * Tombol : UP pin 32, DOWN pin 19 (active LOW)
 *
 * MQTT   : pub inkubator/status, sub inkubator/set/param & /set/mode
 **************************************************/

#include <Arduino.h>
#include <Wire.h>
#include <DHT.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <WiFi.h>
#include <WiFiManager.h>
#include <PubSubClient.h>
#include "esp_timer.h"
#include "esp_log.h"
#include <time.h>
#include "dt_model.h"

// ===================== PIN =====================
#define DHTPIN      17
#define DHTTYPE     DHT22
#define TRIGGER_PIN 18     // TRIAC gate (heater dimmer)
#define FAN_PIN     26
#define ZC_PIN      5
#define RELAY_PIN   25    // Motor relay
#define BUZZER_PIN  27
#define BTN_UP      32
#define BTN_DOWN    19

// ===================== I2C =====================
#define I2C_SDA     21
#define I2C_SCL     22

// ===================== OLED =====================
#define SCREEN_WIDTH  128
#define SCREEN_HEIGHT 64
#define OLED_RESET    -1
Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET);

// ===================== DHT =====================
DHT dht(DHTPIN, DHTTYPE);

// ===================== FAN =====================
#define FAN_KICK_MS  250

// ===================== MQTT =====================
const char MQTT_HOST_DEFAULT[] = "103.253.212.182";
char mqtt_host[16];
const int   MQTT_PORT = 1883;
const char* MQTT_TOPIC_STATUS = "inkubator/status";
const char* MQTT_TOPIC_PARAM  = "inkubator/set/param";
const char* MQTT_TOPIC_MODE   = "inkubator/set/mode";

WiFiClient wifi;
PubSubClient mqtt(wifi);
unsigned long lastPub = 0;
unsigned long lastMqttRetry = 0;

// ===================== STATE =====================
enum ControlMode { AUTO, MANUAL };
enum UiState { UI_INTRO, UI_HOME, UI_EDIT_HEAT, UI_EDIT_FAN };

ControlMode controlMode = AUTO;
UiState     uiState     = UI_INTRO;

// —— Sensor ——
float suhu = 0.0f, humi = 0.0f;
bool  suhuValid = false, humiValid = false;
unsigned long lastValidTempMs = 0, lastValidHumiMs = 0;
unsigned long lastDHTRead = 0;
const unsigned long SENSOR_DHT_MS = 3000;

// —— Output ——
int heaterPercent = 0;
int fanPercent    = 0;
int heaterManual  = 0;
int fanManual     = 40;
bool motorOn      = false;

// —— PID state ——
float h_int = 0, h_prev_err = 0;
float f_int = 0, f_prev_err = 0;
float h_kp = 8.0f, h_ki = 0.5f, h_kd = 2.0f, h_sp = 37.5f;
float f_kp = 6.0f, f_ki = 0.3f, f_kd = 1.5f, f_sp = 60.0f;

// ===================== DIMMER =====================
static volatile uint8_t dimBrightness = 0;
static esp_timer_handle_t dim_timer;

void IRAM_ATTR zeroCrossISR() {
  if (dimBrightness == 0) { digitalWrite(TRIGGER_PIN, LOW); return; }
  if (dimBrightness >= 255) { digitalWrite(TRIGGER_PIN, HIGH); return; }
  uint32_t delay_us = (uint32_t)(30 * (255 - dimBrightness) + 400);
  esp_timer_start_once(dim_timer, delay_us);
}

static void dimmerPulse(void* arg) {
  digitalWrite(TRIGGER_PIN, HIGH);
  ets_delay_us(20);
  digitalWrite(TRIGGER_PIN, LOW);
}

static void applyDimmer(int pct) {
  dimBrightness = (uint8_t)map(pct, 0, 100, 0, 255);
}

// ===================== FAN PWM =====================
static bool fanKickActive = false;
static unsigned long fanKickStart = 0;
static int lastFanPercentApplied = -1;

static void applyFanPWM(int pct) {
  pct = constrain(pct, 0, 100);
  if (pct != lastFanPercentApplied) {
    lastFanPercentApplied = pct;
    if (pct <= 0) { analogWrite(FAN_PIN, 0); fanKickActive = false; return; }
    fanKickActive = true; fanKickStart = millis(); analogWrite(FAN_PIN, 255);
    return;
  }
  if (fanKickActive && millis() - fanKickStart >= FAN_KICK_MS) {
    analogWrite(FAN_PIN, constrain(map(pct, 0, 100, 70, 255), 70, 255));
    fanKickActive = false;
  }
}

// ===================== RELAY MOTOR =====================
static void applyMotor() {
  digitalWrite(RELAY_PIN, motorOn ? HIGH : LOW);
}

// Jadwal motor AUTO: tiap 6 jam, nyala 5 menit, mulai 07:00
static void updateMotorAuto() {
  if (controlMode != AUTO) return;
  time_t t; time(&t);
  struct tm *ti = localtime(&t);
  if (!ti) return;
  int since700 = (ti->tm_hour - 7) * 60 + ti->tm_min;
  bool on = false;
  if (since700 >= 0) {
    int pos = since700 % 360; // posisi dalam cycle 6 jam
    on = (pos < 2);           // 2 menit pertama nyala
  }
  if (on != motorOn) { motorOn = on; applyMotor(); markUiDirty(); }
}

// ===================== BUZZER =====================
static void beep(int count) {
  for (int i = 0; i < count; i++) {
    digitalWrite(BUZZER_PIN, HIGH); delay(80);
    digitalWrite(BUZZER_PIN, LOW);  if (i < count - 1) delay(60);
  }
}

// ===================== SENSOR DHT =====================
float readHumidityStable() {
  float v[3]; uint8_t n = 0;
  for (uint8_t i = 0; i < 3; ++i) {
    float h = dht.readHumidity();
    if (!isnan(h) && h >= 0 && h <= 100) v[n++] = h;
    delay(5);
  }
  if (n == 0) return NAN;
  if (n == 1) return v[0];
  if (n == 2) return (v[0] + v[1]) * 0.5f;
  // median of 3
  if (v[0] > v[1]) { float t = v[0]; v[0] = v[1]; v[1] = t; }
  if (v[1] > v[2]) { float t = v[1]; v[1] = v[2]; v[2] = t; }
  if (v[0] > v[1]) { float t = v[0]; v[0] = v[1]; v[1] = t; }
  return v[1];
}

float readTempStable() {
  float v[3]; uint8_t n = 0;
  for (uint8_t i = 0; i < 3; ++i) {
    float t = dht.readTemperature();
    if (!isnan(t)) v[n++] = t;
    delay(5);
  }
  if (n == 0) return NAN;
  if (n == 1) return v[0];
  if (n == 2) return (v[0] + v[1]) * 0.5f;
  if (v[0] > v[1]) { float t = v[0]; v[0] = v[1]; v[1] = t; }
  if (v[1] > v[2]) { float t = v[1]; v[1] = v[2]; v[2] = t; }
  if (v[0] > v[1]) { float t = v[0]; v[0] = v[1]; v[1] = t; }
  return v[1];
}

// ===================== UI SELECTOR =====================
const int selectableItemsAuto[]   = { 0, 6 };
const int selectableItemsManual[] = { 0, 3, 4, 6 };
int selectPos = 0;

unsigned long lastUserInput = 0;
const unsigned long BLINK_IDLE_TIMEOUT = 3000;
unsigned long introStart = 0;
unsigned long lastOLEDRefresh = 0;
const unsigned long OLED_MS = 150;
bool oledOk = false;
bool uiDirty = true;

void markUiDirty() { uiDirty = true; }

int getSelectableCount() {
  return (controlMode == AUTO)
    ? (int)(sizeof(selectableItemsAuto) / sizeof(selectableItemsAuto[0]))
    : (int)(sizeof(selectableItemsManual) / sizeof(selectableItemsManual[0]));
}

int getSelectableItem(int pos) {
  return (controlMode == AUTO) ? selectableItemsAuto[pos] : selectableItemsManual[pos];
}

int getActiveCard() {
  int item = getSelectableItem(selectPos);
  if (item == 0) return 2;
  if (item == 3) return 3;
  if (item == 4) return 4;
  if (item == 6) return 6;
  return -1;
}

// ===================== BUTTON =====================
bool upPressed = false, downPressed = false;
bool upLong = false, downLong = false;
bool upLastRaw = false, downLastRaw = false;
unsigned long tUp = 0, tDown = 0;
unsigned long upDebounceMs = 0, downDebounceMs = 0;

const bool BTN_ACTIVE_LEVEL = HIGH;
const unsigned long BTN_DEBOUNCE_MS = 25;
const unsigned long BTN_LONG_MS = 1000;

void moveUp()   { selectPos--; if (selectPos < 0) selectPos = getSelectableCount() - 1; }
void moveDown() { selectPos++; if (selectPos >= getSelectableCount()) selectPos = 0; }

void onShortPress(bool isUp) {
  if (uiState == UI_INTRO) return;

  if (uiState == UI_HOME) {
    if (isUp) { moveDown(); beep(1); return; }
    int idx = getSelectableItem(selectPos);
    if (idx == 0) {
      controlMode = (controlMode == AUTO) ? MANUAL : AUTO;
      if (selectPos >= getSelectableCount()) selectPos = getSelectableCount() - 1;
      beep(2);
    } else if (idx == 3 && controlMode == MANUAL) {
      uiState = UI_EDIT_HEAT; beep(1);
    } else if (idx == 4 && controlMode == MANUAL) {
      uiState = UI_EDIT_FAN; beep(1);
    } else if (idx == 6) {
      motorOn = !motorOn; applyMotor(); beep(1);
    }
    return;
  }

  if (uiState == UI_EDIT_HEAT && controlMode == MANUAL) {
    heaterManual = constrain(heaterManual + (isUp ? 5 : -5), 0, 100); beep(1);
    return;
  }
  if (uiState == UI_EDIT_FAN && controlMode == MANUAL) {
    fanManual = constrain(fanManual + (isUp ? 5 : -5), 0, 100); beep(1);
    return;
  }
}

void onLongPress(bool isUp) {
  if (!isUp && (uiState == UI_EDIT_HEAT || uiState == UI_EDIT_FAN)) {
    uiState = UI_HOME; beep(1);
  }
}

void updateSingleButton(bool raw, bool &lastRaw, bool &pressed, bool &longFired,
                        unsigned long &pressStart, unsigned long &debounceMark,
                        bool isUp, unsigned long now) {
  if (raw != lastRaw) { lastRaw = raw; debounceMark = now; return; }
  if (now - debounceMark < BTN_DEBOUNCE_MS) return;
  if (raw) {
    if (!pressed) { pressed = true; longFired = false; pressStart = now; markUiDirty(); }
    if (!longFired && (now - pressStart >= BTN_LONG_MS)) {
      onLongPress(isUp); longFired = true; markUiDirty();
    }
  } else if (pressed) {
    if (!longFired) onShortPress(isUp);
    pressed = false; longFired = false; markUiDirty();
  }
}

void handleButtons() {
  unsigned long now = millis();
  bool rawUp   = digitalRead(BTN_UP)   == BTN_ACTIVE_LEVEL;
  bool rawDown = digitalRead(BTN_DOWN) == BTN_ACTIVE_LEVEL;
  if (rawUp || rawDown) lastUserInput = now;
  updateSingleButton(rawUp,   upLastRaw,   upPressed,   upLong,   tUp,   upDebounceMs,   true,  now);
  updateSingleButton(rawDown, downLastRaw, downPressed, downLong, tDown, downDebounceMs, false, now);
}

// ===================== OLED DRAW =====================
void drawBox(int x, int y, int w, int h, bool active, bool blink) {
  if (active && blink) {
    display.fillRoundRect(x, y, w, h, 4, SSD1306_WHITE);
    display.setTextColor(SSD1306_BLACK);
  } else {
    display.drawRoundRect(x, y, w, h, 4, SSD1306_WHITE);
    display.setTextColor(SSD1306_WHITE);
  }
}

void drawOLED() {
  if (!oledOk) return;
  display.clearDisplay();
  display.setTextSize(1);
  display.setTextColor(SSD1306_WHITE);

  bool blink = false;
  if (millis() - lastUserInput < BLINK_IDLE_TIMEOUT)
    blink = ((millis() / 350) % 2) != 0;

  int active = getActiveCard();

  // Safety screen override
  if (suhuValid && suhu > 42.0f) {
    display.setTextSize(2);
    display.setCursor(18, 14); display.print("SAFETY ON");
    display.setTextSize(1);
    display.setCursor(30, 40); display.print("Suhu: "); display.print(suhu, 1); display.print(" C");
    display.display();
    return;
  }

  if (uiState == UI_INTRO) {
    display.setCursor(34, 20); display.print("INKUBATOR");
    display.setTextSize(2);
    display.setCursor(36, 32); display.print("IKI-3B");
  }
  else if (uiState == UI_HOME) {
    // Row 1: TEMP | HUMI | MODE
    drawBox(0, 0, 42, 20, false, false);
    display.setCursor(4, 4);   display.print("TEMP");
    display.setCursor(6, 12);  display.print(suhuValid ? String(suhu, 1) : "--.-");

    drawBox(43, 0, 42, 20, false, false);
    display.setCursor(47, 4);  display.print("HUMI");
    display.setCursor(49, 12); display.print(humiValid ? String(humi, 0) : "--");

    drawBox(86, 0, 42, 20, active == 2, blink);
    display.setCursor(90, 4);  display.print("MODE");
    display.setCursor(90, 12); display.print(controlMode == AUTO ? "AUTO" : "MAN");

    // Row 2: HEAT | FAN | MOTOR
    drawBox(0, 22, 42, 20, active == 3, blink);
    display.setCursor(4, 26);  display.print("HEAT");
    display.setCursor(6, 34);  display.print(heaterPercent); display.print("%");

    drawBox(43, 22, 42, 20, active == 4, blink);
    display.setCursor(47, 26); display.print("FAN");
    display.setCursor(49, 34); display.print(fanPercent); display.print("%");

    drawBox(86, 22, 42, 20, active == 6, blink);
    display.setCursor(90, 26); display.print("MOTOR");
    display.setCursor(90, 34); display.print(motorOn ? "ON" : "OFF");

    // Row 3: WiFi SSID
    drawBox(20, 44, 88, 18, false, false);
    display.setCursor(24, 48);
    display.setTextSize(1);
    String ssid = WiFi.SSID();
    if (ssid.length() == 0) ssid = "NO WiFi";
    display.print(ssid);
  }
  else if (uiState == UI_EDIT_HEAT) {
    display.setCursor(28, 4);  display.print("EDIT HEATER");
    display.drawLine(0, 14, 127, 14, SSD1306_WHITE);
    display.setTextSize(2);
    display.setCursor(50, 20); display.print(heaterManual); display.print("%");
    display.setTextSize(1);
    display.setCursor(8, 54);  display.print("^:+  v:-  hold v:back");
  }
  else if (uiState == UI_EDIT_FAN) {
    display.setCursor(22, 6);  display.print("EDIT FAN VALUE");
    display.drawLine(0, 16, 127, 16, SSD1306_WHITE);
    display.setTextSize(2);
    display.setCursor(40, 26); display.print(fanManual); display.print("%");
    display.setTextSize(1);
    display.setCursor(8, 54);  display.print("^:+  v:-  hold v:back");
  }

  display.display();
}

// ===================== PID =====================
static float _pid(float err, float *intg, float *prev,
                  float kp, float ki, float kd, float clamp) {
  *intg += err;
  if (*intg >  clamp) *intg =  clamp;
  if (*intg < -clamp) *intg = -clamp;
  float deriv = err - *prev;
  *prev = err;
  float out = kp * err + ki * *intg + kd * deriv;
  if (out < -clamp) out = -clamp;
  if (out >  clamp) out =  clamp;
  return out;
}

// ===================== CONTROL =====================
void updateControl() {
  float st = suhuValid ? suhu : 37.5f;
  float sh = humiValid ? humi : 60.0f;

  int hp, fp;
  if (controlMode == AUTO) {
    dt_predict(st, sh, &hp, &fp);
    float he = h_sp - st, fe = f_sp - sh;
    hp += (int)(_pid(he, &h_int, &h_prev_err, h_kp, h_ki, h_kd, 50.0f) + 0.5f);
    fp += (int)(_pid(fe, &f_int, &f_prev_err, f_kp, f_ki, f_kd, 50.0f) + 0.5f);
  } else {
    hp = heaterManual; fp = fanManual;
  }

  if (hp < 0) hp = 0; if (hp > 100) hp = 100;
  if (fp < 0) fp = 0; if (fp > 100) fp = 100;

  // Safety cutoff — suhu > 42°C
  if (suhuValid && suhu > 42.0f) { hp = 0; fp = 100; }

  heaterPercent = hp; fanPercent = fp;
}

// ===================== SENSOR =====================
void updateSensors() {
  unsigned long now = millis();
  if (now - lastDHTRead < SENSOR_DHT_MS) return;
  lastDHTRead = now;

  float t = readTempStable();
  if (!isnan(t)) { suhu = t; suhuValid = true; lastValidTempMs = now; markUiDirty(); }

  float h = readHumidityStable();
  if (!isnan(h)) { humi = h; humiValid = true; lastValidHumiMs = now; markUiDirty(); }
}

// ===================== JSON =====================
const char* statusJson() {
  static char buf[512];
  snprintf(buf, sizeof(buf),
    "{\"mode\":\"%s\",\"suhu\":%.1f,\"humi\":%.1f,"
    "\"heater\":%d,\"kipas\":%d,\"motor\":\"%s\","
    "\"pid_h\":{\"kp\":%.1f,\"ki\":%.2f,\"kd\":%.1f,\"sp\":%.1f},"
    "\"pid_f\":{\"kp\":%.1f,\"ki\":%.2f,\"kd\":%.1f,\"sp\":%.1f},"
    "\"manual\":{\"heater\":%d,\"fan\":%d}}",
    controlMode == AUTO ? "AUTO" : "MANUAL",
    suhu, humi, heaterPercent, fanPercent, motorOn ? "ON" : "OFF",
    h_kp, h_ki, h_kd, h_sp,
    f_kp, f_ki, f_kd, f_sp,
    heaterManual, fanManual);
  return buf;
}

// ===================== MQTT =====================
static void mqtt_cb(char *topic, byte *payload, unsigned int len) {
  char buf[64];
  if (len >= sizeof(buf)) len = sizeof(buf) - 1;
  memcpy(buf, payload, len); buf[len] = 0;

  String t = topic;
  if (t.endsWith("/mode")) {
    bool wasAuto = (controlMode == AUTO);
    controlMode = (strcmp(buf, "MANUAL") == 0) ? MANUAL : AUTO;
    if (wasAuto != (controlMode == AUTO)) beep(2);
    markUiDirty();
    return;
  }
  if (t.endsWith("/param")) {
    char *eq = strchr(buf, '=');
    if (!eq) return;
    *eq = 0; float val = atof(eq + 1);
    String k = buf;
    if      (k == "h_kp") { h_kp = val < 0 ? 0 : val; markUiDirty(); }
    else if (k == "h_ki") { h_ki = val < 0 ? 0 : val; markUiDirty(); }
    else if (k == "h_kd") { h_kd = val < 0 ? 0 : val; markUiDirty(); }
    else if (k == "h_sp") { h_sp = val < 0 ? 0 : val; markUiDirty(); }
    else if (k == "f_kp") { f_kp = val < 0 ? 0 : val; markUiDirty(); }
    else if (k == "f_ki") { f_ki = val < 0 ? 0 : val; markUiDirty(); }
    else if (k == "f_kd") { f_kd = val < 0 ? 0 : val; markUiDirty(); }
    else if (k == "f_sp") { f_sp = val < 0 ? 0 : val; markUiDirty(); }
    else if (k == "m_heater") { heaterManual = constrain((int)val, 0, 100); markUiDirty(); }
    else if (k == "m_fan")    { fanManual    = constrain((int)val, 0, 100); markUiDirty(); }
    else if (k == "motor")    { motorOn = strcmp(buf + (eq - buf) + 1, "ON") == 0; applyMotor(); markUiDirty(); }
  }
}

static void mqtt_reconnect() {
  if (mqtt.connected()) return;
  unsigned long now = millis();
  if (now - lastMqttRetry < 5000) return;
  lastMqttRetry = now;

  Serial.print("MQTT connect... ");
  if (mqtt.connect("inkubator-esp32")) {
    Serial.println("ok");
    mqtt.subscribe(MQTT_TOPIC_PARAM);
    mqtt.subscribe(MQTT_TOPIC_MODE);
  } else {
    Serial.print("fail rc="); Serial.print(mqtt.state());
    Serial.println(" next retry in 5s");
  }
}

// ===================== SETUP =====================
void setup() {
  Serial.begin(115200);

  pinMode(TRIGGER_PIN, OUTPUT);
  pinMode(FAN_PIN, OUTPUT);
  pinMode(RELAY_PIN, OUTPUT);
  pinMode(BUZZER_PIN, OUTPUT);
  pinMode(BTN_UP, INPUT);
  pinMode(BTN_DOWN, INPUT);
  pinMode(ZC_PIN, INPUT_PULLUP);

  digitalWrite(TRIGGER_PIN, LOW);
  analogWrite(FAN_PIN, 0);
  digitalWrite(RELAY_PIN, LOW);
  digitalWrite(BUZZER_PIN, LOW);

  attachInterrupt(digitalPinToInterrupt(ZC_PIN), zeroCrossISR, RISING);

  esp_timer_create_args_t ta = {
    .callback = &dimmerPulse, .arg = NULL,
    .dispatch_method = ESP_TIMER_TASK, .name = "ac_dimmer"
  };
  esp_timer_create(&ta, &dim_timer);

  // Suppress I2C error spam (OLED opsional)
  esp_log_level_set("i2c", ESP_LOG_NONE);
  esp_log_level_set("i2c.master", ESP_LOG_NONE);
  esp_log_level_set("i2c_master", ESP_LOG_NONE);

  Wire.begin(I2C_SDA, I2C_SCL);
  oledOk = display.begin(SSD1306_SWITCHCAPVCC, 0x3C);
  if (!oledOk) {
    Serial.println("OLED tidak terdeteksi — lanjut tanpa display");
  } else {
    display.setRotation(2);  // 180°
    display.clearDisplay();
    display.setTextColor(SSD1306_WHITE);
  }

  dht.begin();

  introStart = millis();
  lastUserInput = millis();
  markUiDirty();

  // Initial sensor read
  delay(2600);
  float t0 = readTempStable();
  if (!isnan(t0)) { suhu = t0; suhuValid = true; lastValidTempMs = millis(); }
  float h0 = readHumidityStable();
  if (!isnan(h0)) { humi = h0; humiValid = true; lastValidHumiMs = millis(); }

  strcpy(mqtt_host, MQTT_HOST_DEFAULT);

  WiFiManager wm;
  wm.setTimeout(10);
  wm.autoConnect("Inkubator-IKI3B");

  Serial.print("WiFi "); Serial.print(WiFi.localIP());
  Serial.print(" MQTT "); Serial.println(mqtt_host);

  configTime(7 * 3600, 0, "pool.ntp.org", "time.google.com");
  Serial.println("NTP sync...");
  {
    time_t t = 0;
    for (int i = 0; i < 20 && t < 100000; i++) {
      delay(500);
      time(&t);
    }
    struct tm *ti = localtime(&t);
    if (ti) Serial.printf("Time: %02d:%02d:%02d\n", ti->tm_hour, ti->tm_min, ti->tm_sec);
  }

  mqtt.setServer(mqtt_host, MQTT_PORT);
  mqtt.setCallback(mqtt_cb);
}

// ===================== LOOP =====================
void loop() {
  unsigned long now = millis();

  mqtt_reconnect();
  if (mqtt.connected()) {
    mqtt.loop();
  }

  handleButtons();

  if (uiState == UI_INTRO) {
    if (now - introStart >= 2000) { uiState = UI_HOME; markUiDirty(); }
    if (uiDirty || now - lastOLEDRefresh >= OLED_MS) { drawOLED(); lastOLEDRefresh = now; uiDirty = false; }
    return;
  }

  // Safety buzzer — 5 detik aja, 500ms on/off
  static unsigned long safetyAlarmStart = 0;
  static bool safetyWasActive = false;
  bool safetyNow = (suhuValid && suhu > 42.0f);
  if (safetyNow && !safetyWasActive) safetyAlarmStart = now;
  if (safetyNow && now - safetyAlarmStart < 5000) {
    digitalWrite(BUZZER_PIN, ((now / 500) % 2) ? HIGH : LOW);
  } else {
    digitalWrite(BUZZER_PIN, LOW);
  }
  safetyWasActive = safetyNow;

  updateSensors();

  static unsigned long lastControlRun = 0;
  const unsigned long CONTROL_MS = 500;
  if (now - lastControlRun >= CONTROL_MS) {
    lastControlRun = now;
    updateControl();
    applyDimmer(heaterPercent);
    applyFanPWM(fanPercent);
    updateMotorAuto();
    markUiDirty();
  }

  if (uiDirty || now - lastOLEDRefresh >= OLED_MS) {
    drawOLED();
    lastOLEDRefresh = now;
    uiDirty = false;
  }

  if (millis() - lastPub > 2000) {
    lastPub = millis();
    const char* json = statusJson();
    Serial.println(json);
    if (mqtt.connected()) {
      mqtt.publish(MQTT_TOPIC_STATUS, json, true);
    }
  }

  delay(5);
}
