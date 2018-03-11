# Configuration Data

#AWS IOT Thing Endpoint (Under AWS console IOT Thing: Interact)
ENDPOINT = "a3f9rjliro4kji.iot.us-west-2.amazonaws.com"

#AWS IOT group name that the thing is a member of
GROUP = "FultonKitchen"

#AWS IOT thing name
THING = "weight_pi"

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
   'ref_unit': 24.675,
   'tare_offset' : 8671108 }
]
