import os
import logging
import json

import azure.functions as func
from azure.cosmosdb.table.tableservice import TableService
from azure.cosmosdb.table.models import Entity

def main(event: func.EventHubEvent):
    logging.debug('Function triggered to process a message: %s', event)
    logging.debug('  body: %s', event.get_body())
    logging.debug('  EnqueuedTimeUtc: %s', event.enqueued_time)
    logging.debug('  SequenceNumber: %s', event.sequence_number)
    logging.debug('  Offset: %s', event.offset)
    logging.debug('  Partition: %s', event.partition_key)
    logging.debug('  Metadata: %s', event.iothub_metadata)

    table_service = TableService(connection_string=os.environ['AzureTableConnectionString'])

    for datapoint in json.loads(event.get_body()):
        if datapoint is not None and 'tap' in datapoint and 'timestamp' in datapoint:
            logging.debug('  datapoint: %s', (datapoint))
            # Expected data format:
            #   {'timestmap': 1564062672, 'tap': 'Tap 1', 'temperature': 1.0, 'weight': 7915}
            #
            # tap name is used as partition key.  Timestamp is used as RowKey
            # since it's unique, however since RowKey must be a string,
            # timestamp is duplicated as an int column to keep it searchable.
            # The rest of the datapoint elements are added as columns as well.
            entry = {}
            entry['PartitionKey'] = datapoint.pop('tap')
            entry['RowKey'] = str(datapoint['timestamp'])
            entry.update(datapoint.items())
            logging.debug('entry: %s' % (entry))
            table_service.insert_entity('ScaleDataTable', entry)
            logging.info('Added table entry: %s', (entry))
        else:
            logging.info('  Invalid datapoint: %s', (datapoint))
