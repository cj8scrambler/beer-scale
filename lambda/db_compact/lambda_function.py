import logging
import boto3
import json
import time

SECS_PER_DAY = 86400

logger = logging.getLogger()
logger.setLevel(logging.INFO)
sdb = boto3.client('sdb') 

# Hardcoded to operate on testdata.
# Eventually should itterate over all groups/taps
group = 'TestData'
tap = 'LeftFridgeLeftTap'

def timestamp_days_ago(days):
    return (int(time.time() - SECS_PER_DAY * float(days)))

def lambda_handler(event, context):
    day = 2       # Start with day '2' (keep all data < 2 days old)
    day_updates = 1;  # Get into the while loop below
    total = 0;    # Total records compacted
    
    # Grab all data older than 'day' that has never been compacted (i.e. no 'age' set)
    query = "select * from `" + group + "` where `timestamp` < '"
    query = query + str(timestamp_days_ago(day)) + "' and `name` = '" + tap + "'" 
    query = query + "and `age` is null order by `timestamp` ASC limit 2"

    while True:
        data = []
        logger.info("DZ: Running query:" + query)
        # Here's a really in-effecient way to grab the 2 oldest data points in the query
        sdbData = sdb.select(SelectExpression=query, ConsistentRead=True)
        if 'Items' in sdbData:
            for element in sdbData['Items']:
                point={}
                point['itemName'] = element['Name']
                for key in element['Attributes']:
                    point[key['Name']] = key['Value']
                    #logger.info("  %s = %s" % (key['Name'], key['Value']))
                data.append(point)
                total = total + 1
                day_updates = day_updates + 1
                if len(data) == 2:
                    break;
        elif day_updates == 0:
            # If this is the first query of the 'day' range and we got nothing, then
            # we're all done
            break;

        # If 2 old datapoints were found, then replace them with the average of those 2
        if len(data) == 2:
            avg = {}
            avg['name'] = data[0]['name']  # Name is the same
            avg['timestamp'] = int((int(data[0]['timestamp']) + int(data[1]['timestamp'])) / 2)
            avg['weight'] = (float(data[0]['weight']) + float(data[1]['weight'])) / 2
            avg['itemName'] = data[0]['name'] + ":" + str(avg['timestamp'])  # Generate new itemName
           
            # delete the 2 old data points
            for item in data:
                att = []
                att.append({'Name': 'name', 'Value': item['name']})
                att.append({'Name': 'weight', 'Value': item['weight']})
                att.append({'Name': 'timestamp', 'Value': item['timestamp']})
                if 'age' in item:
                    att.append({'Name': 'age', 'Value': item['age']})
                #logger.info("DZ: Delete:")    
                #logger.info(att) 
                response = sdb.delete_attributes(DomainName=group, 
                                                 ItemName=item['itemName'],
                                                 Attributes=att)
            # insert the newly calculated average along with recorded 'age'
            att = []
            att.append({'Name': 'name', 'Value': avg['name'], 'Replace': True})
            att.append({'Name': 'weight', 'Value': str(avg['weight']), 'Replace': True})
            att.append({'Name': 'timestamp', 'Value': str(avg['timestamp']), 'Replace': True})
            att.append({'Name': 'age', 'Value': str(day), 'Replace': True})
            
            #logger.info("DZ: Insert:")    
            #logger.info(att) 
            response = sdb.put_attributes(DomainName=group, 
                                          ItemName=avg['itemName'],
                                          Attributes=att)
        else:
            # If less than 2 old datapoints available, then double the 'day' and repeat
            logger.info("DZ: day %d done: total=%d" % (day, total))
            query = "select * from `" + group + "` where `age` = '" + str(day) +"' "
            day = day * 2
            query = query + "and `timestamp` < '" + str(timestamp_days_ago(day)) + "' "
            query = query + "and `name` = '" + tap + "' order by `timestamp` ASC limit 2"
            day_updates = 0

    response = {}
    response["statusCode"] = 200
    response["headers"] = {}
    response["headers"]["Access-Control-Allow-Origin"] = "http://beer-status.s3-website-us-west-2.amazonaws.com"
    response["body"] = {'total': total, 'days': int(day/2)}
    response["isBase64Encoded"] = False

    return (response)
