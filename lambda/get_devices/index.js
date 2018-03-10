var AWS = require('aws-sdk');
var iot = new AWS.Iot();

exports.handler = (event, context, callback) => {
  //console.log('DZ: Received event:', event);
  
  const group = event.pathParameters.group;
  if (group == undefined) {
    context.fail("Invalid path: missing group");
  }
  
  var params = {
    thingGroupName: group,
    maxResults: 32,
    recursive: true
  };
  
  iot.listThingsInThingGroup(params, function(err, groupData) {
    if (err) context.fail(err);
    else {
      //console.log('DZ: Received group list::', groupData);
      iot.describeEndpoint({}, function(err, endpointData) {
        if (err) context.fail(err);
        else {
          console.log('DZ: endpoint data:', endpointData);
          groupData.things.forEach(function(item, index, array) {
            console.log('DZ: on thing:', item)
            var iotdata = new AWS.IotData({endpoint: endpointData.endpointAddress});
            iotdata.getThingShadow({thingName: item}, function(err, shadowData) {
              if (err) {
                context.fail(err);
              } else {
                console.log('DZ:', item, "has:", shadowData)
                var list = []
                var jsonPayload = JSON.parse(shadowData.payload);
                if (jsonPayload.state.reported != undefined) {
                  for (var i in jsonPayload.state.reported.scales) {
                    console.log('DZ: thing:', item, '  scale:', i, ' weight:', jsonPayload.state.reported.scales[i]);
                    var entry = {};
                    entry['tap'] = jsonPayload.state.reported.scales[i].scale;
                    entry['weight'] = jsonPayload.state.reported.scales[i].weight;
                    console.log("DZ: entry is:", entry)
                    list.push(entry);
                  }
                }

                var response = {
                  "statusCode": 200,
                  "headers": {
                  },
                  "body": JSON.stringify(list),
                  "isBase64Encoded": false
                };
                context.succeed(response);
              }
            });
          });
        }
      });
    }
  });
};
