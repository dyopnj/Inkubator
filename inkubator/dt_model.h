/*
 * dt_model.h  �  Decision Tree untuk Inkubator ESP32
 * Generated : 2026-06-15 22:16:52
 * Dataset   : temperature_humidity_data.csv (Kaggle)
 * Depth     : Heater=5, Fan=5
 * Nodes     : Heater=51, Fan=49
 *
 * Input  : suhu (�C), kelembapan (%)
 * Output : heater_pct (0-100), fan_pct (0-100)
 *
 * Keunggulan: tidak perlu normalisasi, 0 RAM runtime, eksekusi super cepat
 */

#ifndef DT_MODEL_H
#define DT_MODEL_H

// ====================================================================
//  HEATER DECISION TREE  (depth=5, 51 nodes)
// ====================================================================
static float dt_predict_heater(float suhu, float kelembapan) {
    if (suhu <= 38.25f) {
        if (suhu <= 38.05f) {
            if (suhu <= 36.95f) {
                if (suhu <= 36.65f) {
                    if (kelembapan <= 50.65f) {
                        return 94.68f;
                    } else {
                        return 82.50f;
                    }
                } else {
                    if (suhu <= 36.85f) {
                        return 79.59f;
                    } else {
                        return 75.92f;
                    }
                }
            } else {
                if (suhu <= 37.05f) {
                    if (kelembapan <= 43.95f) {
                        return 72.00f;
                    } else {
                        return 72.33f;
                    }
                } else {
                    if (suhu <= 37.15f) {
                        return 67.97f;
                    } else {
                        return 64.98f;
                    }
                }
            }
        } else {
            if (suhu <= 38.15f) {
                if (kelembapan <= 48.35f) {
                    if (kelembapan <= 48.05f) {
                        return 55.00f;
                    } else {
                        return 51.60f;
                    }
                } else {
                    if (kelembapan <= 48.95f) {
                        return 48.17f;
                    } else {
                        return 43.29f;
                    }
                }
            } else {
                if (kelembapan <= 50.40f) {
                    if (kelembapan <= 48.50f) {
                        return 46.00f;
                    } else {
                        return 42.88f;
                    }
                } else {
                    return 33.50f;
                }
            }
        }
    } else {
        if (suhu <= 38.45f) {
            if (suhu <= 38.35f) {
                if (kelembapan <= 50.75f) {
                    if (kelembapan <= 46.45f) {
                        return 38.00f;
                    } else {
                        return 37.27f;
                    }
                } else {
                    if (kelembapan <= 53.05f) {
                        return 29.00f;
                    } else {
                        return 27.00f;
                    }
                }
            } else {
                if (kelembapan <= 46.25f) {
                    return 29.00f;
                } else {
                    return 30.11f;
                }
            }
        } else {
            if (suhu <= 41.55f) {
                if (kelembapan <= 49.65f) {
                    if (kelembapan <= 48.05f) {
                        return 20.00f;
                    } else {
                        return 18.46f;
                    }
                } else {
                    if (kelembapan <= 51.15f) {
                        return 16.62f;
                    } else {
                        return 14.80f;
                    }
                }
            } else {
                return 0.00f;
            }
        }
    }
}

// ====================================================================
//  FAN DECISION TREE  (depth=5, 49 nodes)
// ====================================================================
static float dt_predict_fan(float suhu, float kelembapan) {
    if (suhu <= 38.25f) {
        if (suhu <= 37.05f) {
            if (suhu <= 36.65f) {
                if (kelembapan <= 68.40f) {
                    if (kelembapan <= 48.45f) {
                        return 15.04f;
                    } else {
                        return 20.18f;
                    }
                } else {
                    if (kelembapan <= 71.40f) {
                        return 26.33f;
                    } else {
                        return 29.92f;
                    }
                }
            } else {
                if (suhu <= 36.95f) {
                    if (suhu <= 36.85f) {
                        return 26.32f;
                    } else {
                        return 30.05f;
                    }
                } else {
                    if (kelembapan <= 43.95f) {
                        return 33.00f;
                    } else {
                        return 31.67f;
                    }
                }
            }
        } else {
            if (suhu <= 38.05f) {
                if (suhu <= 37.15f) {
                    if (kelembapan <= 49.45f) {
                        return 35.98f;
                    } else {
                        return 38.40f;
                    }
                } else {
                    if (kelembapan <= 49.55f) {
                        return 40.00f;
                    } else {
                        return 46.79f;
                    }
                }
            } else {
                if (suhu <= 38.15f) {
                    if (kelembapan <= 48.35f) {
                        return 47.02f;
                    } else {
                        return 54.77f;
                    }
                } else {
                    if (kelembapan <= 50.40f) {
                        return 54.03f;
                    } else {
                        return 65.00f;
                    }
                }
            }
        }
    } else {
        if (suhu <= 41.55f) {
            if (suhu <= 38.45f) {
                if (suhu <= 38.35f) {
                    if (kelembapan <= 50.75f) {
                        return 60.01f;
                    } else {
                        return 70.80f;
                    }
                } else {
                    if (kelembapan <= 49.15f) {
                        return 66.99f;
                    } else {
                        return 69.00f;
                    }
                }
            } else {
                if (kelembapan <= 49.95f) {
                    if (kelembapan <= 48.75f) {
                        return 74.95f;
                    } else {
                        return 78.06f;
                    }
                } else {
                    if (kelembapan <= 51.15f) {
                        return 80.70f;
                    } else {
                        return 84.84f;
                    }
                }
            }
        } else {
            return 100.00f;
        }
    }
}

// ====================================================================
//  INFERENCE ENGINE
// ====================================================================

/**
 * dt_predict() � panggil dari loop kontrol
 * @param suhu        suhu aktual (�C)
 * @param kelembapan  kelembapan aktual (%)
 * @param heater      [out] heater output 0-100%
 * @param kipas       [out] kipas output 0-100%
 */
static void dt_predict(float suhu, float kelembapan, int *heater, int *kipas) {
    float h_raw = dt_predict_heater(suhu, kelembapan);
    float f_raw = dt_predict_fan(suhu, kelembapan);

    int h = (int)(h_raw + 0.5f);
    int f = (int)(f_raw + 0.5f);
    if (h < 0) h = 0; if (h > 100) h = 100;
    if (f < 0) f = 0; if (f > 100) f = 100;

    // Hard safety
    if (suhu > 41.5f) { h = 0;   f = 100; }
    if (suhu < 34.0f) { h = 100; f = 10;  }

    *heater = h;
    *kipas  = f;
}

#endif // DT_MODEL_H
