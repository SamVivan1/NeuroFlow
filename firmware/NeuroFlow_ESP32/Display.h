#ifndef DISPLAY_H
#define DISPLAY_H

#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <Wire.h>
#include "SystemConfig.h"

class Display {
private:
    Adafruit_SSD1306 display;
    bool available;

public:
    Display();
    
    bool begin(TwoWire* wire);
    void printLines(const char* line1, const char* line2 = "", const char* line3 = "", const char* line4 = "");
    void showMainScreen(const char* netStatus, float battVolt, int battPct, int hr, float tremor, int stress, bool fingerPresent, bool warmupDone, int warmupRemain);
    void sleep();
};

#endif // DISPLAY_H
