import logging
import boto3
import json

logger = logging.getLogger()
logger.setLevel(logging.INFO)
client = boto3.client('iot')

def lambda_handler(event, context):
    result = {}
    result['results'] = []

    logger.debug('got event{}'.format(event))

    # Get group parameter from path input
    if 'group' in event['pathParameters']:
        group = event['pathParameters']['group']
    else:
        raise Exception('group not defined')

    logger.debug('got group: %s' % group)

    # Loop over things in group
    grouplist = client.list_things_in_thing_group(
        thingGroupName=group, recursive=True,)
    for thing in grouplist['things']:
        logger.debug("Working on thing: %s" % thing)
        dataclient = boto3.client('iot-data')
        thingdata = dataclient.get_thing_shadow(thingName=thing)
        body = thingdata["payload"]
        thingState = json.loads(body.read())
        # If there is data, then loop over taps in thing
        if 'reported' in thingState['state']:
            for tapdata in thingState['state']['reported']['taps']:
                data = {}
                logger.debug("got tapdata: %s" % tapdata)
                logger.info("Updating tap: %s" % tapdata['tap'])
                data['tap'] = tapdata['tap']
                data['weight'] = tapdata['weight']
                data['timestamp'] = tapdata['timestamp']

                result['results'].append(data)
    response = {}
    response["statusCode"] = 200
    response["headers"] = {}
    response["headers"]["Access-Control-Allow-Origin"] = "http://beer-status.s3-website-us-west-2.amazonaws.com"
    response["body"] = result
    response["isBase64Encoded"] = False

    return (response)
