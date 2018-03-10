# Configuration Data

#AWS IOT Thing Endpoint (Under AWS console IOT Thing: Interact)
ENDPOINT = "SOME_NAME.iot.REGION.amazonaws.com"

#AWS IOT thing name
THING = "NAME_OF_THING"

# Scale configurations
scaleConfigs = [
  # Scale 0 configuration
  {'name': 'LeftFridgeLeftTap',
   'data_gpio': 24,
   'clk_gpio': 23,
   'ref_unit': 24.675,
   'tare_offset' : 8671108 },

  # Scale 1 configuration
  {'name': 'LeftFridgeRightTap',
   'data_gpio': 5,
   'clk_gpio': 6,
   'ref_unit': 22.375,
   'tare_offset' : 9011438 }
  ]
