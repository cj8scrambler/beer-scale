#ifndef COMMON_H
#define COMMON_H

#include <Arduino.h>

/* enables global debug (can also be enabled per file) */
//#define DEBUG

/* hardware configuration */
//#define SIMULATED                      1      // Set to simulate I2C mux & ADC hardware

#define NUM_ADC                        1      // # of NAU7802 ADCs (1 implies no I2C MUX)
#define NUM_CHAN_PER_ADC               2
#define NUM_SCALES                     (NUM_ADC*NUM_CHAN_PER_ADC)
#define I2C_MUX_ADDR                   0x70   // 7-bit address of I2C Mux
#define CONFIG_SW_GPIO                 14     // Causes device to go into config mode when held low at reset
#define AVDD_EN_GPIO                   15     // Enable line for AVDD

/* buffer sizes */
#define SSID_LEN                       32
#define PASS_LEN                       32
#define CONNECTION_STRING_LEN          256
#define DEVICEID_MAX_LEN               32
#define MEDIAN_FILTER_SIZE             9      // # of ADC readings taken & fed through median filter
#define MESSAGE_MAX_LEN                256

/* Sleep between scale readings */
//#define WEIGHT_CHANGE_REPORTS          3      // consectutive short samples without variance which cause change to long sleep times
//#define SHORT_SLEEP_TIME_S             10     // when a signifigant weight change has happened recently
//#define LONG_SLEEP_TIME_S              30     // normal sleep time
#define WEIGHT_CHANGE_REPORTS          8      // consectutive short samples without variance which cause change to long sleep times
#define SHORT_SLEEP_TIME_S             30     // when a signifigant weight change has happened recently
#define LONG_SLEEP_TIME_S              300    // normal sleep time

typedef struct scale_config {
  bool enabled;
  int32_t offset;
  float slope;
  uint32_t updates;
  int32_t last_weight;
} scaleConfig;

typedef struct config {
  char ssid[SSID_LEN];
  char pass[PASS_LEN];
  char connection[CONNECTION_STRING_LEN];
  char deviceid[DEVICEID_MAX_LEN];
  scaleConfig scaledata[NUM_SCALES];
} systemConfig;

extern systemConfig *g_config;        // global configuration pointer

/* Common function prototypes provided by utils.ino */
void setmux(int position);
void hang(const char *message);
bool readFromSerial(char * prompt, char * buf, int maxLen, int timeout, bool hide);

#endif
