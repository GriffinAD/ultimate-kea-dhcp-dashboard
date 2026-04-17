#!/bin/bash
###############################################################################
# Ultimate Kea DHCP Dashboard - Installation Script
# Author: NeySlim
# Description: Interactive installer with professional UI
###############################################################################

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# Installation paths
INSTALL_DIR="/opt/ukd"
CONFIG_DIR="/etc/ultimate-kea-dashboard"
SYSTEMD_DIR="/etc/systemd/system"

# Print colored header
print_header() {
    clear
    echo -e "${MAGENTA}${BOLD}"
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║                                                              ║"
    echo "║         Ultimate Kea DHCP Dashboard - Installer             ║"
    echo "║                                                              ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

# Print section header
print_section() {
    echo -e "\n${CYAN}${BOLD}▶ $1${NC}\n"
}

# Print success message
print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

# Print error message
print_error() {
    echo -e "${RED}✗${NC} $1"
}

# Print warning message
print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

# Print info message
print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

# Check if running as root
check_root() {
    if [[ $EUID -ne 0 ]]; then
        print_error "This script must be run as root"
        echo "Please run: sudo $0"
        exit 1
    fi
}

# Detect Linux distribution
detect_distro() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        DISTRO=$ID
        DISTRO_VERSION=$VERSION_ID
        DISTRO_NAME=$NAME
    elif [ -f /etc/redhat-release ]; then
        DISTRO="rhel"
        DISTRO_NAME="Red Hat Enterprise Linux"
    elif [ -f /etc/debian_version ]; then
        DISTRO="debian"
        DISTRO_NAME="Debian"
    else
        DISTRO="unknown"
        DISTRO_NAME="Unknown"
    fi
    
    # Determine package manager
    case "$DISTRO" in
        debian|ubuntu|linuxmint|pop)
            PKG_MANAGER="apt"
            PKG_UPDATE="apt-get update -qq"
            PKG_INSTALL="apt-get install -y -qq"
            ;;
        fedora)
            PKG_MANAGER="dnf"
            PKG_UPDATE="dnf check-update -q || true"
            PKG_INSTALL="dnf install -y -q"
            ;;
        centos|rhel|rocky|almalinux)
            if command -v dnf &> /dev/null; then
                PKG_MANAGER="dnf"
                PKG_UPDATE="dnf check-update -q || true"
                PKG_INSTALL="dnf install -y -q"
            else
                PKG_MANAGER="yum"
                PKG_UPDATE="yum check-update -q || true"
                PKG_INSTALL="yum install -y -q"
            fi
            ;;
        arch|manjaro|endeavouros)
            PKG_MANAGER="pacman"
            PKG_UPDATE="pacman -Sy --noconfirm"
            PKG_INSTALL="pacman -S --noconfirm --needed"
            ;;
        opensuse*|sles)
            PKG_MANAGER="zypper"
            PKG_UPDATE="zypper refresh -q"
            PKG_INSTALL="zypper install -y"
            ;;
        *)
            PKG_MANAGER="unknown"
            ;;
    esac
}

# Check system requirements
check_requirements() {
    print_section "Checking System Requirements"
    
    # Detect distribution
    detect_distro
    
    if [[ "$PKG_MANAGER" == "unknown" ]]; then
        print_error "Unsupported Linux distribution: $DISTRO_NAME"
        print_info "Supported distributions: Debian, Ubuntu, Fedora, CentOS, RHEL, Rocky, AlmaLinux, Arch, Manjaro, openSUSE"
        exit 1
    fi
    
    print_success "$DISTRO_NAME detected (using $PKG_MANAGER)"
    
    # Check Python version
    if command -v python3 &> /dev/null; then
        PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
        print_success "Python 3 found (version $PYTHON_VERSION)"
    else
        print_error "Python 3 not found"
        exit 1
    fi
}

# Install dependencies
install_dependencies() {
    print_section "Installing Dependencies"
    
    print_info "Updating package lists..."
    eval $PKG_UPDATE >/dev/null 2>&1 || true
    
    print_info "Installing required packages..."
    
    case "$PKG_MANAGER" in
        apt)
            eval $PKG_INSTALL nmap arping python3 python3-pip net-tools python3-psutil curl jq git >/dev/null 2>&1
            # Optional packages for enhanced features
            print_info "Installing optional packages (SNMP, mDNS)..."
            eval $PKG_INSTALL snmp avahi-utils >/dev/null 2>&1 || print_warning "Optional packages (snmp, avahi-utils) not installed - some features may be limited"
            ;;
        dnf|yum)
            # EPEL required for some packages on RHEL/CentOS
            if [[ "$DISTRO" == "centos" ]] || [[ "$DISTRO" == "rhel" ]] || [[ "$DISTRO" == "rocky" ]] || [[ "$DISTRO" == "almalinux" ]]; then
                eval $PKG_INSTALL epel-release >/dev/null 2>&1 || true
            fi
            eval $PKG_INSTALL nmap iputils python3 python3-pip net-tools python3-psutil curl jq git >/dev/null 2>&1
            # Optional packages
            print_info "Installing optional packages (SNMP, mDNS)..."
            eval $PKG_INSTALL net-snmp-utils avahi-tools >/dev/null 2>&1 || print_warning "Optional packages (net-snmp-utils, avahi-tools) not installed - some features may be limited"
            ;;
        pacman)
            eval $PKG_INSTALL nmap iputils python python-pip net-tools python-psutil curl jq git >/dev/null 2>&1
            # Optional packages
            print_info "Installing optional packages (SNMP, mDNS)..."
            eval $PKG_INSTALL net-snmp avahi >/dev/null 2>&1 || print_warning "Optional packages (net-snmp, avahi) not installed - some features may be limited"
            ;;
        zypper)
            eval $PKG_INSTALL nmap iputils python3 python3-pip net-tools python3-psutil curl jq git >/dev/null 2>&1
            # Optional packages
            print_info "Installing optional packages (SNMP, mDNS)..."
            eval $PKG_INSTALL net-snmp avahi-utils >/dev/null 2>&1 || print_warning "Optional packages (net-snmp, avahi-utils) not installed - some features may be limited"
            ;;
    esac
    
    print_success "Dependencies installed"
}

# Get default SSL paths based on distribution
get_default_ssl_paths() {
    case "$PKG_MANAGER" in
        apt)
            DEFAULT_SSL_CERT="/etc/ssl/certs/ssl-cert-snakeoil.pem"
            DEFAULT_SSL_KEY="/etc/ssl/private/ssl-cert-snakeoil.key"
            ;;
        dnf|yum)
            DEFAULT_SSL_CERT="/etc/pki/tls/certs/localhost.crt"
            DEFAULT_SSL_KEY="/etc/pki/tls/private/localhost.key"
            ;;
        pacman)
            DEFAULT_SSL_CERT="/etc/ssl/certs/ssl-cert-snakeoil.pem"
            DEFAULT_SSL_KEY="/etc/ssl/private/ssl-cert-snakeoil.key"
            ;;
        zypper)
            DEFAULT_SSL_CERT="/etc/ssl/certs/ssl-cert-snakeoil.pem"
            DEFAULT_SSL_KEY="/etc/ssl/private/ssl-cert-snakeoil.key"
            ;;
        *)
            DEFAULT_SSL_CERT="/etc/ssl/certs/ssl-cert-snakeoil.pem"
            DEFAULT_SSL_KEY="/etc/ssl/private/ssl-cert-snakeoil.key"
            ;;
    esac
}

# Prompt for configuration
configure_dashboard() {
    print_section "Dashboard Configuration"
    
    echo -e "${BOLD}Please provide the following configuration:${NC}\n"
    
    # Port
    read -p "$(echo -e ${CYAN}"Dashboard port [8089]: "${NC})" PORT
    PORT=${PORT:-8089}
    
    # Get default SSL paths for this distribution
    get_default_ssl_paths
    
    # SSL
    read -p "$(echo -e ${CYAN}"Enable SSL/TLS? (Y/n): "${NC})" -n 1 SSL_ENABLED
    echo
    SSL_ENABLED=${SSL_ENABLED:-Y}
    if [[ $SSL_ENABLED =~ ^[Yy]$ ]]; then
        USE_SSL="true"
        read -p "$(echo -e ${CYAN}"SSL certificate path [$DEFAULT_SSL_CERT]: "${NC})" SSL_CERT
        SSL_CERT=${SSL_CERT:-$DEFAULT_SSL_CERT}
        
        read -p "$(echo -e ${CYAN}"SSL key path [$DEFAULT_SSL_KEY]: "${NC})" SSL_KEY
        SSL_KEY=${SSL_KEY:-$DEFAULT_SSL_KEY}
    else
        USE_SSL="false"
        SSL_CERT="$DEFAULT_SSL_CERT"
        SSL_KEY="$DEFAULT_SSL_KEY"
    fi
    
    # Kea configuration
    read -p "$(echo -e ${CYAN}"Kea control socket path [/run/kea/kea4-ctrl-socket]: "${NC})" KEA_SOCKET
    KEA_SOCKET=${KEA_SOCKET:-/run/kea/kea4-ctrl-socket}
    
    read -p "$(echo -e ${CYAN}"Kea leases path [/var/lib/kea/kea-leases4.csv]: "${NC})" KEA_LEASES
    KEA_LEASES=${KEA_LEASES:-/var/lib/kea/kea-leases4.csv}
    
    # Network configuration
    read -p "$(echo -e ${CYAN}"Bind address [all interfaces]: "${NC})" BIND_ADDRESS
    BIND_ADDRESS=${BIND_ADDRESS:-}
    
    # Scanner configuration
    read -p "$(echo -e ${CYAN}"Enable network scanner? (Y/n): "${NC})" -n 1 SCANNER_ENABLED
    echo
    SCANNER_ENABLED=${SCANNER_ENABLED:-Y}
    if [[ $SCANNER_ENABLED =~ ^[Nn]$ ]]; then
        ENABLE_SCANNER="false"
    else
        ENABLE_SCANNER="true"
    fi
    
    # SNMP configuration
    read -p "$(echo -e ${CYAN}"Enable SNMP enrichment? (y/N): "${NC})" -n 1 SNMP_ENABLED
    echo
    SNMP_ENABLED=${SNMP_ENABLED:-N}
    if [[ $SNMP_ENABLED =~ ^[Yy]$ ]]; then
        ENABLE_SNMP="true"
        read -p "$(echo -e ${CYAN}"SNMP communities [public]: "${NC})" SNMP_COMMUNITIES
        SNMP_COMMUNITIES=${SNMP_COMMUNITIES:-public}
    else
        ENABLE_SNMP="false"
        SNMP_COMMUNITIES="public"
    fi
    
    # Language
    echo -e "\n${BOLD}Select language:${NC}"
    echo "1) Français"
    echo "2) English"
    read -p "$(echo -e ${CYAN}"Choice [1]: "${NC})" LANG_CHOICE
    LANG_CHOICE=${LANG_CHOICE:-1}
    
    if [[ $LANG_CHOICE == "2" ]]; then
        LANGUAGE="en"
    else
        LANGUAGE="fr"
    fi
}

# Install files
install_files() {
    print_section "Installing Files"
    
    # Create directories
    print_info "Creating directories..."
    mkdir -p "$INSTALL_DIR"/{bin,core,server,ui,assets,plugins,data,logs,etc}
    mkdir -p "$CONFIG_DIR"

    # Copy files
    print_info "Copying application files..."
    cp -r bin/* "$INSTALL_DIR/bin/"
    cp -r core/* "$INSTALL_DIR/core/"
    cp -r server/* "$INSTALL_DIR/server/"
    cp -r ui/* "$INSTALL_DIR/ui/"
    if [[ -d assets ]]; then
        cp -r assets/* "$INSTALL_DIR/assets/"
    fi
    if [[ -d plugins ]]; then
        cp -r plugins/* "$INSTALL_DIR/plugins/"
    fi
    cp -r data/* "$INSTALL_DIR/data/"
    cp start.sh "$INSTALL_DIR/"

    chmod +x "$INSTALL_DIR/bin/ultimate-kea-dashboard"
    if [[ -f "$INSTALL_DIR/bin/ultimate-kea-dashboard-plugin" ]]; then
        chmod +x "$INSTALL_DIR/bin/ultimate-kea-dashboard-plugin"
    fi
    chmod +x "$INSTALL_DIR/start.sh"
    
    print_success "Files installed to $INSTALL_DIR"
}

# Create configuration file
create_config() {
    print_section "Creating Configuration"
    
    cat > "$CONFIG_DIR/ultimate-kea-dashboard.conf" <<EOF
[DEFAULT]
# Dashboard server configuration
port = $PORT
use_ssl = $USE_SSL
cert_file = $SSL_CERT
key_file = $SSL_KEY
bind_address = $BIND_ADDRESS

# Kea DHCP configuration
kea_socket = $KEA_SOCKET
leases_file = $KEA_LEASES

# Scanner configuration
enable_scanner = $ENABLE_SCANNER
scanner_timeout = 5
scan_threads = 50

# SNMP configuration
enable_snmp = $ENABLE_SNMP
snmp_communities = $SNMP_COMMUNITIES

# Language
language = $LANGUAGE
EOF
    
    chmod 600 "$CONFIG_DIR/ultimate-kea-dashboard.conf"
    
    # Create symlink for compatibility
    ln -sf "$CONFIG_DIR/ultimate-kea-dashboard.conf" "$INSTALL_DIR/etc/ultimate-kea-dashboard.conf"
    
    print_success "Configuration created at $CONFIG_DIR/ultimate-kea-dashboard.conf"
}

# Create systemd service
create_systemd_service() {
    print_section "Creating Systemd Service"
    
    cat > "$SYSTEMD_DIR/ultimate-kea-dashboard.service" <<EOF
[Unit]
Description=Ultimate Kea DHCP Dashboard
After=network.target kea-dhcp4.service

[Service]
Type=simple
User=root
WorkingDirectory=$INSTALL_DIR
ExecStart=$INSTALL_DIR/bin/ultimate-kea-dashboard
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
    
    systemctl daemon-reload
    
    print_success "Systemd service created"
}

# Start service
start_service() {
    print_section "Starting Service"
    
    systemctl enable ultimate-kea-dashboard.service
    systemctl start ultimate-kea-dashboard.service
    
    sleep 2
    
    if systemctl is-active --quiet ultimate-kea-dashboard.service; then
        print_success "Service started successfully"
    else
        print_error "Service failed to start"
        print_info "Check logs with: journalctl -u ultimate-kea-dashboard -f"
        exit 1
    fi
}

# Print completion message
print_completion() {
    print_header
    echo -e "${GREEN}${BOLD}"
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║                                                              ║"
    echo "║             Installation Completed Successfully!            ║"
    echo "║                                                              ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    
    echo -e "${BOLD}Access your dashboard at:${NC}"
    if [[ $USE_SSL == "true" ]]; then
        echo -e "  ${CYAN}https://$(hostname -I | awk '{print $1}'):$PORT${NC}"
    else
        echo -e "  ${CYAN}http://$(hostname -I | awk '{print $1}'):$PORT${NC}"
    fi
    
    echo -e "\n${BOLD}Useful commands:${NC}"
    echo -e "  ${YELLOW}sudo systemctl status ultimate-kea-dashboard${NC}  - Check service status"
    echo -e "  ${YELLOW}sudo systemctl restart ultimate-kea-dashboard${NC} - Restart service"
    echo -e "  ${YELLOW}sudo journalctl -u ultimate-kea-dashboard -f${NC} - View logs"
    echo -e "  ${YELLOW}sudo nano $CONFIG_DIR/ultimate-kea-dashboard.conf${NC} - Edit configuration"
    
    echo -e "\n${GREEN}Enjoy your Ultimate Kea DHCP Dashboard!${NC}\n"
}

# Main installation flow
main() {
    print_header
    check_root
    check_requirements
    install_dependencies
    configure_dashboard
    install_files
    create_config
    create_systemd_service
    start_service
    print_completion
}

# Run main function
main
