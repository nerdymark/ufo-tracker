#!/bin/bash

# UFO Tracker Services Restart Script
# This script ensures all UFO Tracker services are restarted in the correct order

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}✅${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠️${NC} $1"
}

print_error() {
    echo -e "${RED}❌${NC} $1"
}

print_info() {
    echo -e "${BLUE}ℹ️${NC} $1"
}

# Function to check if service exists
service_exists() {
    systemctl list-unit-files | grep -q "^$1\.service"
}

# Function to wait for service to stop
wait_for_service_stop() {
    local service=$1
    local max_wait=30
    local count=0
    
    while systemctl is-active --quiet "$service" 2>/dev/null; do
        if [ $count -ge $max_wait ]; then
            print_error "Timeout waiting for $service to stop"
            return 1
        fi
        sleep 1
        count=$((count + 1))
    done
    return 0
}

# Function to wait for service to start
wait_for_service_start() {
    local service=$1
    local max_wait=30
    local count=0
    
    while ! systemctl is-active --quiet "$service" 2>/dev/null; do
        if [ $count -ge $max_wait ]; then
            print_error "Timeout waiting for $service to start"
            return 1
        fi
        sleep 1
        count=$((count + 1))
    done
    return 0
}

echo "🛸 UFO Tracker Service Restart"
echo "=============================="

# Define services in dependency order
SERVICES=("ufo-tracker-camera" "ufo-tracker-frame" "ufo-tracker-api")

# Step 1: Stop all services in reverse order
print_info "Stopping UFO Tracker services..."

for service in "${SERVICES[@]}"; do
    if service_exists "$service"; then
        if systemctl is-active --quiet "$service" 2>/dev/null; then
            print_info "Stopping $service..."
            systemctl stop "$service"
            if wait_for_service_stop "$service"; then
                print_status "$service stopped"
            else
                print_error "Failed to stop $service"
                exit 1
            fi
        else
            print_warning "$service was not running"
        fi
    else
        print_warning "$service does not exist"
    fi
done

# Small delay to ensure clean shutdown
sleep 2

# Step 2: Start services in correct order
print_info "Starting UFO Tracker services..."

for service in "${SERVICES[@]}"; do
    if service_exists "$service"; then
        print_info "Starting $service..."
        systemctl start "$service"
        if wait_for_service_start "$service"; then
            print_status "$service started"
        else
            print_error "Failed to start $service"
            # Show the service status for debugging
            systemctl status "$service" --no-pager -l
            exit 1
        fi
        # Small delay between service starts
        sleep 2
    fi
done

# Step 3: Update main service state (skip if called from within ufo-tracker service)
if [ "${SYSTEMD_EXEC_PID}" != "$$" ] && service_exists "ufo-tracker"; then
    print_info "Updating main service state..."
    # Only update if we're not already running within the service
    if ! systemctl is-active --quiet "ufo-tracker"; then
        systemctl start ufo-tracker 2>/dev/null || true
        print_status "Main service updated"
    else
        print_info "Main service already active, skipping update"
    fi
else
    print_info "Skipping main service update (running within service context)"
fi

# Step 4: Verify all services are running
print_info "Verifying service status..."
all_good=true

for service in "${SERVICES[@]}"; do
    if service_exists "$service"; then
        if systemctl is-active --quiet "$service" 2>/dev/null; then
            print_status "$service is active"
        else
            print_error "$service is not active"
            all_good=false
        fi
    fi
done

if $all_good; then
    echo ""
    print_status "All UFO Tracker services restarted successfully!"
    echo ""
    print_info "Service status:"
    systemctl status "${SERVICES[@]}" --no-pager -l
else
    echo ""
    print_error "Some services failed to start properly"
    echo ""
    print_info "Current status:"
    systemctl status "${SERVICES[@]}" --no-pager -l
    exit 1
fi

echo ""
print_info "You can monitor logs with:"
echo "sudo journalctl -u ${SERVICES[0]} -u ${SERVICES[1]} -f"