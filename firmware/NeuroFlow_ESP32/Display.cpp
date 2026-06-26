#include "Display.h"

Display::Display() : display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET), available(false) {}

bool Display::begin(TwoWire* wire) {
    display = Adafruit_SSD1306(SCREEN_WIDTH, SCREEN_HEIGHT, wire, OLED_RESET);
    if (!display.begin(SSD1306_SWITCHCAPVCC, 0x3C)) {
        available = false;
        return false;
    }
    available = true;
    display.clearDisplay();
    display.display();
    return true;
}

void Display::printLines(const char* line1, const char* line2, const char* line3, const char* line4) {
    if (!available) return;
    display.clearDisplay();
    display.setTextSize(1);
    display.setTextColor(SSD1306_WHITE);
    display.setCursor(0, 0);
    display.println(line1);
    if (line2 && line2[0]) display.println(line2);
    if (line3 && line3[0]) display.println(line3);
    if (line4 && line4[0]) display.println(line4);
    display.display();
}

void Display::showMainScreen(const char* netStatus, float battVolt, int battPct, int hr, float tremor, int stress, bool fingerPresent, bool warmupDone, int warmupRemain) {
    if (!available) return;
    display.clearDisplay();
    display.setTextColor(SSD1306_WHITE);

    display.setTextSize(1);
    display.setCursor(0, 0);
    display.print(netStatus); 
    
    char battBuf[16];
    snprintf(battBuf, sizeof(battBuf), "%d%% %.1fV", battPct, battVolt);
    int16_t x, y; uint16_t w, h;
    display.getTextBounds(battBuf, 0, 0, &x, &y, &w, &h);
    display.setCursor(SCREEN_WIDTH - w, 0);
    display.print(battBuf);
    
    display.drawLine(0, 10, SCREEN_WIDTH, 10, SSD1306_WHITE);

    display.setCursor(0, 15);
    display.setTextSize(1);
    display.print("HEART RATE:");

    display.setCursor(0, 26);
    if (!fingerPresent) {
        display.setTextSize(1);
        display.print("-> Pasang Gelang <-");
    } else if (!warmupDone) {
        display.setTextSize(2);
        display.print("WARM: ");
        display.print(warmupRemain);
        display.print("s");
    } else {
        display.setTextSize(2);
        if (hr > 0) {
            display.print(hr);
            display.setTextSize(1);
            display.print(" BPM");
        } else {
            display.print("-- BPM");
        }
    }

    display.drawLine(0, 44, SCREEN_WIDTH, 44, SSD1306_WHITE);

    display.setTextSize(1);
    display.setCursor(0, 48);
    display.print("TREMOR");
    display.setCursor(0, 57);
    display.print(tremor, 2);

    display.setCursor(70, 48);
    display.print("STRESS");
    display.setCursor(70, 57);
    display.print(stress); 
    display.print(" %");

    display.display();
}

void Display::sleep() {
    if (available) {
        display.clearDisplay();
        display.display();
        display.ssd1306_command(SSD1306_DISPLAYOFF);
    }
}
