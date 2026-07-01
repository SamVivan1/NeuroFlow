#include "MAX30102_Manager.h"
#include <Arduino.h>

MAX30102_Manager::MAX30102_Manager() {
    irDC = 0; redDC = 0;
    dcInitialized = false;
    irFilteredPrev = 0;
    irPeakValue = 0;
    irRising = false;
    lastPeakTime = 0;
    
    peakIntervalIndex = 0;
    peakIntervalCount = 0;
    
    currentBPM = -1;
    currentSpO2 = -1;
    lastValidBPM = -1;
    lastValidSpO2 = -1;
    
    redMax = -100000; redMin = 100000;
    irMax = -100000; irMin = 100000;
    
    fingerPresent = false;
    warmupDone = false;
    fingerDetectedTime = 0;
    fingerLiftedTime = 0;
    
    historyIndex = 0;
    historyCount = 0;
    lastHistorySave = 0;
    lastSpo2Calc = 0;
    
    for (int i = 0; i < HISTORY_SIZE; i++) {
        bpmHistory[i] = -1;
        spo2History[i] = -1;
        if(i < 5) peakIntervals[i] = 0;
    }
}

bool MAX30102_Manager::begin(TwoWire* wire) {
    if (!maxSensor.begin(*wire, I2C_FREQ)) {
        return false;
    }
    
    maxSensor.setup(60, 4, 2, 100, 411, 4096);
    maxSensor.setPulseAmplitudeRed(255); 
    maxSensor.setPulseAmplitudeGreen(0);
    return true;
}

void MAX30102_Manager::wakeUp() {
    maxSensor.wakeUp();
    maxSensor.setup(60, 4, 2, 100, 411, 4096);
    maxSensor.setPulseAmplitudeRed(255); 
    maxSensor.setPulseAmplitudeGreen(0);
}

void MAX30102_Manager::shutDown() {
    maxSensor.shutDown();
}

void MAX30102_Manager::registerPeak(unsigned long now) {
    long interval = now - lastPeakTime;
    if (lastPeakTime != 0 && interval > PEAK_MIN_INTERVAL_MS && interval < PEAK_MAX_INTERVAL_MS) {
        peakIntervals[peakIntervalIndex % 5] = interval;
        peakIntervalIndex++;
        if (peakIntervalCount < 5) peakIntervalCount++;
        long sum = 0;
        for (int i = 0; i < peakIntervalCount; i++) sum += peakIntervals[i];
        int bpm = 60000 / (sum / peakIntervalCount);
        if (bpm >= 40 && bpm <= 180) {
            currentBPM = bpm;
            lastValidBPM = bpm;
        }
    }
    lastPeakTime = now;
}

void MAX30102_Manager::calculateSpO2() {
    long redAC = redMax - redMin;
    long irAC = irMax - irMin;
    if (redAC > 0 && irAC > 0 && redDC > 0 && irDC > 0) {
        float ratio = ((float)redAC / redDC) / ((float)irAC / irDC);
        int spo2 = constrain((int)(110 - 25 * ratio), 70, 100);
        currentSpO2 = spo2;
        lastValidSpO2 = spo2;
    }
    redMax = -100000; redMin = 100000;
    irMax = -100000; irMin = 100000;
}

void MAX30102_Manager::update(unsigned long now) {
    if (!maxSensor.available()) {
        maxSensor.check();
        if (!maxSensor.available()) return;
    }
    long irValue = maxSensor.getIR();
    long redValue = maxSensor.getRed();
    maxSensor.nextSample();

    if (irValue < IR_FINGER_THRESHOLD) {
        if (fingerPresent) {
            fingerPresent = false;
            fingerLiftedTime = now;
        }
        return;
    }

    if (!fingerPresent) {
        fingerPresent = true;
        warmupDone = false;
        fingerDetectedTime = now;
        dcInitialized = false;
        peakIntervalCount = 0;
        peakIntervalIndex = 0;
        lastPeakTime = 0;
        currentBPM = -1;
        currentSpO2 = -1;
        irFilteredPrev = 0;
        irRising = false;
    }

    if (!dcInitialized) {
        irDC = irValue; redDC = redValue;
        dcInitialized = true;
    }

    irDC = (DC_ALPHA * irDC) + ((1 - DC_ALPHA) * irValue);
    redDC = (DC_ALPHA * redDC) + ((1 - DC_ALPHA) * redValue);

    long irFiltered = irValue - irDC;
    long redFiltered = redValue - redDC;

    if (!warmupDone) {
        if (now - fingerDetectedTime >= WARMUP_MS) warmupDone = true;
        return;
    }

    if (irFiltered > irFilteredPrev) {
        irRising = true;
        irPeakValue = irFiltered;
    } else if (irRising && irFiltered < irFilteredPrev) {
        irRising = false;
        if (irPeakValue > PEAK_THRESHOLD) registerPeak(now);
        irPeakValue = 0;
    }
    irFilteredPrev = irFiltered;

    redMax = max(redMax, redFiltered); redMin = min(redMin, redFiltered);
    irMax = max(irMax, irFiltered); irMin = min(irMin, irFiltered);

    if (now - lastSpo2Calc >= 1000) {
        lastSpo2Calc = now;
        calculateSpO2();
    }
}

void MAX30102_Manager::updateHistory(unsigned long now) {
    if (now - lastHistorySave < 1000) return;
    lastHistorySave = now;
    int bpm = getDisplayBPM(now);
    int spo2 = getDisplaySpO2(now);
    if (bpm > 0 || spo2 > 0) {
        bpmHistory[historyIndex] = bpm;
        spo2History[historyIndex] = spo2;
        historyIndex = (historyIndex + 1) % HISTORY_SIZE;
        if (historyCount < HISTORY_SIZE) historyCount++;
    }
}

int MAX30102_Manager::getDisplayBPM(unsigned long now) const {
    if (fingerPresent && warmupDone && currentBPM >= 40) return currentBPM;
    if (!fingerPresent && lastValidBPM > 0 && now - fingerLiftedTime < LAST_DATA_HOLD_MS) return lastValidBPM;
    return -1;
}

int MAX30102_Manager::getDisplaySpO2(unsigned long now) const {
    if (fingerPresent && warmupDone && currentSpO2 > 0) return currentSpO2;
    if (!fingerPresent && lastValidSpO2 > 0 && now - fingerLiftedTime < LAST_DATA_HOLD_MS) return lastValidSpO2;
    return -1;
}

int MAX30102_Manager::getAverageBPM() const {
    int sum = 0, count = 0;
    for (int i = 0; i < historyCount; i++) {
        if (bpmHistory[i] > 0) { sum += bpmHistory[i]; count++; }
    }
    return count > 0 ? sum / count : -1;
}
