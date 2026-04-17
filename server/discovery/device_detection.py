"""Device type detection and classification"""

from . import custom_devices


SERVICE_ICONS = {
    '22': ('🔑', 'SSH'),
    '25': ('✉️', 'SMTP'),
    '53': ('🔍', 'DNS'),
    '80': ('🌐', 'HTTP'),
    '110': ('📧', 'POP3'),
    '143': ('📧', 'IMAP'),
    '161': ('📊', 'SNMP'),
    '389': ('👤', 'LDAP'),
    '443': ('🔒', 'HTTPS'),
    '631': ('🖨️', 'CUPS'),
    '3000': ('📊', 'Web'),
    '3306': ('🗄️', 'MySQL'),
    '5000': ('📊', 'Flask'),
    '5432': ('🗄️', 'PostgreSQL'),
    '5900': ('👁️', 'VNC'),
    '6379': ('⚡', 'Redis'),
    '8000': ('🌐', 'HTTP'),
    '8080': ('🌐', 'HTTP-Alt'),
    '8443': ('🔒', 'HTTPS-Alt'),
    '8888': ('🌐', 'HTTP'),
    '9000': ('🎯', 'Admin'),
    '9090': ('📊', 'Admin'),
}


def format_service_link(ip, port_service, service_name):
    """Format service with icon and clickable link if applicable"""
    port = port_service.split('/')[0]
    
    # Get icon for known services
    if port in SERVICE_ICONS:
        icon, label = SERVICE_ICONS[port]
    else:
        icon = '⚙️'
    
    # Truncate service name if too long
    display_name = service_name if len(service_name) <= 40 else service_name[:37] + '...'
    
    # Create clickable link for web services
    if port in ['80', '443', '8080', '8443', '3000', '5000', '8000', '8888', '9000', '9090']:
        protocol = 'https' if port in ['443', '8443'] else 'http'
        url = f"{protocol}://{ip}:{port}"
        return f'<li>{icon} <a href="{url}" target="_blank" class="service-link" title="{service_name}">{display_name}</a></li>'
    else:
        return f'<li>{icon} <span title="{service_name}">{display_name}</span></li>'


def get_device_type(hostname, vendor, mac, device_info=None):
    """Detect device type from all available sources
    Returns: (emoji, label, icon_name) where icon_name is for SVG icons
    """
    h = hostname.lower() if hostname and hostname != "N/A" else ""
    v = vendor.lower() if vendor else ""
    m = mac.lower() if mac else ""
    
    combined = f"{h} {v} {m}"
    
    if device_info:
        if device_info.get("snmp"):
            combined += f" {device_info['snmp'].lower()}"
        if device_info.get("mdns"):
            combined += f" {device_info['mdns'].lower()}"
    
    # Check custom devices FIRST (from custom-devices.json)
    custom_type = custom_devices.get_device_type_info(hostname, vendor, mac)
    if custom_type:
        return custom_type
    
    # Proxmox detection (must be BEFORE other checks)
    # 1. Hostname contains "pve" = Proxmox hypervisor
    # 2. Vendor = "Proxmox Server Solutions" = VM on Proxmox
    if "proxmox server solutions" in v:
        # It's a VM running on Proxmox (MAC assigned by Proxmox)
        return ("💻", "Proxmox VM", "computer")
    
    if any(x in h for x in ["pve", "proxmox"]) and "proxmox" not in v:
        # Hostname contains pve/proxmox but vendor is NOT Proxmox = it's the hypervisor itself
        # Special case for Raspberry Pi running Proxmox
        if "raspberry" in v.lower() or "raspberrypi" in h:
            return ("🍓", "Proxmox (RPi)", "raspberry-pi")
        return ("📡", "Proxmox VE", "server")
    
    # Cameras
    if any(x in combined for x in ["dafang", "camera", "webcam", "hikvision", "dahua", "reolink", "wyze", "ring", "doorbell", "video", "ipcam", "cam-"]):
        return ("📷", "Camera", "camera")
    
    # Samsung devices
    if "samsung" in v or "s24" in h or "galaxy" in h or "tab-a" in h or "sm-" in h:
        if any(x in h for x in ["tab", "tablet"]):
            return ("📱", "Samsung Tablet", "tablet")
        elif any(x in h for x in ["s24", "s23", "s22", "s21", "s20", "galaxy", "phone"]):
            return ("📱", "Samsung Phone", "samsung-mobile")
        elif "tv" in h:
            return ("📺", "Samsung TV", "tv")
        else:
            return ("📱", "Samsung", "samsung-mobile")
    
    # Apple devices
    if any(x in h for x in ["macbook", "imac", "mac-", "iphone", "ipad"]):
        if "macbook" in h or "imac" in h or "mac" in h:
            return ("🍎", "Apple Mac", "apple-mac")
        elif "iphone" in h:
            return ("🍎", "iPhone", "apple-mobile")
        elif "ipad" in h:
            return ("🍎", "iPad", "tablet")
        else:
            return ("🍎", "Apple", "apple-mobile")
    
    if any(x in v for x in ["apple"]):
        return ("🍎", "Apple", "apple-mobile")
    
    # Amazon devices
    if "amazon" in v:
        if any(x in combined for x in ["echo", "alexa", "dot"]):
            return ("🔊", "Amazon Echo", "smart-home")
        elif any(x in combined for x in ["fire", "firetv", "stick"]):
            return ("📺", "Fire TV", "tv")
        else:
            return ("📦", "Amazon Device", "iot")
    
    # TV & Media devices
    if any(x in h for x in ["tv", "tele", "television"]):
        if "philips" in combined or "phillips" in combined:
            return ("📺", "Philips TV", "tv")
        elif "samsung" in combined:
            return ("📺", "Samsung TV", "tv")
        elif "lg" in combined:
            return ("📺", "LG TV", "tv")
        else:
            return ("📺", "TV", "tv")
    
    if any(x in combined for x in ["samsung tv", "lg tv", "sony tv", "philips", "panasonic", "toshiba", "vizio", "roku", "firestick", "appletv", "android tv", "smarttv", "hisense", "sharp"]):
        return ("📺", "TV", "tv")
    
    # Smartphones
    if any(x in h for x in ["phone", "mobile", "pixel", "oneplus", "redmi"]):
        return ("📱", "Smartphone", "mobile")
    
    if any(x in combined for x in ["android", "pixel", "htc", "motorola", "oneplus", "redmi", "realme", "oppo", "vivo"]):
        return ("📱", "Smartphone", "mobile")
    
    # Tablets
    if any(x in h for x in ["tablet", "tab-", "ipad"]):
        return ("📱", "Tablet", "tablet")
    
    # Xiaomi devices
    if "xiaomi" in v:
        if any(x in h for x in ["camera", "cam", "dafang"]):
            return ("📷", "Xiaomi Camera", "camera")
        elif any(x in h for x in ["phone", "redmi", "mi-", "poco"]):
            return ("📱", "Xiaomi Phone", "mobile")
        elif "tv" in h:
            return ("📺", "Xiaomi TV", "tv")
        else:
            return ("🔌", "Xiaomi Device", "iot")
    
    # Routers & Network
    if any(x in combined for x in ["router", "gateway", "access point", "ap-", "ap_", "wifi", "ubiquiti", "tp-link", "netgear", "cisco", "asus", "linksys", "mikrotik", "fortinet", "d-link", "meraki", "ieee registration authority"]):
        return ("📡", "Router/AP", "router")
    
    # Printers
    if any(x in combined for x in ["print", "brother", "hp", "xerox", "canon", "epson", "ricoh", "konica", "minolta"]):
        return ("🖨️", "Printer", "printer")
    
    # Smart Home & IoT
    if any(x in combined for x in ["esp", "esp32", "esp8266", "esp8285", "espressif", "arduino", "home", "smart", "homekit", "zigbee", "zwave", "mqtt", "sonoff", "shelly", "tasmota", "tuya"]):
        return ("🔌", "Smart Home", "iot")
    
    # Laptops & Desktops
    if any(x in combined for x in ["laptop", "desktop", "pc", "computer", "dell", "hp", "lenovo", "asus", "acer", "msi", "windows", "linux", "workstation"]):
        return ("💻", "Computer", "laptop")
    
    # Raspberry Pi & SBC
    if any(x in combined for x in ["raspi", "raspberry", "rpi", "pi", "jetson", "odroid", "beaglebone"]):
        return ("🍓", "Raspberry Pi", "raspberry-pi")
    
    # Servers & NAS (check before generic "server" pattern)
    if any(x in combined for x in ["proxmox", "esxi", "vmware", "vcenter", "hypervisor", "truenas", "freenas"]):
        return ("🖥️", "Server", "server")
    
    if any(x in combined for x in ["server", "nas", "synology", "qnap", "pfsense", "homelab", "unraid"]):
        return ("⚙️", "Server/NAS", "nas")
    
    # Smart TVs & Media Players
    if any(x in combined for x in ["chromecast", "nvidia shield", "kodi", "plex", "media"]):
        return ("📺", "Media Player", "tv")
    
    # Network Switches (BEFORE gaming detection!)
    if any(x in h for x in ["switch", "switch1", "switch2", "sw-", "sw1", "sw2"]) and "nintendo" not in v.lower():
        return ("🔌", "Network Switch", "switch")
    
    # Gaming
    if any(x in combined for x in ["gaming", "xbox", "playstation", "ps4", "ps5", "nintendo", "steam deck"]):
        return ("🎮", "Gaming", "gaming")
    
    # Audio & Speakers
    if any(x in combined for x in ["speaker", "audio", "sonos", "bose", "harman", "denon", "yamaha", "amplifier"]):
        return ("🔊", "Audio", "smart-home")
    
    # Smartwatch & Wearables
    if any(x in combined for x in ["watch", "fitbit", "garmin", "smartband", "wearable"]):
        return ("⌚", "Wearable", "iot")
    
    # Scanners
    if any(x in combined for x in ["scanner", "mfp", "multifunction"]):
        return ("📄", "Scanner", "printer")
    
    # Network Storage
    if any(x in combined for x in ["storage", "backup", "hdd", "ssd"]):
        return ("💾", "Storage", "nas")
    
    # Chinese tech company devices
    if "hui zhou gaoshengda" in v or "gaoshengda" in v:
        if "tv" in h or "tele" in h:
            return ("📺", "TV Box", "tv")
        else:
            return ("📺", "Media Box", "tv")
    
    return ("❓", "Unknown", "unknown")
