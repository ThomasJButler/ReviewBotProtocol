#!/bin/bash
# Azure Container Management Script
# Git Review Assistant - On-Demand Usage
#
# This script makes it easy to start/stop your Azure containers
# for on-demand usage (2 hours/day) = $0/month!
#
# Usage:
#   ./manage-azure-containers.sh [command]
#
# Commands:
#   status    - Check current status
#   start     - Start containers (for demos)
#   stop      - Stop containers (save credits)
#   restart   - Restart containers
#   logs      - View container logs
#   update    - Update to latest Docker image
#   costs     - Check current spending
#   info      - Show deployment information
#   help      - Show this help message

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Configuration
RESOURCE_GROUP="${AZURE_RESOURCE_GROUP:-git-review-free-rg}"
BACKEND_APP="${AZURE_BACKEND_APP:-git-review-backend}"

# Check Azure CLI
if ! command -v az &> /dev/null; then
    echo -e "${RED}❌ Azure CLI not found${NC}"
    exit 1
fi

# Check login
if ! az account show &> /dev/null 2>&1; then
    echo -e "${RED}❌ Not logged in to Azure. Run: az login${NC}"
    exit 1
fi

# Functions

show_help() {
    echo -e "${GREEN}╔══════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║      Azure Container Management - On-Demand          ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${BLUE}Usage:${NC} ./manage-azure-containers.sh [command]"
    echo ""
    echo -e "${BLUE}Commands:${NC}"
    echo "  status    - Check current container status"
    echo "  start     - Start containers (scale to 1 replica)"
    echo "  stop      - Stop containers (scale to 0 = FREE)"
    echo "  restart   - Restart containers"
    echo "  logs      - View live container logs"
    echo "  update    - Update to latest Docker image"
    echo "  costs     - Check current Azure spending"
    echo "  info      - Show deployment information"
    echo "  help      - Show this help message"
    echo ""
    echo -e "${YELLOW}💡 For On-Demand Usage (2 hrs/day = $0/month):${NC}"
    echo "   1. Run './manage-azure-containers.sh start' before demos"
    echo "   2. Use your app"
    echo "   3. Run './manage-azure-containers.sh stop' when done"
    echo ""
    echo -e "${GREEN}💰 Free Tier: 33 hours/month at 0.5 vCPU + 1GB RAM${NC}"
    echo ""
}

check_status() {
    echo -e "${YELLOW}📊 Checking container status...${NC}"
    echo ""

    # Get container app details
    STATUS=$(az containerapp show \
        --name $BACKEND_APP \
        --resource-group $RESOURCE_GROUP \
        --query "{name:name,status:properties.runningStatus,replicas:properties.template.scale.minReplicas,fqdn:properties.configuration.ingress.fqdn}" \
        --output json 2>/dev/null)

    if [ $? -ne 0 ]; then
        echo -e "${RED}❌ Container app not found${NC}"
        echo -e "${BLUE}   Resource Group: $RESOURCE_GROUP${NC}"
        echo -e "${BLUE}   Container App: $BACKEND_APP${NC}"
        exit 1
    fi

    NAME=$(echo $STATUS | jq -r '.name')
    RUN_STATUS=$(echo $STATUS | jq -r '.status')
    MIN_REPLICAS=$(echo $STATUS | jq -r '.replicas')
    FQDN=$(echo $STATUS | jq -r '.fqdn')

    echo -e "${CYAN}Container:${NC} $NAME"
    echo -e "${CYAN}Status:${NC}    $RUN_STATUS"
    echo -e "${CYAN}Replicas:${NC}  $MIN_REPLICAS"
    echo -e "${CYAN}URL:${NC}       https://$FQDN"
    echo ""

    # Get replica count
    REPLICA_COUNT=$(az containerapp replica list \
        --name $BACKEND_APP \
        --resource-group $RESOURCE_GROUP \
        --query "length(@)" \
        --output tsv 2>/dev/null || echo "0")

    echo -e "${CYAN}Active Replicas:${NC} $REPLICA_COUNT"
    echo ""

    if [ "$MIN_REPLICAS" == "0" ]; then
        echo -e "${GREEN}✅ Scale-to-zero enabled (FREE when idle)${NC}"
        if [ "$REPLICA_COUNT" == "0" ]; then
            echo -e "${GREEN}   Currently scaled to zero = $0 cost${NC}"
        else
            echo -e "${YELLOW}   Container running (will scale down when idle)${NC}"
        fi
    else
        echo -e "${YELLOW}⚠️  Always running ($MIN_REPLICAS replica)${NC}"
        echo -e "${YELLOW}   Tip: Run 'stop' command to enable scale-to-zero${NC}"
    fi

    echo ""

    # Test health endpoint
    echo -e "${YELLOW}🏥 Testing health endpoint...${NC}"
    HEALTH=$(curl -s -o /dev/null -w "%{http_code}" https://$FQDN/health --max-time 5)

    if [ "$HEALTH" == "200" ]; then
        echo -e "${GREEN}✅ Backend is healthy!${NC}"
    elif [ "$HEALTH" == "000" ]; then
        echo -e "${YELLOW}⚠️  Backend not responding (may be scaled to zero)${NC}"
        echo -e "${BLUE}   Run 'start' command to wake it up${NC}"
    else
        echo -e "${RED}❌ Health check failed (HTTP $HEALTH)${NC}"
    fi

    echo ""
}

start_containers() {
    echo -e "${YELLOW}🚀 Starting containers...${NC}"

    az containerapp update \
        --name $BACKEND_APP \
        --resource-group $RESOURCE_GROUP \
        --min-replicas 1 \
        --max-replicas 1 \
        --output none

    echo -e "${GREEN}✅ Container starting...${NC}"
    echo ""
    echo -e "${BLUE}Waiting for container to be ready (30 seconds)...${NC}"
    sleep 30

    FQDN=$(az containerapp show \
        --name $BACKEND_APP \
        --resource-group $RESOURCE_GROUP \
        --query properties.configuration.ingress.fqdn \
        --output tsv)

    # Test health
    HEALTH=$(curl -s -o /dev/null -w "%{http_code}" https://$FQDN/health --max-time 10)

    if [ "$HEALTH" == "200" ]; then
        echo -e "${GREEN}✅ Backend is ready!${NC}"
        echo ""
        echo -e "${CYAN}Backend URL:${NC} https://$FQDN"
        echo -e "${CYAN}Health Check:${NC} https://$FQDN/health"
        echo ""
        echo -e "${YELLOW}💡 Don't forget to stop containers when done:${NC}"
        echo "   ./manage-azure-containers.sh stop"
    else
        echo -e "${YELLOW}⚠️  Container may still be starting${NC}"
        echo -e "${BLUE}   Check status with: ./manage-azure-containers.sh status${NC}"
    fi

    echo ""
}

stop_containers() {
    echo -e "${YELLOW}🛑 Stopping containers (scale-to-zero)...${NC}"

    az containerapp update \
        --name $BACKEND_APP \
        --resource-group $RESOURCE_GROUP \
        --min-replicas 0 \
        --max-replicas 1 \
        --output none

    echo -e "${GREEN}✅ Container will scale to zero when idle${NC}"
    echo -e "${GREEN}   This saves credits = $0 cost when idle!${NC}"
    echo ""
    echo -e "${BLUE}Note:${NC} Container will auto-start for webhooks (<1 second)"
    echo ""
}

restart_containers() {
    echo -e "${YELLOW}🔄 Restarting containers...${NC}"

    # Get current revision
    REVISION=$(az containerapp revision list \
        --name $BACKEND_APP \
        --resource-group $RESOURCE_GROUP \
        --query "[0].name" \
        --output tsv)

    # Restart revision
    az containerapp revision restart \
        --name $BACKEND_APP \
        --resource-group $RESOURCE_GROUP \
        --revision $REVISION \
        --output none

    echo -e "${GREEN}✅ Container restarted${NC}"
    echo ""
}

view_logs() {
    echo -e "${YELLOW}📄 Streaming container logs...${NC}"
    echo -e "${BLUE}   Press Ctrl+C to exit${NC}"
    echo ""

    az containerapp logs show \
        --name $BACKEND_APP \
        --resource-group $RESOURCE_GROUP \
        --follow
}

update_image() {
    echo -e "${YELLOW}🔄 Updating to latest Docker image...${NC}"
    echo ""

    # Get current image
    CURRENT_IMAGE=$(az containerapp show \
        --name $BACKEND_APP \
        --resource-group $RESOURCE_GROUP \
        --query "properties.template.containers[0].image" \
        --output tsv)

    echo -e "${BLUE}Current image:${NC} $CURRENT_IMAGE"
    echo ""

    # Extract image name (remove tag)
    IMAGE_NAME="${CURRENT_IMAGE%:*}"

    echo -e "${YELLOW}Pulling latest image...${NC}"

    # Update container
    az containerapp update \
        --name $BACKEND_APP \
        --resource-group $RESOURCE_GROUP \
        --image $IMAGE_NAME:latest \
        --output none

    echo -e "${GREEN}✅ Container updated to latest image${NC}"
    echo ""
    echo -e "${BLUE}Tip:${NC} Check logs to verify update:"
    echo "   ./manage-azure-containers.sh logs"
    echo ""
}

check_costs() {
    echo -e "${YELLOW}💰 Checking Azure costs...${NC}"
    echo ""

    # Get costs for last 7 days
    START_DATE=$(date -d "7 days ago" +%Y-%m-%d 2>/dev/null || date -v-7d +%Y-%m-%d)
    END_DATE=$(date +%Y-%m-%d)

    echo -e "${BLUE}Cost usage (last 7 days):${NC}"
    echo ""

    az consumption usage list \
        --start-date $START_DATE \
        --end-date $END_DATE \
        --query "[?contains(instanceName,'git-review')].{Service:meterName,Quantity:quantity,Unit:unitOfMeasure}" \
        --output table 2>/dev/null || echo -e "${YELLOW}⚠️  Cost data not available yet (may take 24-48 hours)${NC}"

    echo ""
    echo -e "${BLUE}💡 Free Tier Status:${NC}"
    echo "   180,000 vCPU-seconds/month = 33 hours @ 0.5 vCPU + 1GB RAM"
    echo ""
    echo -e "${BLUE}📊 Full cost analysis:${NC}"
    echo "   https://portal.azure.com → Cost Management + Billing"
    echo ""
}

show_info() {
    echo -e "${GREEN}╔══════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║         Azure Deployment Information                 ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════════╝${NC}"
    echo ""

    # Get deployment details
    DETAILS=$(az containerapp show \
        --name $BACKEND_APP \
        --resource-group $RESOURCE_GROUP \
        --query "{fqdn:properties.configuration.ingress.fqdn,image:properties.template.containers[0].image,cpu:properties.template.containers[0].resources.cpu,memory:properties.template.containers[0].resources.memory,minReplicas:properties.template.scale.minReplicas,maxReplicas:properties.template.scale.maxReplicas}" \
        --output json 2>/dev/null)

    if [ $? -ne 0 ]; then
        echo -e "${RED}❌ Deployment not found${NC}"
        exit 1
    fi

    FQDN=$(echo $DETAILS | jq -r '.fqdn')
    IMAGE=$(echo $DETAILS | jq -r '.image')
    CPU=$(echo $DETAILS | jq -r '.cpu')
    MEMORY=$(echo $DETAILS | jq -r '.memory')
    MIN=$(echo $DETAILS | jq -r '.minReplicas')
    MAX=$(echo $DETAILS | jq -r '.maxReplicas')

    echo -e "${CYAN}Resource Group:${NC}    $RESOURCE_GROUP"
    echo -e "${CYAN}Container App:${NC}     $BACKEND_APP"
    echo -e "${CYAN}Region:${NC}            eastus"
    echo ""
    echo -e "${CYAN}Backend URL:${NC}       https://$FQDN"
    echo -e "${CYAN}Health Check:${NC}      https://$FQDN/health"
    echo -e "${CYAN}Webhook:${NC}           https://$FQDN/api/webhook/github"
    echo ""
    echo -e "${CYAN}Docker Image:${NC}      $IMAGE"
    echo -e "${CYAN}Resources:${NC}         $CPU CPU, $MEMORY Memory"
    echo -e "${CYAN}Scaling:${NC}           $MIN - $MAX replicas"
    echo ""

    if [ "$MIN" == "0" ]; then
        echo -e "${GREEN}✅ Scale-to-zero enabled (FREE when idle!)${NC}"
    else
        echo -e "${YELLOW}⚠️  Always running (using credits)${NC}"
    fi

    echo ""
    echo -e "${BLUE}Management Commands:${NC}"
    echo "  Status:   ./manage-azure-containers.sh status"
    echo "  Start:    ./manage-azure-containers.sh start"
    echo "  Stop:     ./manage-azure-containers.sh stop"
    echo "  Logs:     ./manage-azure-containers.sh logs"
    echo "  Update:   ./manage-azure-containers.sh update"
    echo "  Costs:    ./manage-azure-containers.sh costs"
    echo ""
    echo -e "${BLUE}Azure Portal:${NC}"
    echo "  https://portal.azure.com"
    echo ""
}

# Main script
case "${1:-help}" in
    status)
        check_status
        ;;
    start)
        start_containers
        ;;
    stop)
        stop_containers
        ;;
    restart)
        restart_containers
        ;;
    logs)
        view_logs
        ;;
    update)
        update_image
        ;;
    costs)
        check_costs
        ;;
    info)
        show_info
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        echo -e "${RED}❌ Unknown command: $1${NC}"
        echo ""
        show_help
        exit 1
        ;;
esac
