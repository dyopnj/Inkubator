/**
 * inkubator.h  —  Semua API: PID + Controller + Button + Web
 *
 * Integrasi ESP32:
 *   #include "inkubator.h"
 *   Incubator incubator;
 *
 *   void setup() { inc_init(&incubator); }
 *   void loop()  { inc_loop(&incubator); }  // baca sensor → kontrol → output
 *
 * Web server: pakai inc_status_json() + inc_set_param() + inc_set_mode()
 * Button:     inc_btn_mode(), inc_btn_up(), inc_btn_down(), inc_btn_set()
 */
#ifndef INKUBATOR_H
#define INKUBATOR_H

#include <stdint.h>

// ===== Mode =====
typedef enum { MODE_AUTO, MODE_MANUAL } IncMode;

// ===== Parameter yang bisa diatur =====
typedef enum {
    PARAM_H_KP, PARAM_H_KI, PARAM_H_KD, PARAM_H_SP,
    PARAM_F_KP, PARAM_F_KI, PARAM_F_KD, PARAM_F_SP,
    PARAM_M_HEATER, PARAM_M_FAN,
    PARAM_COUNT
} IncParam;

// ===== State utama =====
typedef struct {
    IncMode mode;
    int sel_param;       // parameter yg dipilih button
    int m_heater, m_fan; // manual output 0-100

    // PID heater
    float h_kp, h_ki, h_kd, h_sp;
    float h_int, h_prev_err;
    // PID fan
    float f_kp, f_ki, f_kd, f_sp;
    float f_int, f_prev_err;

    int cur_heater, cur_fan;  // output terkini 0-100%
} Incubator;

// ===== Init & Loop =====
void inc_init(Incubator *c);
void inc_loop(Incubator *c);  // baca sensor → kontrol → PWM

// ===== Button =====
void inc_btn_mode(Incubator *c);
void inc_btn_up(Incubator *c);
void inc_btn_down(Incubator *c);
void inc_btn_set(Incubator *c);

// ===== Web API =====
const char* inc_status_json(Incubator *c, float suhu, float humi);
void        inc_set_param(Incubator *c, IncParam p, float val);
float       inc_get_param(Incubator *c, IncParam p);
void        inc_set_mode(Incubator *c, IncMode mode);

#endif
