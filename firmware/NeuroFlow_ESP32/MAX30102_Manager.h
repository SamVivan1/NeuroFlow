#ifndef MAX30102_MANAGER_H
#define MAX30102_MANAGER_H

#include "MAX30105.h"
#include <Wire.h>
#include "SystemConfig.h"

class MAX30102_Manager {
private:
    MAX30105 maxSensor;
    
    // State variables
    long irDC, redDC;
    bool dcInitialized;
    long irFilteredPrev;
    long irPeakValue;
    bool irRising;
    unsigned long lastPeakTime;
    
    long peakIntervals[5];
    int peakIntervalIndex;
    int peakIntervalCount;
    
    int currentBPM;
    int currentSpO2;
    int lastValidBPM;
    int lastValidSpO2;
    
    long redMax, redMin;
    long irMax, irMin;
    
    bool fingerPresent;
    bool warmupDone;
    unsigned long fingerDetectedTime;
    unsigned long fingerLiftedTime;
    
    // History
    int bpmHistory[HISTORY_SIZE];
    int spo2History[HISTORY_SIZE];
    int historyIndex;
    int historyCount;
    unsigned long lastHistorySave;
    unsigned long lastSpo2Calc;

    void registerPeak(unsigned long now);
    void calculateSpO2();

public:
    MAX30102_Manager();
    
    bool begin(TwoWire* wire);
    void wakeUp();
    void shutDown();
    
    void update(unsigned long now);
    void updateHistory(unsigned long now);
    
    int getDisplayBPM(unsigned long now) const;
    int getDisplaySpO2(unsigned long now) const;
    int getAverageBPM() const;
    
    bool isFingerPresent() const { return fingerPresent; }
    bool isWarmupDone() const { return warmupDone; }
    unsigned long getFingerDetectedTime() const { return fingerDetectedTime; }
};

#endif // MAX30102_MANAGER_H
