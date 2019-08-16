#ifndef Scale_h
#define Scale_h

#include "NAU7802.h"

/* MedianFilterLib from:
 *   https://github.com/luisllamasbinaburo/Arduino-MedianFilter
 * is the fastest median filter I could find.  I have copied it
 * here instead of using the system library because the published
 * version includes a mis-capitalized 'arduino.h' which breaks
 * the build on case sensitive filesystems
 */
#include "MedianFilterLib.h"

#define CALIBRATION_MEDIAN_FILTER_SIZE 20   // Number of samples durring calibration
#define REFERENCE_CAL_WEIGHT_GRAMS     4000 // Reference weight used in calibration

#define ALLOWED_VARIANCE_GRAMS         250  // variance which triggers a change to quick update mode

#define DUMMY_ADC_READS                  0  // Number of ADC reads to drop
#define ADC_READ_DELAY                 100  // delay(ms) between consecutive ADC reads (calibration)

class Scale
{
  public:
    Scale(NAU7802 adc, int channel, int scalenum);
    void begin(scaleConfig *config);
    void calibrate(uint16_t reference_grams);   /* run calibration with any reference weight */
    void tare();                /* tare scale (set offset) */
    int32_t datapoint();        /* collect a datapoint from scale */
    bool recentWeightChange(void);

    bool enabled();             /* get enabled/disabled state */
    int32_t weight();           /* get the last calculated data in grams */
    uint8_t scaleNum();         /* get scale number [0 - NUM_SCALES-1] */

    float slope();              /* report calibrated slope (only valid if != 0) */
    int32_t offset();           /* report calibrated offset (only valid if slope != 0) */

  private:

    /* hardware interface */
    NAU7802 _adc;
    uint8_t _chan;
    int32_t _read_adc();        /* talks to NAU780x device to get raw scale reading */

    /* peristant data */
    scaleConfig * _config;
    uint8_t _scalenum;

    /* state */
    bool _weight_change;

    /* results */
    int32_t _weight_g;
};
#endif
