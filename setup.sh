#!/bin/bash

# UFO Tracker Setup Script for Raspberry Pi
# This script helps set up the UFO Tracker system

set -e  # Exit on error

echo "🛸 UFO Tracker Setup Script"
echo "=========================="

# Color codes for output
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

# Function to check if running as root
check_not_root() {
    if [ "$EUID" -eq 0 ]; then
        print_error "Please do not run this script as root (don't use sudo)"
        echo "The script will prompt for sudo when needed"
        exit 1
    fi
}

# Function to check Raspberry Pi
check_raspberry_pi() {
    if ! grep -q "Raspberry Pi" /proc/cpuinfo 2>/dev/null; then
        print_warning "This doesn't appear to be a Raspberry Pi"
        echo "Some features may not work correctly."
        read -p "Continue anyway? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
}

# Function to check Python version
check_python() {
    if ! command -v python3 &> /dev/null; then
        print_error "Python 3 is required but not installed"
        echo "Please install Python 3 and try again"
        exit 1
    fi

    print_status "Python 3 found: $(python3 --version)"

    # Check Python version (need 3.7+)
    if ! python3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 7) else 1)" 2>/dev/null; then
        python_version=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
        print_error "Python 3.7 or higher is required. Found: $python_version"
        exit 1
    fi
}

# Function to install system packages
install_system_packages() {
    print_info "Updating system packages..."
    if ! sudo apt update; then
        print_warning "Failed to update package lists, continuing anyway..."
    fi

    print_info "Installing system dependencies..."
    
    # Essential packages
    local essential_packages=(
        "python3-pip"
        "python3-venv" 
        "python3-dev"
        "build-essential"
        "git"
    )
    
    # OpenCV dependencies
    local opencv_packages=(
        "libjpeg-dev"
        "libtiff5-dev"
        "libpng-dev"
        "libavcodec-dev"
        "libavformat-dev"
        "libswscale-dev"
        "libv4l-dev"
        "libgtk-3-dev"
        "libatlas-base-dev"
        "gfortran"
    )
    
    # Install essential packages first
    sudo apt install -y "${essential_packages[@]}"
    
    # Install OpenCV dependencies (continue if some fail)
    sudo apt install -y "${opencv_packages[@]}" || print_warning "Some OpenCV dependencies failed to install"
    
    # Install Raspberry Pi specific packages if available
    if command -v raspi-config &> /dev/null; then
        print_info "Installing Raspberry Pi camera packages..."
        sudo apt install -y python3-picamera2 libcamera-apps libcamera-dev || print_warning "Some camera packages failed to install"
        
        # Enable camera interface
        print_info "Enabling camera interface..."
        sudo raspi-config nonint do_camera 0
        print_status "Camera interface enabled"
    else
        print_warning "raspi-config not found, skipping camera-specific setup"
    fi
}

# Function to create virtual environment
create_venv() {
    print_info "Creating Python virtual environment..."
    if [ ! -d "venv" ]; then
        if python3 -m venv venv; then
            print_status "Virtual environment created"
        else
            print_error "Failed to create virtual environment"
            exit 1
        fi
    else
        print_status "Virtual environment already exists"
    fi
}

# Function to install Python packages
install_python_packages() {
    print_info "Installing Python dependencies..."
    
    # Activate virtual environment
    source venv/bin/activate || {
        print_error "Failed to activate virtual environment"
        exit 1
    }

    # Upgrade pip
    print_info "Upgrading pip..."
    pip install --upgrade pip

    print_info "Installing packages from requirements.txt..."
    if pip install -r requirements.txt; then
        print_status "All requirements installed successfully"
    else
        print_warning "Some packages failed to install, trying individual installation..."
        
        # Install packages individually
        local packages=(
            "Flask==2.3.3"
            "numpy>=1.21.0"
            "Pillow>=9.0.0" 
            "imutils>=0.5.4"
            "psutil>=5.9.0"
        )
        
        for package in "${packages[@]}"; do
            print_info "Installing $package..."
            if ! pip install "$package"; then
                print_warning "Failed to install $package, trying without version constraint..."
                package_name=$(echo "$package" | cut -d'=' -f1 | cut -d'>' -f1)
                pip install "$package_name" || print_error "Failed to install $package_name"
            fi
        done

        # Install OpenCV with fallback options
        print_info "Installing OpenCV..."
        if command -v raspi-config &> /dev/null; then
            # On Raspberry Pi, try different approaches
            if ! pip install opencv-python-headless; then
                print_warning "opencv-python-headless failed, trying opencv-python..."
                if ! pip install opencv-python; then
                    print_warning "pip opencv install failed, using system package..."
                    sudo apt install -y python3-opencv || print_error "All OpenCV installation methods failed"
                fi
            fi
        else
            # On other systems
            pip install opencv-python || {
                print_warning "opencv-python failed, trying headless version..."
                pip install opencv-python-headless || print_error "OpenCV installation failed"
            }
        fi
    fi

    print_status "Python dependencies installation completed"
}

# Function to setup configuration
setup_config() {
    print_info "Setting up configuration..."
    if [ ! -f "config/config.py" ]; then
        cp config/config.example.py config/config.py
        print_status "Configuration file created"
    else
        print_status "Configuration file already exists"
    fi
}

# Function to create directories
create_directories() {
    print_info "Creating directories..."
    mkdir -p detections logs
    print_status "Directories created"
}

# Function to setup permissions
setup_permissions() {
    if command -v raspi-config &> /dev/null; then
        print_info "Setting up camera permissions..."
        if ! groups "$USER" | grep -q video; then
            sudo usermod -a -G video "$USER"
            print_warning "Added user to video group. Please logout and login again for camera access."
        else
            print_status "User already in video group"
        fi
    fi
}

# Function to create systemd services
create_services() {
    echo ""
    read -p "📋 Create systemd services for auto-start? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        print_info "Creating systemd services..."
        
        # Create camera service
        print_info "Creating camera service..."
        sudo tee /etc/systemd/system/ufo-tracker-camera.service > /dev/null <<EOF
[Unit]
Description=UFO Tracker - Camera Streaming Service
After=network.target
Wants=network.target

[Service]
Type=simple
User=$USER
Group=$USER
WorkingDirectory=$(pwd)
Environment=PYTHONPATH=$(pwd)
ExecStart=$(pwd)/venv/bin/python $(pwd)/camera_service.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

# Resource limits
MemoryMax=512M
CPUQuota=50%

# Camera access
SupplementaryGroups=video

[Install]
WantedBy=multi-user.target
EOF
        
        # Create frame service
        print_info "Creating frame service..."
        sudo tee /etc/systemd/system/ufo-tracker-frame.service > /dev/null <<EOF
[Unit]
Description=UFO Tracker - Frame Service (Port 5002)
After=network.target ufo-tracker-camera.service
Wants=network.target
Requires=ufo-tracker-camera.service

[Service]
Type=simple
User=$USER
Group=$USER
WorkingDirectory=$(pwd)
Environment=PYTHONPATH=$(pwd)
ExecStart=$(pwd)/venv/bin/python $(pwd)/frame_service.py
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

# Resource limits (lighter than camera service)
MemoryMax=128M
CPUQuota=15%

[Install]
WantedBy=multi-user.target
EOF
        
        # Create API service
        print_info "Creating API service..."
        sudo tee /etc/systemd/system/ufo-tracker-api.service > /dev/null <<EOF
[Unit]
Description=UFO Tracker - API Service
After=network.target
Wants=network.target

[Service]
Type=simple
User=$USER
Group=$USER
WorkingDirectory=$(pwd)
Environment=PYTHONPATH=$(pwd)
ExecStart=$(pwd)/venv/bin/python $(pwd)/api_service.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

# Resource limits
MemoryMax=256M
CPUQuota=25%

[Install]
WantedBy=multi-user.target
EOF
        
        # Create main orchestrator service
        print_info "Creating main orchestrator service..."
        sudo tee /etc/systemd/system/ufo-tracker.service > /dev/null <<EOF
[Unit]
Description=UFO Tracker - Main Application
After=network.target
Wants=ufo-tracker-camera.service ufo-tracker-frame.service ufo-tracker-api.service

[Service]
Type=oneshot
User=root
WorkingDirectory=$(pwd)
ExecStart=$(pwd)/restart-ufo-services.sh
ExecReload=$(pwd)/restart-ufo-services.sh
ExecStop=/bin/systemctl stop ufo-tracker-camera.service ufo-tracker-frame.service ufo-tracker-api.service
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF
        
        # Reload systemd and enable services
        print_info "Enabling all services..."
        sudo systemctl daemon-reload
        sudo systemctl enable ufo-tracker-camera.service
        sudo systemctl enable ufo-tracker-frame.service
        sudo systemctl enable ufo-tracker-api.service
        sudo systemctl enable ufo-tracker.service
        
        print_status "All systemd services created and enabled"
        echo ""
        echo "Service Architecture:"
        echo "   ufo-tracker-camera.service  - Camera streaming (port 5001)"
        echo "   ufo-tracker-frame.service   - Frame service (port 5002)"
        echo "   ufo-tracker-api.service     - API service (port 5000)"
        echo "   ufo-tracker.service         - Main orchestrator"
        echo ""
        echo "Usage:"
        echo "   Start all: sudo systemctl start ufo-tracker"
        echo "   Check status: sudo systemctl status ufo-tracker-camera ufo-tracker-frame ufo-tracker-api"
        echo "   View logs: sudo journalctl -u ufo-tracker-camera -u ufo-tracker-frame -u ufo-tracker-api -f"
    fi
}

# Function to print final instructions
print_final_instructions() {
    echo ""
    echo "🎉 Setup Complete!"
    echo "=================="
    echo ""
    echo "Next steps:"
    echo "1. Activate the virtual environment: source venv/bin/activate"
    echo "2. Review configuration: nano config/config.py"
    echo "3. Connect your cameras to the Raspberry Pi"
    echo "4. Run the application: ./run.sh"
    echo "5. Open http://$(hostname -I | awk '{print $1}'):5000 in a web browser"
    echo ""
    echo "Service Architecture:"
    echo "- Camera Service (port 5001): Live MJPEG streams"
    echo "- Frame Service (port 5002): Individual frame capture"
    echo "- API Service (port 5000): Main dashboard and controls"
    echo ""
    echo "Important notes:"
    echo "- Make sure both cameras are properly connected"
    echo "- Camera auto-detection will assign the higher resolution camera as HQ"
    echo "- Camera auto-detection will assign the lower resolution camera as IR"
    echo "- Pan-tilt mechanism is in placeholder mode"
    if groups "$USER" | grep -q video; then
        echo "- Camera permissions are set up"
    else
        echo "- You may need to logout/login for camera permissions"
    fi
    echo ""
    echo "For troubleshooting:"
    echo "- Check logs in the logs/ directory"
    echo "- Test with: python3 -c 'import cv2; print(cv2.__version__)'"
    echo "- Verify cameras: ls /dev/video*"
    echo ""
    echo "Happy UFO hunting! 🛸"
}

# Main execution
main() {
    check_not_root
    check_raspberry_pi
    check_python
    install_system_packages
    create_venv
    install_python_packages
    setup_config
    create_directories
    setup_permissions
    create_services
    print_final_instructions
}

# Run main function
main "$@"
