var AWS = require('aws-sdk');
var iot = new AWS.Iot();

// Could figure this out programaticly, but that takes time.
// Comes from 'aws iot describe-endpoint'
var ENDPOINT = "a3f9rjliro4kji.iot.us-west-2.amazonaws.com"

exports.handler = (event, context, callback) => {
  console.log('DZ: Received event:', event);
  var simpledb = new AWS.SimpleDB();
  var params = {
    Items: []
  };

  var group;
  var thing;
  var jobs = [];
  var scaledata = event['state']['reported']['taps'];
  for (var scale in scaledata){
    console.log('DZ: working on  entry:', scaledata[scale]);
    name = scaledata[scale].tap;
    group = scaledata[scale].group;
    params.Items.push(
     { Attributes: [
        {
          Name: 'timestamp',
          Value: scaledata[scale].timestamp.toString(),
        },
        {
          Name: 'name',
          Value: name
        },
        {
          Name: 'weight',
          Value: scaledata[scale].weight.toString(),
        },
      ],
      Name: name + ":" + scaledata[scale].timestamp.toString(),
     });
  }
  params.DomainName = group;
  
  console.log('DZ: pushing simpledb update job');
  jobs.push(simpledb.batchPutAttributes(params, function(err, data) {
    // For some reason, we hit this twice sometimes
    console.log('DZ:   simbledb callback');
    if (err) {
      console.log("DB Update Error: " + JSON.stringify(err));
    }
    else {
      console.log("DB update success: " + JSON.stringify(params));
    }
  }).promise());
  
  Promise.all(jobs).then(function() {
      console.log("All jobs done");
      context.succeed('data update success');
    }, function(err) {
      console.log("Problem somewhere: ", arguments);
      context.fail(err);
    });
};
