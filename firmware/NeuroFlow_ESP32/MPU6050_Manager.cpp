#include "MPU6050_Manager.h"

MPU6050_Manager::MPU6050_Manager() 
    : magBuffer(ACTIVITY_WINDOW_SIZE), baseGravityMag(9.81f), currentActivity(ACTIVITY_DIAM) {}

bool MPU6050_Manager::begin(TwoWire* wire) {
    if (!mpu.begin(0x68, wire)) {
        return false;
    }
    
    // MPU6050 Base Config
    mpu.setAccelerometerRange(MPU6050_RANGE_8_G);
    mpu.setGyroRange(MPU6050_RANGE_500_DEG);
    mpu.setFilterBandwidth(MPU6050_BAND_21_HZ); 

    // MPU6050 Motion Interrupt Config for Wakeup
    mpu.setHighPassFilter(MPU6050_HIGHPASS_0_63_HZ);
    mpu.setMotionDetectionThreshold(5); 
    mpu.setMotionDetectionDuration(20); 
    mpu.setInterruptPinLatch(true);     
    mpu.setInterruptPinPolarity(false);  
    mpu.setMotionInterrupt(true);
    
    return true;
}

void MPU6050_Manager::calibrate() {
    float sumMag = 0;
    int sampleCount = 0;
    unsigned long startCalib = millis();
    
    while (millis() - startCalib < CALIBRATION_MS) {
        float mag = getAccelMagnitude();
        sumMag += mag;
        sampleCount++;
        delay(20);
    }
    baseGravityMag = sumMag / sampleCount;
}

void MPU6050_Manager::prepareForDeepSleep() {
    mpu.getMotionInterruptStatus(); // Clear old interrupt status
}

float MPU6050_Manager::getAccelMagnitude() {
    sensors_event_t a, g, temp;
    mpu.getEvent(&a, &g, &temp);
    float ax = a.acceleration.x / 9.81f;
    float ay = a.acceleration.y / 9.81f;
    float az = a.acceleration.z / 9.81f;
    return sqrt(ax*ax + ay*ay + az*az);
}

void MPU6050_Manager::update(float magnitude) {
    magBuffer.process(magnitude);
    
    float std = magBuffer.getStandardDeviation();
    if (std > STD_THRESHOLD_LARI) currentActivity = ACTIVITY_LARI;
    else if (std > STD_THRESHOLD_JALAN) currentActivity = ACTIVITY_JALAN;
    else currentActivity = ACTIVITY_DIAM;
}

float MPU6050_Manager::getTremorIntensity() const {
    return magBuffer.getStandardDeviation();
}

ActivityLevel MPU6050_Manager::getActivityLevel() const {
    return currentActivity;
}

const char* MPU6050_Manager::getActivityLabel() const {
    switch (currentActivity) {
        case ACTIVITY_DIAM:  return "STATIONARY";
        case ACTIVITY_JALAN: return "WALKING";
        case ACTIVITY_LARI:  return "RUNNING";
        default:             return "STATIONARY";
    }
}
