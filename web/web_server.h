/**
 * web_server.h  —  ESP32 Web Server handler untuk Inkubator Control
 * Endpoint:
 *   GET  /           → serve dashboard HTML
 *   GET  /api/status → JSON status
 *   GET  /api/set?kp=val → set parameter
 *   GET  /api/mode?mode=AUTO|MANUAL → ganti mode
 *
 * Integrasi di main.cpp:
 *   #include "inkubator.h"
 *   #include "web/web_server.h"
 *   Incubator ink;
 *
 *   void setup() { inc_init(&ink); web_init(); }
 *   void loop()  { inc_loop(&ink); web_handle(); }
 */
#ifndef WEB_SERVER_H
#define WEB_SERVER_H

void web_init(void);
void web_handle(void);

#endif
