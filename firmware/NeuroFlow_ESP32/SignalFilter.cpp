#include "SignalFilter.h"
#include <math.h>

// ---------------- Moving Average Filter ----------------
MovingAverageFilter::MovingAverageFilter(int windowSize) {
    size = windowSize;
    buffer = new float[size];
    reset();
}

MovingAverageFilter::~MovingAverageFilter() {
    delete[] buffer;
}

void MovingAverageFilter::reset() {
    index = 0;
    count = 0;
    sum = 0.0f;
    for (int i = 0; i < size; i++) buffer[i] = 0.0f;
}

float MovingAverageFilter::process(float newValue) {
    sum -= buffer[index];
    buffer[index] = newValue;
    sum += buffer[index];
    
    index = (index + 1) % size;
    if (count < size) count++;
    
    return getAverage();
}

float MovingAverageFilter::getAverage() const {
    if (count == 0) return 0.0f;
    return sum / count;
}

float MovingAverageFilter::getVariance() const {
    if (count == 0) return 0.0f;
    float avg = getAverage();
    float variance = 0.0f;
    for (int i = 0; i < count; i++) {
        float diff = buffer[i] - avg;
        variance += (diff * diff);
    }
    return variance / count;
}

float MovingAverageFilter::getStandardDeviation() const {
    return sqrt(getVariance());
}

bool MovingAverageFilter::isFull() const {
    return count == size;
}

// ---------------- Low Pass Filter ----------------
LowPassFilter::LowPassFilter(float alphaValue) {
    alpha = alphaValue;
    reset();
}

void LowPassFilter::reset() {
    lastOutput = 0.0f;
    initialized = false;
}

float LowPassFilter::process(float newValue) {
    if (!initialized) {
        lastOutput = newValue;
        initialized = true;
    } else {
        lastOutput = alpha * newValue + (1.0f - alpha) * lastOutput;
    }
    return lastOutput;
}
