/**
 * web_server.cpp  —  ESP32 Web Server (template)
 *
 * Contoh integrasi dengan ESP32 WebServer:
 *
 *   #include <WebServer.h>
 *   #include "inkubator.h"
 *   #include "web/web_server.h"
 *
 *   Incubator ink;
 *   WebServer server(80);
 *   float suhu_aktual, humi_aktual;  // update dari sensor tiap loop
 *
 *   void handleStatus() {
 *     String json = inc_status_json(&ink, suhu_aktual, humi_aktual);
 *     server.send(200, "application/json", json);
 *   }
 *
 *   void handleSet() {
 *     for (int i = 0; i < server.args(); i++) {
 *       String key = server.argName(i);
 *       float val = server.arg(i).toFloat();
 *       if      (key == "h_kp") inc_set_param(&ink, PARAM_H_KP, val);
 *       else if (key == "h_ki") inc_set_param(&ink, PARAM_H_KI, val);
 *       else if (key == "h_kd") inc_set_param(&ink, PARAM_H_KD, val);
 *       else if (key == "h_sp") inc_set_param(&ink, PARAM_H_SP, val);
 *       else if (key == "f_kp") inc_set_param(&ink, PARAM_F_KP, val);
 *       else if (key == "f_ki") inc_set_param(&ink, PARAM_F_KI, val);
 *       else if (key == "f_kd") inc_set_param(&ink, PARAM_F_KD, val);
 *       else if (key == "f_sp") inc_set_param(&ink, PARAM_F_SP, val);
 *       else if (key == "m_heater") inc_set_param(&ink, PARAM_M_HEATER, val);
 *       else if (key == "m_fan")    inc_set_param(&ink, PARAM_M_FAN, val);
 *     }
 *     server.send(200, "text/plain", "OK");
 *   }
 *
 *   void handleMode() {
 *     String mode = server.arg("mode");
 *     inc_set_mode(&ink, mode == "MANUAL" ? MODE_MANUAL : MODE_AUTO);
 *     server.send(200, "text/plain", "OK");
 *   }
 *
 *   void setup() {
 *     Serial.begin(115200);
 *     inc_init(&ink);
 *
 *     // WiFi.connect(...)
 *
 *     server.on("/",          []{ server.send(200, "text/html", WEB_INDEX_HTML); });
 *     server.on("/api/status", handleStatus);
 *     server.on("/api/set",   handleSet);
 *     server.on("/api/mode",  handleMode);
 *     server.begin();
 *   }
 *
 *   void loop() {
 *     server.handleClient();
 *     inc_loop(&ink);
 *   }
 */
#include "web_server.h"

void web_init(void) {
    // Implementasi depend pada library WebServer yang dipilih
}

void web_handle(void) {
    // Panggil server.handleClient() di loop()
}
