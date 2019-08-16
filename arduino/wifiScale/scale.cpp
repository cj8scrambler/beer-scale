#include "common.h"
#include "scale.h"

//#define DEBUG                          1      // Enable verbose serial logging
#define ADC_VOLTAGE                    3.3
#define MAX_LINE_SIZE                   80

Scale::Scale(NAU7802 adc, int channel, int scalenum)
{
  /* hardware interface */
  _adc = adc;
  _chan = channel;

  /* configuration */
  _config = NULL;
  _scalenum = scalenum;

  /* state */
  _weight_change = false;

  /* results */
  _weight_g = 0;

}

void Scale::begin(scaleConfig *config)
{
  /* pointer into the EEPROM backed config/state data */
  _config = config;

#ifndef SIMULATED
  _adc.begin(SDA, SCL, NAU7802_I2CADDR);
  _adc.extAvcc(ADC_VOLTAGE);
  _adc.rate010sps();
#endif

  if (_config->enabled && (_config->slope == 0.0))
  {
    Serial.printf("\r\nForcing recalibration on scale-%d (invalid slope)\r\n", _scalenum); 
    calibrate(REFERENCE_CAL_WEIGHT_GRAMS);
  }

#ifdef DEBUG
  Serial.printf("Create scale-%d %s (%0.2f / %d)\r\n", _scalenum,
                 _config->enabled?"enabled":"disabled",
                 _config->slope, _config->offset);
#endif
}

int32_t Scale::datapoint()
{
  int32_t median;
#ifdef SIMULATED
  /* convert the last sampel back to A/D value then randomize */
  median = (_config->last_weight * _config->slope) + _config->offset;
  median += random(-400,400);
#else
  MedianFilter<int32_t>* samples = 
      new MedianFilter<int32_t>(MEDIAN_FILTER_SIZE);

  for (int i = 0; i < MEDIAN_FILTER_SIZE; i++)
  {
    int32_t val = _read_adc();
    median = samples->AddValue(val);
#ifdef DEBUG
    Serial.printf("  datapoint: raw: %ld  new median: %ld\r\n", val, median);
#endif
  }
#endif

  /* Convert ADC reading to grams */
  if ( _config->slope != 0.0)
  {
    _weight_g = (int32_t)(((median - _config->offset) / _config->slope) + 0.5);
  }
  else
  {
    Serial.printf("Error: scale-%d has slope 0.0\r\n", _scalenum);
  }

  /* Check for a signifigant weight change */
  if (abs(_weight_g - _config->last_weight) > ALLOWED_VARIANCE_GRAMS)
  {
#ifdef DEBUG
    Serial.println(F(" Weight change state"));
#endif
    _weight_change = true;
    _config->updates = 0;
  }

  if (_config->updates++ > WEIGHT_CHANGE_REPORTS)
  {
#ifdef DEBUG
    Serial.println(F(" Idle state"));
#endif
    _weight_change = false;
  }

#ifdef DEBUG
  Serial.printf("Scale-%d  weight: %.1fkg  median: %d  delta: %d/%d  "
                "weight_change: %d  updates: %d\r\n", _scalenum,
                _weight_g/1000.0, median, abs(_weight_g - _config->last_weight),
                ALLOWED_VARIANCE_GRAMS, _weight_change, _config->updates);
#endif
  _config->last_weight = _weight_g;
}

bool Scale::enabled()
{
  return _config->enabled;
}

int32_t Scale::weight()
{
  return _weight_g;
}

uint8_t Scale::scaleNum()
{
  return _scalenum;
}

void Scale::tare()
{
  calibrate(0);
}

/* Passing 0 for reference_grams causes a tare instead of calibrate */
void Scale::calibrate(uint16_t reference_grams)
{
  int i;
  int32_t before, after;
  char buff[MAX_LINE_SIZE];

  MedianFilter<int32_t> *tare_samples = NULL;

  tare_samples = new MedianFilter<int32_t>(CALIBRATION_MEDIAN_FILTER_SIZE);
 
  if (reference_grams)
  {
    Serial.printf("Calibrate scale-%d\r\r", _scalenum);
  } else {
    Serial.printf("Tare scale-%d\r\r", _scalenum);
  }

  /******** Get an empty baseline *************/
  readFromSerial("  Press enter when scale is empty: ", buff, MAX_LINE_SIZE, 0, false);

  Serial.print("  Reading basline");
  for (i = 0; i < 2 * CALIBRATION_MEDIAN_FILTER_SIZE; i++ )
  {
#ifdef SIMULATED
    before = (random(0,50) - 25);
#else
    int32_t val = _read_adc();
    before = tare_samples->AddValue(val);
#ifdef DEBUG
    Serial.printf("  A/D: %ld  newmean: %ld\r\n", val, before);
#endif
#endif
    delay(ADC_READ_DELAY);
    Serial.print(F("."));
  }
  Serial.println(F(""));

  if (reference_grams)
  {
    /******** Get a reference reading *************/
    snprintf(buff, MAX_LINE_SIZE,
             "  Press enter when %0.1fkg weight is on scale: ",
             reference_grams / 1000.0);
    readFromSerial(buff, buff, MAX_LINE_SIZE, 0, false);

    Serial.print("  Reading reference");
    for (i = 0; i < 2 * CALIBRATION_MEDIAN_FILTER_SIZE; i++ )
    {
#ifdef SIMULATED
      after = (random(reference_grams,reference_grams+500) - 250);
#else
      int32_t val = _read_adc();
      after = tare_samples->AddValue(val);
#ifdef DEBUG
      Serial.printf("  A/D: %ld  newmean: %ld\r\n", val, after);
#endif
#endif
      delay(ADC_READ_DELAY);
      Serial.print(F("."));
    }
    Serial.println(F(""));

    /******** Save calculated slope ************/
    _config->slope = (after - before) / (float) reference_grams;
    if (_config->slope == 0.0)
    {
      Serial.printf("  Error: invalid slope; disabling scale\r\n");
      _config->enabled = 0;
    }
    else
    {
#ifdef DEBUG
      Serial.printf("  Before: %d  After: %d\r\n", before, after);
#endif
      Serial.printf("  Slope: %.2f\r\n", _config->slope);
    }
  }
  _config->offset = before;
  _config->last_weight = 0;  /* clear history on recalibrate */

  delete tare_samples;

  Serial.print(F("  Tare Offset: "));
  Serial.println(_config->offset);
}

float Scale::slope(void)
{
  return _config->slope;
}

int32_t Scale::offset(void)
{
  return _config->offset;
}

bool Scale::recentWeightChange(void)
{
  return _weight_change;
}

int32_t Scale::_read_adc(void)
{
  int i;

  switch(_chan)
  {
    case 0:
      _adc.selectCh1();
      break;
    case 1:
      _adc.selectCh2();
      break;
    default:
      Serial.print(F("Unsupported channel: "));
      Serial.println(_chan);
      return 0;
      break;
  }

  for (i = 0; i < DUMMY_ADC_READS; i++)
  {  
     _adc.readADC();
  }

  return _adc.readADC();
}
