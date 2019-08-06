import os
import logging
import json

import azure.functions as func
from applicationinsights.logging import LoggingHandler
from applicationinsights import TelemetryClient
from azure.cosmosdb.table.tableservice import TableService
from azure.cosmosdb.table.models import Entity

TABLE_NAME_HISTORICAL_DATA = os.environ['HistoricalDataTableName']
TABLE_NAME_CONFIGURATION = os.environ['ConfigurationTableName']

def main(event: func.EventHubEvent):
    handler = LoggingHandler(os.environ['APPINSIGHTS_INSTRUMENTATIONKEY'])
    logging.basicConfig(handlers=[ handler ], format='%(levelname)s: %(message)s', level=logging.DEBUG)

    tc = TelemetryClient(os.environ['APPINSIGHTS_INSTRUMENTATIONKEY'])
    tc.track_event("Incoming event")
    tc.flush()

    logging.info('Function triggered to process a message: %s', event)
    logging.info('  body: %s', event.get_body())
    logging.info('  EnqueuedTimeUtc: %s', event.enqueued_time)
    logging.info('  SequenceNumber: %s', event.sequence_number)
    logging.info('  Offset: %s', event.offset)
    logging.info('  Partition: %s', event.partition_key)
    logging.info('  Metadata: %s', event.iothub_metadata)

    table_service = TableService(connection_string=os.environ['AzureTableConnectionString'])

    for datapoint in json.loads(event.get_body()):
        # Expected data format:
        #   {"timestamp": 1564598054, "deviceid": "Node1", "scale": 2, "temperature": 1.1,"weight": 10000}
        if datapoint is not None and 'deviceid' in datapoint and \
           'timestamp' in datapoint and 'scale' in datapoint and \
           'weight' in datapoint:
            logging.debug('  datapoint: %s', (datapoint))
            # deviceid is used as partition key.
            # {timestamp}-{scale} is used as RowKey
            # timestamp and scale number are duplicated as an int columns
            # to keep them searchable.  The rest of the datapoint elements
            # are added as columns as well.
            history = {}
            history['PartitionKey'] = datapoint.pop('deviceid')
            history['RowKey'] = str(datapoint['timestamp']) + '-' + str(datapoint['scale'])
            history.update(datapoint.items())
            logging.debug('history: %s' % (history))
            table_service.insert_entity(TABLE_NAME_HISTORICAL_DATA, history)
            logging.info('Added historical table data: %s', (history))

            # Touch/create the row in the config table for each reported scale with latest weight
            configupdate = {}
            configupdate['PartitionKey'] = history['PartitionKey']
            configupdate['RowKey'] = str(history['scale'])
            configupdate['weight'] = history['weight']
            if 'temperature' in history:
                configupdate['temperature'] = history['temperature']
            logging.info('config update: %s' % (configupdate))
            logging.info('Writing to table: %s' % (TABLE_NAME_CONFIGURATION))
            table_service.insert_or_merge_entity(TABLE_NAME_CONFIGURATION, configupdate)
            logging.info('Updated configuration table entry: %s', (configupdate))
        else:
            logging.info('  Invalid datapoint: %s', (datapoint))
