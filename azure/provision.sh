#!/bin/bash

# Script to provision the following resources on Azure for scale readings:
#   Resource Group (-g flag)
#     IOT Hub (-i flag)
#       # of IOT Devices (-n flag; default 2)
#     Event Hubs Namespace
#       Event Hub
#     Storage Account (-s flag)
#       Storage Table
#     Route all messages from IOT Hub to Event Hub
#     Function App (-a & -L flags)
#       Configure Event Hub & Storage Table connection strings
#       Install scaleDataIngest as Function app

# For each named resource the following priorities will be used:
#   use name supplied on command line if it already exists in azure
#   use the default name (below) if it already exists in azure
#   use first resource (of same type) found in the resource group
#   create new resource with the name supplied on command line
#   create new resource with default name

RANDO=$(head /dev/urandom | tr -dc a-z0-9 | head -c 10 ; echo '')

# Defaults that can be overriden on command line:
  GROUP=scale
  LOCATION=northcentralus
  NUM_NODES=2
  IOTH_NAME="ScaleIotHub-${RANDO}"
  STORAGE_ACCT_NAME="scalestorage${RANDO}"
  FUNC_APP_NAME="ScaleMoveData${RANDO}"
  FUNC_APP_LOC="westus"

# Defaults that are hardcoded
  OUTPUT=table

  # IOT Hub
  IOTH_SKU="F1"   # Free iothub is limited to 8000 messages/day

  # Event Hub
  EH_NAMESPACE="ScaleEvents${RANDO}"
  EH_NAMESPACE_SKU="Basic"
  EH_NAME="scaleeventhub"
  EH_AUTH_POLICY="${EH_NAME}_send_policy"

  # App
  FUNC_APP_OS_TYPE="linux"
  FUNC_APP_RUNTIME="python"
  FUNC_APP_LOCAL_DIRECTORY="scaleDataIngest"

  # Storage
  STORAGE_SKU="Standard_LRS"
  STORAGE_KIND="StorageV2"
  TABLE_NAME="ScaleDataTable"

  # Message Route
  ROUTE_NAME="Ioth2EhRoute"
  IOTH_EH_ENDPOINT_NAME="EvHubEndpoint"

function usage(){
  cat << EOM
Usage: $(basename $0) [-g resource-group-name] [-i iot-hub-name] [-l location] [-n # iot devices] [ -s storage acct name] [-a function app name] [-L function app location]
  -g Creates (or uses existing) resource group   [default: scale]
     Warns before creating if it doesn't already exist
  -i Creates (or uses existing) iothub name      [default: ScaleIotHub-{randomstring}]
     Must be globally unique across all of Azure
  -l Location to provision resources             [default: ${LOCATION}]
     See available locations with: az account list-locations
  -n # IOT devices (rPis) to provision           [default: ${NUM_NODES}]
  -s Storage account name                        [default: scalestorage{randomstring}]]
     Must be globally unique across all of Azure and all lower case
  -a Function app name                           [default: ScaleMoveData{randomstring}]]
     Must be globally unique across all of Azure
  -L Function app location                       [default: ${FUNC_APP_LOC}]
     Linux function consumption only available in: [westus|eastus|westeurope|eastasia]
     https://github.com/Azure/Azure-Functions/wiki/Azure-Functions-on-Linux-Preview
EOM
}

while getopts ":hg:i:l:n:s:a:L:" opt; do
  case ${opt} in
    a ) # function app name
      FUNC_APP_NAME=${OPTARG}
      ;;
    g ) # resource group name
      GROUP=${OPTARG}
      ;;
    i ) # iot hub name
      IOTH_NAME=${OPTARG}
      ;;
    l ) # location
      LOCATION=${OPTARG}
      ;;
    L ) # app location
      FUNC_APP_LOC=${OPTARG}
      ;;
    n ) # number of iot devices
      NUM_NODES=${OPTARG}
      ;;
    s ) # storage account name
      STORAGE_ACCT_NAME=${OPTARG}
      ;;
    h|\? ) # help
      usage
      exit 0
      ;;
  esac
done

COMMON_ARGS="-l ${LOCATION} -g ${GROUP} --output ${OUTPUT}"

# Make sure az command is available and authenticated
az group list > /dev/null 2>&1
if [[ $? -ne 0 ]]
then
  echo "Error: Make sure azure cli is installed and authenticated"
  echo "https://docs.microsoft.com/en-us/cli/azure/install-azure-cli-apt"
  exit -1
fi

# Make sure iot extension is installed
az extension show --name azure-cli-iot-ext > /dev/null 2>&1
if [[ $? -ne 0 ]]
then
  echo "Error: azure cli iot extension is needed.  Install with:"
  echo "       az extension add --name azure-cli-iot-ext"
  exit -1
fi

# Verify the resource group
if [[ $(az group exists --name ${GROUP}) != true ]] 
then
  echo -n "Resource group '${GROUP}' doesn't exist.  Create it (n/Y)? "
  read RESP
  if [[ ${RESP} == "" || ${RESP} == "y" || ${RESP} == "Y" ]]
  then
    echo "az group create ${COMMON_ARGS}"
    az group create ${COMMON_ARGS}
    if [[ $? -ne 0 ]]
    then
      exit -1
    fi
    echo ""
  else
    exit 0
  fi
else
  echo "Using existing resource group: ${GROUP}"
fi

# Verify / provision the IOThub
az iot hub show -g ${GROUP} --output none --name ${IOTH_NAME} > /dev/null 2>&1
if [[ $? -ne 0 ]]
then
  VALUE=$(az iot hub list -g ${GROUP} --output json --query "[0].name" 2>/dev/null | tr -d '"')
  if [[ $? -eq 0 && ! -z ${VALUE} ]]
  then
    IOTH_NAME=${VALUE}
    echo "Using existing IOT hub: ${IOTH_NAME}"
  else
    echo "az iot hub create ${COMMON_ARGS} --name ${IOTH_NAME} --sku ${IOTH_SKU}"
    az iot hub create ${COMMON_ARGS} --name ${IOTH_NAME} --sku ${IOTH_SKU}
    if [[ $? -ne 0 ]]
    then
      exit -1
    fi
    echo ""
  fi
else
  echo "Using existing IOT hub: ${IOTH_NAME}"
fi

# Verify / provision the iot devices (represents a raspberry pi)
NODE=1
while [[ ${NODE} -le ${NUM_NODES} ]]
do
  az iot hub device-identity show -g ${GROUP} -n ${IOTH_NAME} -d "Node${NODE}" > /dev/null 2>&1
  if [[ $? -ne 0 ]]
  then
    echo "az iot hub device-identity create --device-id Node${NODE} " \
         "--hub-name ${IOTH_NAME} --am shared_private_key --output ${OUTPUT}"
    az iot hub device-identity create --device-id Node${NODE} \
      --hub-name ${IOTH_NAME} --am shared_private_key --output ${OUTPUT}
    if [[ $? -ne 0 ]]
    then
      exit -1
    fi
    echo ""
  else
    echo "Using existing IOT device: Node${NODE}"
  fi
  CONSTRING=$(az iot hub device-identity show-connection-string --hub-name ${IOTH_NAME} --device Node${NODE} --query "connectionString" | tr -d '"')
  echo "#########################################################################################"
  echo "# Node${NODE} Connection String.  Add to raspberrypi/scale.py or azure/emulator/scale.py:"
  echo "# \"${CONSTRING}"\"
  echo "#########################################################################################"

  NODE=$((${NODE}+1))
done

# Verify / provision Event Hub Namespace
az eventhubs namespace show -g ${GROUP} -n ${EH_NAMESPACE} > /dev/null 2>&1
if [[ $? -ne 0 ]]
then
  VALUE=$(az eventhubs namespace list -g ${GROUP} --output json --query "[0].name" 2>/dev/null | tr -d '"')
  if [[ $? -eq 0 && ! -z ${VALUE} ]]
  then
    EH_NAMESPACE=${VALUE}
    echo "Using existing event hub namespace: ${EH_NAMESPACE}"
  else
    echo "az eventhubs namespace create ${COMMON_ARGS} --name ${EH_NAMESPACE} --sku ${EH_NAMESPACE_SKU}"
    az eventhubs namespace create ${COMMON_ARGS} --name ${EH_NAMESPACE} --sku ${EH_NAMESPACE_SKU}
    if [[ $? -ne 0 ]]
    then
      exit -1
    fi
    echo ""
  fi
else
  echo "Using existing event hub namespace: ${EH_NAMESPACE}"
fi
EH_NAMESPACE_CONSTRING=$(az eventhubs namespace authorization-rule keys list -g ${GROUP} --namespace-name ${EH_NAMESPACE} --name RootManageSharedAccessKey --output json --query "primaryConnectionString" 2>/dev/null | tr -d '"')
if [[ $? -ne 0 ]]
then
  exit -1
fi

# Verify / provision Event Hub 
az eventhubs eventhub show -g ${GROUP} --namespace-name ${EH_NAMESPACE} -n ${EH_NAME} > /dev/null 2>&1
if [[ $? -ne 0 ]]
then
  VALUE=$(az eventhubs eventhub list -g ${GROUP} --output json --query "[0].name" 2>/dev/null | tr -d '"')
  if [[ $? -eq 0 && ! -z ${VALUE} ]]
  then
    EH_NAME=${VALUE}
    echo "Using existing event hub name: ${EH_NAME}"
  else
    echo "az eventhubs eventhub create -g ${GROUP} --output ${OUTPUT} --namespace-name ${EH_NAMESPACE} --name ${EH_NAME} --message-retention 1"
    az eventhubs eventhub create -g ${GROUP} --output ${OUTPUT} --namespace-name ${EH_NAMESPACE} --name ${EH_NAME} --message-retention 1
    if [[ $? -ne 0 ]]
    then
      exit -1
    fi
    echo ""
  fi
else
  echo "Using existing event hub: ${EH_NAME}"
fi

# Get eventhub namespace connection string
EH_CONNECT=$(az eventhubs namespace authorization-rule keys list -g ${GROUP} --namespace-name ${EH_NAMESPACE} --name RootManageSharedAccessKey --output json --query "primaryConnectionString" 2>/dev/null | tr -d '"')
if [[ $? -ne 0 ]]
then
  echo "Error: couldn't get eventhub namespace connection string with:"
  echo "    az eventhubs namespace authorization-rule keys list -g ${GROUP} --namespace-name ${EH_NAMESPACE} --name RootManageSharedAccessKey --output json --query \"primaryConnectionString\" 2>/dev/null | tr -d '\"'"
  exit -1
fi

# Verify / provision storage account
az storage account show -g ${GROUP} -n ${STORAGE_ACCT_NAME} > /dev/null 2>&1
if [[ $? -ne 0 ]]
then
  VALUE=$(az storage account list -g ${GROUP} --output json --query "[0].name" 2>/dev/null | tr -d '"')
  if [[ $? -eq 0 && ! -z ${VALUE} ]]
  then
    STORAGE_ACCT_NAME=${VALUE}
    echo "Using existing storage account: ${STORAGE_ACCT_NAME}"
  else
    echo "az storage account account create ${COMMON_ARGS} --name ${STORAGE_ACCT_NAME} --sku ${STORAGE_SKU} --kind ${STORAGE_KIND}"
    az storage account create ${COMMON_ARGS} --name ${STORAGE_ACCT_NAME} --sku ${STORAGE_SKU} --kind ${STORAGE_KIND}
    if [[ $? -ne 0 ]]
    then
      exit -1
    fi
    echo ""
  fi
else
  echo "Using existing storage account: ${STORAGE_ACCT_NAME}"
fi

# Get storage account key
STORAGE_ACCT_KEY=$(az storage account keys list -g ${GROUP} --account-name ${STORAGE_ACCT_NAME} --output json --query "[0].value" | tr -d '"')
if [[ $? -ne 0 ]]
then
  echo "Error: couldn't get storage key with:"
  echo "    az storage account keys list -g ${GROUP} --account-name ${STORAGE_ACCT_NAME} --output json --query \"[0].value\" | tr -d '\"'\""
  exit -1
fi

# Verify / provision storage table
if [[ $(az storage table exists --account-name ${STORAGE_ACCT_NAME} -n ${TABLE_NAME} --output tsv) != True ]]
then
  VALUE=$(az storage table list --account-name ${STORAGE_ACCT_NAME} --output json --query "[0].name" 2>/dev/null | tr -d '"')
  if [[ $? -eq 0 && ! -z ${VALUE} ]]
  then
    TABLE_NAME=${VALUE}
    echo "Using existing table name: ${TABLE_NAME}"
  else
    echo "az storage table create --account-name ${STORAGE_ACCT_NAME} -n ${TABLE_NAME} --output ${OUTPUT}"
    az storage table create --account-name ${STORAGE_ACCT_NAME} -n ${TABLE_NAME} --output ${OUTPUT}
    if [[ $? -ne 0 ]]
    then
      exit -1
    fi
    echo ""
  fi
else
  echo "Using existing storage table: ${TABLE_NAME}"
fi

## Verify / provision event hub endpoint in iothub
az iot hub routing-endpoint show --hub-name ${IOTH_NAME} --endpoint-name ${IOTH_EH_ENDPOINT_NAME} >/dev/null 2>&1
if [[ $? -ne 0 ]]
then
  VALUE=$(az iot hub routing-endpoint list --hub-name ${IOTH_NAME} --output json --query "eventHubs[0].name" 2>/dev/null | tr -d '"')
  if [[ $? -eq 0 && ! -z ${VALUE} ]]
  then
    IOTH_EH_ENDPOINT_NAME=${VALUE}
    echo "Using existing event hub endpoint: ${IOTH_EH_ENDPOINT_NAME}"
  else
    # Have to append EntityPath to connection string per
    # https://github.com/Azure/azure-event-hubs-spark/blob/master/docs/structured-streaming-eventhubs-integration.md#azure-portal
    echo "az iot hub routing-endpoint create --hub-name ${IOTH_NAME} --endpoint-name ${IOTH_EH_ENDPOINT_NAME} --endpoint-type eventhub --endpoint-resource-group ${GROUP} --connection-string \"${EH_CONNECT};EntityPath=${EH_NAME}\" --endpoint-subscription-id 1 --output ${OUTPUT}"
    az iot hub routing-endpoint create --hub-name ${IOTH_NAME} --endpoint-name ${IOTH_EH_ENDPOINT_NAME} \
        --endpoint-type eventhub --endpoint-resource-group ${GROUP}  \
        --connection-string "${EH_CONNECT};EntityPath=${EH_NAME}" \
        --endpoint-subscription-id 1 --output ${OUTPUT}
    if [[ $? -ne 0 ]]
    then
      exit -1
    fi
    echo ""
  fi
else
  echo "Using existing event hub endpoint: ${IOTH_EH_ENDPOINT_NAME}"
fi

# Verify / provision message route (IOTHub->Event Hub)
az iot hub route show -g ${GROUP} --hub-name ${IOTH_NAME} --route-name ${ROUTE_NAME} >/dev/null 2>&1
if [[ $? -ne 0 ]]
then
  VALUE=$(az iot hub route list -g ${GROUP} --hub-name ${IOTH_NAME} --output json --query "[0].name" 2>/dev/null | tr -d '"')
  if [[ $? -eq 0 && ! -z ${VALUE} ]]
  then
    ROUTE_NAME=${VALUE}
    echo "Using existing route name: ${ROUTE_NAME}"
  else
    echo "az iot hub route create -g ${GROUP} --hub-name ${IOTH_NAME} --route-name ${ROUTE_NAME} --source-type devicemessages --endpoint-name ${IOTH_EH_ENDPOINT_NAME=} --output ${OUTPUT}"
    az iot hub route create -g ${GROUP} --hub-name ${IOTH_NAME} --route-name ${ROUTE_NAME} --source-type devicemessages --endpoint-name ${IOTH_EH_ENDPOINT_NAME=} --output ${OUTPUT}
    if [[ $? -ne 0 ]]
    then
      exit -1
    fi
    echo ""
  fi
else
  echo "Using existing message route: ${ROUTE_NAME}"
fi

# Verify / provision function app
az functionapp show -g ${GROUP} --name ${FUNC_APP_NAME}  > /dev/null 2>&1
if [[ $? -ne 0 ]]
then
  VALUE=$(az functionapp list -g ${GROUP} --output json --query "[0].name" 2>/dev/null | tr -d '"')
  if [[ $? -eq 0 && ! -z ${VALUE} ]]
  then
    FUNC_APP_NAME=${VALUE}
    echo "Using existing function app name: ${FUNC_APP_NAME}"
  else
    echo "az functionapp create --resource-group ${GROUP} --output ${OUTPUT} --name ${FUNC_APP_NAME} "\
        "--storage-account ${STORAGE_ACCT_NAME} --consumption-plan-location ${FUNC_APP_LOC} "   \
        "--os-type ${FUNC_APP_OS_TYPE}  --runtime ${FUNC_APP_RUNTIME} "
    az functionapp create --resource-group ${GROUP} --output ${OUTPUT} --name ${FUNC_APP_NAME} \
        --storage-account ${STORAGE_ACCT_NAME} --consumption-plan-location ${FUNC_APP_LOC}    \
        --os-type ${FUNC_APP_OS_TYPE}  --runtime ${FUNC_APP_RUNTIME} > /dev/null
    if [[ $? -ne 0 ]]
    then
      exit -1
    fi
    echo ""
  fi
else
  echo "Using existing function app name: ${FUNC_APP_NAME}"
fi

# Configure connections strings in App Settings
echo "Update function app table connection string"
#echo "az functionapp config appsettings set --resource-group ${GROUP} --name ${FUNC_APP_NAME} --settings \"AzureTableConnectionString=DefaultEndpointsProtocol=https;AccountName=${STORAGE_ACCT_NAME};AccountKey=${STORAGE_ACCT_KEY};EndpointSuffix=core.windows.net\""
az functionapp config appsettings set --resource-group ${GROUP} --name ${FUNC_APP_NAME} --settings "AzureTableConnectionString=DefaultEndpointsProtocol=https;AccountName=${STORAGE_ACCT_NAME};AccountKey=${STORAGE_ACCT_KEY};EndpointSuffix=core.windows.net" > /dev/null
if [[ $? -ne 0 ]]
then
  exit -1
fi

echo "Update function app eventhub connection string"
#echo "az functionapp config appsettings set --resource-group ${GROUP} --name ${FUNC_APP_NAME} --settings \"EventHubConnectString=${EH_NAMESPACE_CONSTRING}\""
az functionapp config appsettings set --resource-group ${GROUP} --name ${FUNC_APP_NAME} --settings "EventHubConnectString=${EH_NAMESPACE_CONSTRING}" > /dev/null
if [[ $? -ne 0 ]]
then
  exit -1
fi

func > /dev/null 2>&1
if [[ $? -ne 0 ]]
then
  echo "Cannot install function app without azure 'func' utility.  Can be installed with"
  echo ""
  echo "curl https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor > microsoft.gpg"
  echo "sudo mv microsoft.gpg /etc/apt/trusted.gpg.d/microsoft.gpg"
  echo "sudo sh -c 'echo "deb [arch=amd64] https://packages.microsoft.com/repos/microsoft-ubuntu-$(lsb_release -cs)-prod $(lsb_release -cs) main" > /etc/apt/sources.list.d/dotnetdev.list'"
  echo "sudo apt-get update"
  echo "sudo apt-get install azure-functions-core-tools dotnet-sdk-2.1"
else
  if [[ -f ${FUNC_APP_LOCAL_DIRECTORY}/host.json ]]
  then
    cd ${FUNC_APP_LOCAL_DIRECTORY}/
  fi
  if [[ ! -f host.json ]]
  then
    echo "Can't find ${FUNC_APP_LOCAL_DIRECTORY} function app.  Run provision script from function app directory or parent"
    exit -1
  fi

  echo "Start function app"
  az functionapp start --resource-group ${GROUP} --name ${FUNC_APP_NAME} > /dev/null 
  if [[ $? -ne 0 ]]
  then
    exit -1
  fi

  echo "Publish function app"
  func azure functionapp publish ${FUNC_APP_NAME} --build-native-deps > /dev/null
  if [[ $? -ne 0 ]]
  then
    exit -1
  fi

  echo "Pull application settings to local.settings.json"
  func azure functionapp fetch-app-settings ${FUNC_APP_NAME} > /dev/null

  echo "Function app published.  To run locally stop server instance and start local:"
  echo "  az functionapp stop --resource-group ${GROUP} --name ${FUNC_APP_NAME}"
  echo "  func host start"

fi
