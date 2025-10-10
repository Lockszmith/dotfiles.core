#!/usr/bin/env python3
"""
Node and SSD Information Extractor

This script extracts node information (dnodes and cnodes) and SSD information from 
bundle directories and formats it according to the specified output format. It can 
list all available nodes, show detailed information for a specific node, or show 
SSD replacement information for a specific SSD.

Node types are determined by MGMT IP:
- MGMT IP >= 100: dnode
- MGMT IP < 100: cnode

SSD Mode:
- Use --ssd <ssd_serial> to search for SSD replacement information
- Only works with DNodes (nodes with MGMT IP >= 100)
- Shows SSD location, device path, model, and associated node information

Node Matching Logic:
1. Exact match to node name, serial number, MGMT IP, or data IP
2. Regex match to node name, serial number, MGMT IP, or data IP
   - If regex matches exactly one node, show that node
   - If regex matches multiple nodes, show list of matches
3. If no node matches, try regex match to box serial numbers and show list

Usage: 
    python rma_prep.py                               # List all available nodes
    python rma_prep.py dnode-3-100                   # Show specific node (exact match)
    python rma_prep.py 'dnode.*100'                  # Regex match nodes
    python rma_prep.py '172\.16\.1\.'                # Match by IP pattern
    python rma_prep.py 'SN12345'                     # Match by serial number
    python rma_prep.py --ssd PHAC2070006C30PGGN      # Show SSD replacement info

Examples:
    python rma_prep.py
    python rma_prep.py dnode-3-100
    python rma_prep.py cnode-1-50
    python rma_prep.py 'dnode-[0-9]-100'
    python rma_prep.py '172.16.1.11'
    python rma_prep.py 'BOX.*123'
    python rma_prep.py --ssd PHAC2070006C30PGGN
"""

import sys
import os
import json
import re
import argparse
import logging
from pathlib import Path
from datetime import datetime
from collections import defaultdict




def calculate_minimum_unique_paths(bundle_dirs):
    """Calculate minimum unique path components for bundle directories."""
    if not bundle_dirs:
        return {}
    
    current_dir = Path('.').resolve()
    
    # Get relative paths from current directory
    relative_paths = {}
    for bundle_dir in bundle_dirs:
        try:
            rel_path = bundle_dir.resolve().relative_to(current_dir)
            relative_paths[bundle_dir] = rel_path.parts
        except ValueError:
            # If bundle_dir is not relative to current_dir, use absolute path
            relative_paths[bundle_dir] = bundle_dir.resolve().parts
    
    if not relative_paths:
        return {}
    
    # Find minimum number of path components needed for uniqueness
    max_components = max(len(parts) for parts in relative_paths.values())
    
    for num_components in range(1, max_components + 1):
        # Create shortened paths with current number of components
        shortened_paths = {}
        for bundle_dir, parts in relative_paths.items():
            if len(parts) >= num_components:
                shortened = '/'.join(parts[:num_components])
            else:
                shortened = '/'.join(parts)
            shortened_paths[bundle_dir] = shortened
        
        # Check if all shortened paths are unique
        if len(set(shortened_paths.values())) == len(shortened_paths):
            return shortened_paths
    
    # Fallback: return full relative paths
    return {bundle_dir: '/'.join(parts) for bundle_dir, parts in relative_paths.items()}


def find_bundle_directories():
    """Find all bundle directories by looking for METADATA/BUNDLE_ARGS files up to 5 levels deep."""
    bundle_dirs = []
    current_dir = Path('.')
    logging.debug(f"Starting bundle directory search from: {current_dir.resolve()}")
    
    # First, check if the current directory itself is a bundle directory
    bundle_args_file = current_dir / 'METADATA' / 'BUNDLE_ARGS'
    if bundle_args_file.exists():
        logging.debug(f"Found bundle directory: {current_dir}")
        bundle_dirs.append(current_dir)
    
    def search_directory(directory, current_level=0, max_levels=5):
        """Recursively search for bundle directories."""
        if current_level > max_levels:
            logging.debug(f"Reached maximum search depth ({max_levels}) at: {directory}")
            return
        
        try:
            logging.debug(f"Searching directory (level {current_level}): {directory}")
            for item in directory.iterdir():
                if item.is_dir():
                    # Check if this directory is a bundle directory
                    bundle_args_file = item / 'METADATA' / 'BUNDLE_ARGS'
                    if bundle_args_file.exists():
                        logging.debug(f"Found bundle directory: {item}")
                        bundle_dirs.append(item)
                    else:
                        # Recursively search subdirectories
                        search_directory(item, current_level + 1, max_levels)
        except (PermissionError, OSError) as e:
            logging.debug(f"Cannot access directory {directory}: {e}")
            pass
    
    search_directory(current_dir)
    logging.debug(f"Found {len(bundle_dirs)} bundle directories total")
    return bundle_dirs


def filter_latest_bundles_per_node(bundle_dirs):
    """Filter bundle directories to keep only the latest bundle per node.
    
    Groups bundles by node hostname and keeps only the most recent one.
    """
    logging.debug(f"Filtering {len(bundle_dirs)} bundles to keep only latest per node")
    node_bundles = {}  # hostname -> list of (bundle_dir, timestamp)
    
    # First pass: collect all bundles with their timestamps and node info
    for bundle_dir in bundle_dirs:
        monitor_file = bundle_dir / 'monitor_result.json'
        if not monitor_file.exists():
            logging.debug(f"Skipping bundle (no monitor_result.json): {bundle_dir}")
            continue
        
        # Extract basic node info
        node_info = extract_node_info_from_monitor(monitor_file)
        if not node_info:
            continue
        
        # Extract hostname from systemctl output (preferred identifier)
        hostname = extract_hostname_from_systemctl(bundle_dir)
        if not hostname:
            # Fallback to system_product_name if no hostname
            hostname = node_info.get('name')
        
        if not hostname:
            logging.debug(f"Skipping bundle (no hostname found): {bundle_dir}")
            continue
        
        # Extract data IP from bundle directory (for logging purposes)
        data_ip = extract_data_ip_from_bundle(bundle_dir)
        
        logging.debug(f"Processing bundle for node {hostname} (data IP: {data_ip}): {bundle_dir}")
        
        # Extract create_time from BUNDLE_ARGS file
        timestamp = extract_create_time_from_bundle_args(bundle_dir, return_datetime=True)
        if not timestamp:
            # If no create_time found, use directory modification time as fallback
            try:
                timestamp = datetime.fromtimestamp(bundle_dir.stat().st_mtime)
                logging.debug(f"Using directory mtime as timestamp for {bundle_dir}: {timestamp}")
            except OSError:
                timestamp = datetime.min
                logging.debug(f"Could not get timestamp for {bundle_dir}, using minimum datetime")
        else:
            logging.debug(f"Using create_time as timestamp for {bundle_dir}: {timestamp}")
        
        # Group by hostname (which uniquely identifies a physical node)
        if hostname not in node_bundles:
            node_bundles[hostname] = []
        node_bundles[hostname].append((bundle_dir, timestamp))
    
    # Second pass: keep only the latest bundle per node
    latest_bundles = []
    for hostname, bundles in node_bundles.items():
        if bundles:
            # Sort by timestamp and take the latest
            latest_bundle = max(bundles, key=lambda x: x[1])
            logging.debug(f"For node {hostname}, selected latest bundle: {latest_bundle[0]} (timestamp: {latest_bundle[1]})")
            if len(bundles) > 1:
                logging.debug(f"  Skipped {len(bundles)-1} older bundles for this node")
            latest_bundles.append(latest_bundle[0])
    
    logging.debug(f"After filtering: {len(latest_bundles)} bundles (latest per node)")
    return latest_bundles


def extract_box_serial_from_fru(fru_file_path):
    """Extract Box serial number from ipmitool FRU print file."""
    try:
        with open(fru_file_path, 'r') as f:
            content = f.read()
        
        # Look for Chassis Serial line
        match = re.search(r'Chassis Serial\s+:\s+(\S+)', content)
        if match:
            return match.group(1)
    except (FileNotFoundError, IOError):
        pass
    return None


def extract_board_serial_from_fru(fru_file_path):
    """Extract Board serial number from ipmitool FRU print file."""
    try:
        with open(fru_file_path, 'r') as f:
            content = f.read()
        
        # Look for Board Serial line
        match = re.search(r'Board Serial\s+:\s+(\S+)', content)
        if match:
            return match.group(1)
    except (FileNotFoundError, IOError):
        pass
    return None


def get_ip_last_octet(ip_address):
    """Extract the last octet from an IP address for sorting purposes."""
    if not ip_address:
        return 0
    try:
        return int(ip_address.split('.')[-1])
    except (ValueError, IndexError):
        return 0


def extract_ipmi_ip_from_bundle(bundle_dir):
    """Extract IPMI IP address from ipmitool lan print files."""
    try:
        ipmitool_dir = bundle_dir / 'ipmitool'
        if not ipmitool_dir.exists():
            logging.debug(f"No ipmitool directory found: {ipmitool_dir}")
            return None
        
        # Look for ipmitool_lan_print_*.txt files (usually channel 1)
        lan_print_files = list(ipmitool_dir.glob('ipmitool_lan_print_*.txt'))
        if not lan_print_files:
            logging.debug(f"No ipmitool_lan_print files found in: {ipmitool_dir}")
            return None
        
        # Try each lan print file (typically just one: ipmitool_lan_print_1.txt)
        for lan_file in lan_print_files:
            logging.debug(f"Reading IPMI configuration from: {lan_file}")
            try:
                with open(lan_file, 'r') as f:
                    content = f.read()
                
                # Look for IP Address line
                match = re.search(r'IP Address\s+:\s+([0-9]+\.[0-9]+\.[0-9]+\.[0-9]+)', content)
                if match:
                    ipmi_ip = match.group(1)
                    # Exclude obviously invalid IPs
                    if ipmi_ip != '0.0.0.0':
                        logging.debug(f"Found IPMI IP: {ipmi_ip}")
                        return ipmi_ip
                    else:
                        logging.debug(f"Skipping invalid IPMI IP: {ipmi_ip}")
            except (IOError, OSError) as e:
                logging.debug(f"Error reading IPMI lan file {lan_file}: {e}")
                continue
        
        logging.debug("No valid IPMI IP found in any lan print files")
    except (OSError, AttributeError) as e:
        logging.debug(f"Error accessing IPMI files in {bundle_dir}: {e}")
    
    return None


def determine_node_type(data_ip=None, hostname=None, mgmt_ip=None):
    """Determine node type based on hostname pattern first, then data IP (172.x.x.x).
    
    Args:
        data_ip: Data network IP address string (e.g., "172.16.1.102")
        hostname: Hostname string (e.g., "rd1vast02-dnode102")
        mgmt_ip: Management IP address string (e.g., "10.1.1.100") - for logging only
    
    Returns:
        'dnode' if hostname contains 'dnode' or data IP last octet >= 100, 'cnode' otherwise, or 'unknown' if invalid
    """
    logging.debug(f"Determining node type: hostname='{hostname}', data_ip='{data_ip}', mgmt_ip='{mgmt_ip}'")
    
    # First priority: check hostname pattern for 'dnode' or 'cnode'
    if hostname:
        hostname_lower = hostname.lower()
        if 'dnode' in hostname_lower:
            logging.debug(f"Node type determined from hostname: dnode (found 'dnode' in '{hostname}')")
            return 'dnode'
        elif 'cnode' in hostname_lower:
            logging.debug(f"Node type determined from hostname: cnode (found 'cnode' in '{hostname}')")
            return 'cnode'
        else:
            logging.debug(f"Hostname '{hostname}' does not contain dnode/cnode pattern, falling back to data IP")
    
    # Fallback: use data IP logic (172.x.x.x range)
    if not data_ip:
        logging.debug("No data IP available, returning 'unknown'")
        return 'unknown'
    
    try:
        # Extract the last octet from the data IP address
        last_octet = int(data_ip.split('.')[-1])
        node_type = 'dnode' if last_octet >= 100 else 'cnode'
        logging.debug(f"Node type determined from data IP: {node_type} (last octet {last_octet} from {data_ip} {'>=100' if last_octet >= 100 else '<100'})")
        return node_type
    except (ValueError, IndexError) as e:
        logging.debug(f"Could not parse data IP '{data_ip}': {e}")
        return 'unknown'


def update_node_type_with_hostname(node_info, hostname):
    """Update node type in node_info based on hostname if available."""
    if node_info and hostname:
        # Re-determine node type with hostname information
        data_ip = node_info.get('data_ip')
        mgmt_ip = node_info.get('mgmt_ip')
        node_type = determine_node_type(data_ip=data_ip, hostname=hostname, mgmt_ip=mgmt_ip)
        node_info['node_type'] = node_type
    return node_info


def extract_hostname_from_systemctl(bundle_dir):
    """Extract hostname from systemctl_output/systemctl_status.txt file."""
    try:
        systemctl_file = bundle_dir / 'systemctl_output' / 'systemctl_status.txt'
        if not systemctl_file.exists():
            return None
        
        with open(systemctl_file, 'r') as f:
            first_line = f.readline().strip()
        
        # Extract hostname from first line: "● hostname"
        if first_line.startswith('●'):
            hostname = first_line[1:].strip()  # Remove ● symbol and whitespace
            return hostname
    except (FileNotFoundError, IOError):
        pass
    return None


def extract_node_info_from_monitor(monitor_file_path):
    """Extract node information from monitor_result.json file."""
    try:
        with open(monitor_file_path, 'r') as f:
            data = json.load(f)
        
        node_info = data.get('node', {}).get('info', {})
        nics = data.get('nics', {})
        
        # Extract basic node information
        name = node_info.get('system_product_name', '')
        position = node_info.get('position', '')
        serial_number = node_info.get('system_serial_number', '')
        
        # Find management IP and data IP from monitor_result.json
        mgmt_ip = None
        mac_address = None
        data_ips = []  # Collect all data IPs to find the lowest one
        
        logging.debug(f"Extracting IPs from {len(nics)} network interfaces in monitor_result.json")
        
        for nic_name, nic_info in nics.items():
            nic_data = nic_info.get('info', {})
            address = nic_data.get('address', '')
            nic_mac_address = nic_data.get('mac_address', '')
            
            logging.debug(f"  Interface {nic_name}: address='{address}', mac='{nic_mac_address}'")
            
            # Look for management IP (typically 10.x.x.x range)
            if address and address.startswith('10.') and not mgmt_ip:
                mgmt_ip = address
                mac_address = nic_mac_address
                logging.debug(f"Found MGMT IP: {address} from interface {nic_name}")
            
            # Collect all data IPs (typically 172.16.x.x range)
            if address and address.startswith('172.16.'):
                data_ips.append(address)
                logging.debug(f"Found data IP candidate: {address} from interface {nic_name}")
        
        # Select the lowest data IP if multiple exist
        data_ip = None
        if data_ips:
            data_ip = min(data_ips)  # Select the lowest IP address
            if len(data_ips) > 1:
                logging.debug(f"Multiple data IPs found {data_ips}, selected lowest: {data_ip}")
            else:
                logging.debug(f"Single data IP found: {data_ip}")
        
        if not mgmt_ip:
            logging.debug("No MGMT IP found (no interfaces with 10.x.x.x addresses)")
        
        if not data_ip:
            logging.debug("No data IP found (no interfaces with 172.16.x.x addresses)")
        
        # Determine node type based on data IP (preferred) 
        node_type = determine_node_type(data_ip=data_ip, mgmt_ip=mgmt_ip)
        
        return {
            'name': name,
            'position': position,
            'serial_number': serial_number,
            'mgmt_ip': mgmt_ip,
            'mac_address': mac_address,
            'data_ip': data_ip,
            'node_type': node_type,
            'ipmi_ip': None  # Will be extracted separately by calling functions
        }
    except (FileNotFoundError, IOError, json.JSONDecodeError):
        return None


def extract_create_time_from_bundle_args(bundle_dir, return_datetime=False):
    """Extract create_time from BUNDLE_ARGS file.
    
    Args:
        bundle_dir: Path to bundle directory
        return_datetime: If True, returns datetime object; if False, returns formatted string
    
    Returns:
        datetime object or formatted string (YYYY-MM-DD HH:MM:SS) or None if not found
    """
    try:
        bundle_args_file = bundle_dir / 'METADATA' / 'BUNDLE_ARGS'
        if not bundle_args_file.exists():
            return None
        
        with open(bundle_args_file, 'r') as f:
            content = f.read()
        
        # Look for create_time line first, fallback to start_time if not found
        create_time_match = re.search(r'create_time:\s+(.+)', content)
        start_time_match = re.search(r'start_time:\s+(.+)', content)
        
        time_str = None
        if create_time_match:
            time_str = create_time_match.group(1)
        elif start_time_match:
            time_str = start_time_match.group(1)
            
        if time_str:
            # Parse the datetime string: 2025-09-09 18:14:58.277231+00:00
            try:
                # Split at the first dot to remove microseconds and everything after
                base_time_str = time_str.split('.')[0]
                # Parse into datetime object
                dt = datetime.strptime(base_time_str, '%Y-%m-%d %H:%M:%S')
                
                if return_datetime:
                    return dt
                else:
                    # Return formatted string for display
                    return base_time_str
            except ValueError:
                pass
    except (FileNotFoundError, IOError):
        pass
    return None


def extract_data_ip_from_bundle(bundle_dir):
    """Extract data IP from bundle directory by looking in various sources."""
    logging.debug(f"Extracting data IP from bundle: {bundle_dir}")
    
    try:
        # First try to extract from ip_addr.txt file
        ip_addr_file = bundle_dir / 'ip_addr.txt'
        if ip_addr_file.exists():
            logging.debug(f"Reading IP configuration from: {ip_addr_file}")
            with open(ip_addr_file, 'r') as f:
                content = f.read()
            
            # Look for bond0:m or bond0.<vlan>:m interface with 172.16.x.x IP
            match = re.search(r'bond0(?:\.\d+)?:m.*?inet (172\.16\.\d+\.\d+)/', content, re.DOTALL)
            if match:
                data_ip = match.group(1)
                logging.debug(f"Found data IP from ip_addr.txt: {data_ip}")
                return data_ip
            else:
                logging.debug("No data IP found in bond0:m interfaces")
        
        else:
            logging.debug(f"ip_addr.txt not found: {ip_addr_file}")
        
        # Fallback: try to extract from monitor_result.json
        monitor_file = bundle_dir / 'monitor_result.json'
        if monitor_file.exists():
            logging.debug(f"Trying fallback source: {monitor_file}")
            try:
                with open(monitor_file, 'r') as f:
                    data = json.load(f)
                
                nics = data.get('nics', {})
                logging.debug(f"Found {len(nics)} network interfaces in monitor_result.json")
                
                # Look for InfiniBand or Ethernet interfaces with 172.16.x.x addresses
                for nic_name, nic_info in nics.items():
                    nic_data = nic_info.get('info', {})
                    address = nic_data.get('address', '')
                    link_type = nic_data.get('link_type', '')
                    
                    logging.debug(f"  Interface {nic_name}: {address} ({link_type})")
                    
                    if address and address.startswith('172.16.'):
                        # Prioritize InfiniBand, but also accept Ethernet
                        if link_type == 'InfiniBand':
                            logging.debug(f"Found data IP from monitor_result.json (InfiniBand): {address}")
                            return address
                        elif link_type == 'Ethernet' and not address.endswith('.1'):
                            # Accept Ethernet but avoid .1 addresses (usually gateways)
                            logging.debug(f"Found data IP from monitor_result.json (Ethernet): {address}")
                            return address
                        else:
                            logging.debug(f"Skipping {address} (gateway or unsuitable interface)")
            except (json.JSONDecodeError, KeyError) as e:
                logging.debug(f"Error parsing monitor_result.json: {e}")
        else:
            logging.debug(f"Fallback source not found: {monitor_file}")
    except (FileNotFoundError, IOError) as e:
        logging.debug(f"Error reading data IP sources: {e}")
    
    logging.debug("No data IP found in bundle")
    return None


def extract_cluster_name_from_bundle(bundle_dir):
    """Extract cluster name from bundle configuration data."""
    try:
        # First: try to extract from systemctl status hostname
        hostname = extract_hostname_from_systemctl(bundle_dir)
        if hostname:
            # Extract cluster name from hostname pattern: cluster-dnode123 or cluster-cnode45
            hostname_match = re.search(r'^([^-]+(?:-[^-]+)*)-[dc]node\d+', hostname)
            if hostname_match:
                return hostname_match.group(1)
        
        # Fallback: try to extract from vast-configure_network.py-params.ini
        network_config_file = bundle_dir / 'vast-configure_network.py-params.ini'
        if network_config_file.exists():
            with open(network_config_file, 'r') as f:
                content = f.read()
            
            # Look for hostname line and extract cluster name from it
            hostname_match = re.search(r'hostname=([^-\n]+(?:-[^-\n]+)*)-[dc]node\d+', content)
            if hostname_match:
                return hostname_match.group(1)
        
        # Final fallback: try platform_env_id file
        env_id_file = bundle_dir / 'platform_env_id'
        if env_id_file.exists():
            with open(env_id_file, 'r') as f:
                content = f.read().strip()
            # This might contain cluster-related ID information
            if content and not content.isdigit():
                return content
    except (FileNotFoundError, IOError, AttributeError, IndexError):
        pass
    return "Unknown"


def extract_drive_location_from_logs(drive_serial, box_serial, bundle_dir):
    """Extract drive location from management logs using the dbox pattern.
    
    Searches for pattern: dbox-<box S/N>-<location:word>-<location:slot>-SSD-1 or -NVRAM-1
    """
    try:
        # Search paths for management logs in different bundle structures
        log_paths = []
        
        # Current bundle directory management-logs
        log_paths.append(bundle_dir / 'management-logs')
        
        # Navigate up to find other bundle directories with management logs
        case_dir = bundle_dir.parent.parent  # Go up to case level
        if case_dir.exists():
            # Look for all management-logs directories in the case directory tree
            for log_dir in case_dir.glob('**/management-logs'):
                log_paths.append(log_dir)
        
        # Also check parent directory management logs
        if bundle_dir.parent.exists():
            for log_dir in bundle_dir.parent.glob('**/management-logs'):
                log_paths.append(log_dir)
        
        # Remove duplicates
        log_paths = list(set(log_paths))
        
        for log_dir in log_paths:
            if not log_dir.exists():
                continue
                
            # Check workers.log and worker.log files
            for log_file_name in ['workers.log', 'worker.log']:
                log_file = log_dir / log_file_name
                if not log_file.exists():
                    continue
                
                try:
                    with open(log_file, 'r') as f:
                        for line in f:
                            # Look for lines containing both box serial and drive serial
                            if box_serial in line and drive_serial in line:
                                # Search for the dbox pattern: dbox-<box>-<location>-<slot>-SSD-1 or -NVRAM-1
                                ssd_match = re.search(rf'dbox-{re.escape(box_serial)}-([A-Z]+)-(\d+)-SSD-1', line)
                                nvram_match = re.search(rf'dbox-{re.escape(box_serial)}-([A-Z]+)-(\d+)-NVRAM-1', line)
                                
                                match = ssd_match or nvram_match
                                if match:
                                    location_word = match.group(1)
                                    location_slot = match.group(2)
                                    return f"{location_word}-{location_slot}"
                except (IOError, UnicodeDecodeError):
                    # Skip files that can't be read
                    continue
        
    except (OSError, AttributeError):
        pass
    return None


def determine_drive_type(model, path=''):
    """Determine drive type based on model and path information.
    
    Returns:
        'nvram' for NVRAM/SCM drives, 'ssd' for SSD drives
    """
    logging.debug(f"Determining drive type: model='{model}', path='{path}'")
    
    if not model:
        logging.debug("No model information available, defaulting to SSD")
        return 'ssd'  # Default fallback
    
    model_lower = model.lower()
    path_lower = path.lower()
    
    nvram_indicators = ['optane', 'dcpmm', 'ssdpe21k', 'scm', 'nvdimm', 'pmem', 'pascari']
    path_indicators = ['nvdimm', 'pmem']
    
    # NVRAM/SCM indicators
    for indicator in nvram_indicators:
        if indicator in model_lower:
            logging.debug(f"Drive type determined as NVRAM: found '{indicator}' in model '{model}'")
            return 'nvram'
    
    # Additional path-based detection
    for indicator in path_indicators:
        if indicator in path_lower:
            logging.debug(f"Drive type determined as NVRAM: found '{indicator}' in path '{path}'")
            return 'nvram'
    
    # Default to SSD
    logging.debug(f"Drive type determined as SSD: no NVRAM indicators found in model '{model}' or path '{path}'")
    return 'ssd'


def find_drive_in_bundle(drive_serial, bundle_dir):
    """Find drive (SSD/NVRAM) information in a specific bundle directory.
    
    Returns:
        dict: Drive information if found, None otherwise
    """
    logging.debug(f"Searching for drive '{drive_serial}' in bundle: {bundle_dir}")
    
    try:
        # First check nvme_list.json as primary source
        nvme_list_file = bundle_dir / 'nvme_list.json'
        if nvme_list_file.exists():
            logging.debug(f"Reading primary source: {nvme_list_file}")
            with open(nvme_list_file, 'r') as f:
                nvme_data = json.load(f)
            
            devices = nvme_data.get('Devices', [])
            logging.debug(f"Found {len(devices)} devices in nvme_list.json")
            
            for i, device in enumerate(devices):
                device_serial = device.get('SerialNumber')
                logging.debug(f"  Device {i}: serial='{device_serial}', model='{device.get('ModelNumber')}'")
                if device_serial == drive_serial:
                    model = device.get('ModelNumber')
                    path = device.get('DevicePath')
                    drive_type = determine_drive_type(model, path)
                    logging.debug(f"Found drive '{drive_serial}' in nvme_list.json: {model} at {path} (type: {drive_type})")
                    return {
                        'serial': device.get('SerialNumber'),
                        'model': model,
                        'path': path,
                        'size': device.get('PhysicalSize'),
                        'firmware_rev': device.get('Firmware'),
                        'index': device.get('Index'),
                        'drive_type': drive_type
                    }
        else:
            logging.debug(f"Primary source not found: {nvme_list_file}")
        
        # Fallback: check nvme_cli_list.json for extended info
        nvme_cli_file = bundle_dir / 'nvme_cli_list.json'
        if nvme_cli_file.exists():
            logging.debug(f"Reading fallback source: {nvme_cli_file}")
            with open(nvme_cli_file, 'r') as f:
                nvme_data = json.load(f)
            
            # Check both drives and nvrams sections
            drives_list = nvme_data.get('drives', [])
            nvrams_list = nvme_data.get('nvrams', [])
            all_drives = drives_list + nvrams_list
            logging.debug(f"Found {len(drives_list)} drives and {len(nvrams_list)} nvrams in nvme_cli_list.json")
            
            for i, drive in enumerate(all_drives):
                device_serial = drive.get('serial')
                logging.debug(f"  Device {i}: serial='{device_serial}', model='{drive.get('model')}'")
                if device_serial == drive_serial:
                    model = drive.get('model')
                    path = drive.get('path')
                    drive_type = determine_drive_type(model, path)
                    logging.debug(f"Found drive '{drive_serial}' in nvme_cli_list.json: {model} at {path} (type: {drive_type})")
                    return {
                        'serial': drive.get('serial'),
                        'model': model,
                        'path': path,
                        'size': drive.get('size'),
                        'pci_switch_position': drive.get('pci_switch_position'),
                        'pci_switch_slot': drive.get('pci_switch_slot'),
                        'firmware_rev': drive.get('firmware_rev'),
                        'temperature': drive.get('temperature'),
                        'device_minor': drive.get('device_minor'),
                        'drive_type': drive_type
                    }
        else:
            logging.debug(f"Fallback source not found: {nvme_cli_file}")
            
    except (FileNotFoundError, IOError, json.JSONDecodeError) as e:
        logging.debug(f"Error reading drive data from {bundle_dir}: {e}")
    
    logging.debug(f"Drive '{drive_serial}' not found in bundle: {bundle_dir}")
    return None


def find_drive_in_bundles(drive_serial, bundle_dirs):
    """Find the specified drive (SSD/NVRAM) in bundle directories.
    
    Returns:
        tuple: (drive_info, node_info, bundle_dir) if found, (None, None, None) otherwise
    """
    logging.debug(f"Searching for drive '{drive_serial}' across {len(bundle_dirs)} bundles")
    
    # Calculate minimum unique paths for all bundle directories
    unique_paths = calculate_minimum_unique_paths(bundle_dirs)
    
    for i, bundle_dir in enumerate(bundle_dirs, 1):
        logging.debug(f"Checking bundle {i}/{len(bundle_dirs)}: {bundle_dir}")
        
        # First check if this bundle contains the drive
        drive_info = find_drive_in_bundle(drive_serial, bundle_dir)
        if not drive_info:
            logging.debug(f"Drive not found in bundle {i}")
            continue
            
        logging.debug(f"Drive found in bundle {i}! Extracting node information...")
            
        # Get node information for this bundle
        monitor_file = bundle_dir / 'monitor_result.json'
        if not monitor_file.exists():
            continue
            
        node_info = extract_node_info_from_monitor(monitor_file)
        if not node_info:
            continue
        
        # Extract hostname from systemctl output (preferred over system_product_name)
        hostname = extract_hostname_from_systemctl(bundle_dir)
        if hostname:
            node_info['name'] = hostname
            # Update node type with hostname information
            update_node_type_with_hostname(node_info, hostname)
        
        # Check if this is a DNode (required for drive replacement) - after hostname-based node type correction
        if node_info.get('node_type') != 'dnode':
            continue
        
        # Extract data IP from bundle directory
        data_ip = extract_data_ip_from_bundle(bundle_dir)
        node_info['data_ip'] = data_ip
        
        # Extract IPMI IP from bundle directory
        ipmi_ip = extract_ipmi_ip_from_bundle(bundle_dir)
        node_info['ipmi_ip'] = ipmi_ip
        
        # Extract IPMI IP from bundle directory
        ipmi_ip = extract_ipmi_ip_from_bundle(bundle_dir)
        node_info['ipmi_ip'] = ipmi_ip
        
        # Add bundle path (display path for users)
        node_info['bundle_path'] = unique_paths.get(bundle_dir, str(bundle_dir))
        # Add full bundle directory path (for internal processing)
        node_info['bundle_dir_full'] = str(bundle_dir)
        
        # Extract create_time from BUNDLE_ARGS
        create_time = extract_create_time_from_bundle_args(bundle_dir)
        node_info['create_time'] = create_time
        
        # Extract Box serial number from FRU file
        bundle_box_serial = None
        bundle_board_serial = None
        fru_file = bundle_dir / 'ipmitool' / 'ipmitool_fru_list.txt'
        if fru_file.exists():
            bundle_box_serial = extract_box_serial_from_fru(fru_file)
            bundle_board_serial = extract_board_serial_from_fru(fru_file)
            node_info['box_serial'] = bundle_box_serial
            # Override system_serial_number with board serial if available
            if bundle_board_serial:
                node_info['serial_number'] = bundle_board_serial
        
        # Extract cluster name
        cluster_name = extract_cluster_name_from_bundle(bundle_dir)
        node_info['cluster_name'] = cluster_name
        
        return drive_info, node_info, bundle_dir
    
    return None, None, None


def find_node_in_bundles(node_name, bundle_dirs):
    """Find the specified node in bundle directories using enhanced matching logic.
    
    Returns:
        tuple: (match_type, target_node, sibling_nodes, box_serial, matched_nodes)
        - match_type: 'single', 'multiple', 'box_match', or 'none'
        - target_node: Single matched node (only for 'single' match_type)
        - sibling_nodes: Siblings of target_node (only for 'single' match_type)
        - box_serial: Box serial of target_node (only for 'single' match_type)
        - matched_nodes: List of matched nodes (for 'multiple' and 'box_match' types)
    """
    all_nodes = []
    box_nodes = {}  # Group nodes by Box serial number
    
    # Calculate minimum unique paths for all bundle directories
    unique_paths = calculate_minimum_unique_paths(bundle_dirs)
    
    # First pass: collect all node information and group by Box serial
    for bundle_dir in bundle_dirs:
        monitor_file = bundle_dir / 'monitor_result.json'
        if not monitor_file.exists():
            continue
            
        node_info = extract_node_info_from_monitor(monitor_file)
        if not node_info:
            continue
        
        # Extract hostname from systemctl output (preferred over system_product_name)
        hostname = extract_hostname_from_systemctl(bundle_dir)
        if hostname:
            node_info['name'] = hostname
            # Update node type with hostname information
            update_node_type_with_hostname(node_info, hostname)
        
        # Extract data IP from bundle directory
        data_ip = extract_data_ip_from_bundle(bundle_dir)
        node_info['data_ip'] = data_ip
        
        # Extract IPMI IP from bundle directory
        ipmi_ip = extract_ipmi_ip_from_bundle(bundle_dir)
        node_info['ipmi_ip'] = ipmi_ip
        
        # Add bundle path
        node_info['bundle_path'] = unique_paths.get(bundle_dir, str(bundle_dir))
        
        # Extract create_time from BUNDLE_ARGS
        create_time = extract_create_time_from_bundle_args(bundle_dir)
        node_info['create_time'] = create_time
        
        # Extract Box serial number from FRU file
        bundle_box_serial = None
        bundle_board_serial = None
        fru_file = bundle_dir / 'ipmitool' / 'ipmitool_fru_list.txt'
        if fru_file.exists():
            bundle_box_serial = extract_box_serial_from_fru(fru_file)
            bundle_board_serial = extract_board_serial_from_fru(fru_file)
        
        if data_ip and bundle_box_serial:
            node_info['box_serial'] = bundle_box_serial
            # Override system_serial_number with board serial if available
            if bundle_board_serial:
                node_info['serial_number'] = bundle_board_serial
            all_nodes.append(node_info)
            
            # Group nodes by Box serial number
            if bundle_box_serial not in box_nodes:
                box_nodes[bundle_box_serial] = []
            box_nodes[bundle_box_serial].append(node_info)
    
    # Step 1: Try exact matches first
    exact_matches = []
    for node in all_nodes:
        if (node.get('name') == node_name or 
            node.get('serial_number') == node_name or 
            node.get('mgmt_ip') == node_name or 
            node.get('data_ip') == node_name):
            exact_matches.append(node)
    
    if len(exact_matches) == 1:
        target_node = exact_matches[0]
        target_box_serial = target_node['box_serial']
        
        # Find siblings (deduplicated by node name and data IP)
        sibling_nodes = []
        seen_node_identifiers = set()
        target_name = target_node.get('name')
        target_data_ip = target_node.get('data_ip')
        box_nodes_list = box_nodes[target_box_serial]
        box_nodes_list.sort(key=lambda x: get_ip_last_octet(x.get('data_ip', '')))
        
        for node in box_nodes_list:
            node_name = node.get('name')
            node_data_ip = node.get('data_ip')
            node_identifier = f"{node_name}|{node_data_ip}"
            target_identifier = f"{target_name}|{target_data_ip}"
            
            if (node_name and node_data_ip and 
                node_identifier != target_identifier and 
                node_identifier not in seen_node_identifiers):
                sibling_nodes.append(node)
                seen_node_identifiers.add(node_identifier)
        
        return 'single', target_node, sibling_nodes, target_box_serial, []
    elif len(exact_matches) > 1:
        return 'multiple', None, [], None, exact_matches
    
    # Step 2: Try regex matches on node fields
    import re
    try:
        pattern = re.compile(node_name, re.IGNORECASE)
        regex_matches = []
        
        for node in all_nodes:
            # Check if pattern matches any of the node fields
            if (pattern.search(str(node.get('name', ''))) or
                pattern.search(str(node.get('serial_number', ''))) or
                pattern.search(str(node.get('mgmt_ip', ''))) or
                pattern.search(str(node.get('data_ip', '')))):
                regex_matches.append(node)
        
        if len(regex_matches) == 1:
            target_node = regex_matches[0]
            target_box_serial = target_node['box_serial']
            
            # Find siblings (deduplicated by node name and data IP)
            sibling_nodes = []
            seen_node_identifiers = set()
            target_name = target_node.get('name')
            target_data_ip = target_node.get('data_ip')
            box_nodes_list = box_nodes[target_box_serial]
            box_nodes_list.sort(key=lambda x: get_ip_last_octet(x.get('data_ip', '')))
            
            for node in box_nodes_list:
                node_name = node.get('name')
                node_data_ip = node.get('data_ip')
                node_identifier = f"{node_name}|{node_data_ip}"
                target_identifier = f"{target_name}|{target_data_ip}"
                
                if (node_name and node_data_ip and 
                    node_identifier != target_identifier and 
                    node_identifier not in seen_node_identifiers):
                    sibling_nodes.append(node)
                    seen_node_identifiers.add(node_identifier)
            
            return 'single', target_node, sibling_nodes, target_box_serial, []
        elif len(regex_matches) > 1:
            return 'multiple', None, [], None, regex_matches
    except re.error:
        # Invalid regex pattern, continue to box matching
        pass
    
    # Step 3: Try regex matches on box serial numbers
    try:
        pattern = re.compile(node_name, re.IGNORECASE)
        box_matched_nodes = []
        
        for box_serial, nodes_list in box_nodes.items():
            if pattern.search(str(box_serial)):
                box_matched_nodes.extend(nodes_list)
        
        if box_matched_nodes:
            return 'box_match', None, [], None, box_matched_nodes
    except re.error:
        pass
    
    return 'none', None, [], None, []


def format_output(target_node, sibling_nodes, box_serial):
    """Format the output according to the specified format."""
    if not target_node:
        return None
    
    # Determine index based on position
    index = "1" if target_node.get('position') == 'bottom' else "2"
    
    # Get model number (empty for now as it's not clearly defined in the data)
    model_number = ""
    
    # Get node type for display
    node_type = target_node.get('node_type', 'unknown').upper()
    
    # Define column widths
    left_col_width = 18
    right_col_width = 28
    
    # Helper function to create formatted lines
    def create_line(left_text, right_text=""):
        return f"| {left_text:<{left_col_width}} | {right_text:<{right_col_width}} |"
    
    def create_separator():
        return f"| {'-' * left_col_width} | {'-' * right_col_width} |"
    
    # Build output lines
    lines = [
        create_line("Node Replacement", f"FRU-___-{node_type}-___"),
        create_separator(),
        create_line("Tracking", "FedEx #"),
        create_line("Delivery ETA", ""),
        create_line("Room", ""),
        create_line("Rack", ""),
        create_line("Rack Unit", ""),
        create_line("Box S/N", box_serial or ""),
        create_line("----------------", f"--- {node_type.lower()} -------"),
        create_line("Index", str(index)),
        create_line("ModelNumber", model_number),
        create_line("name", target_node.get('name', '')),
        create_line("position", target_node.get('position', '')),
        create_line("IP", target_node.get('data_ip', '')),
        create_line("MGMT IP", target_node.get('mgmt_ip', '')),
        create_line("IPMI IP", target_node.get('ipmi_ip', '')),
        create_line("SerialNumber", target_node.get('serial_number', '')),
        create_line("MAC Address", target_node.get('mac_address', '')),
    ]
    
    # Add all sibling nodes
    if sibling_nodes:
        for i, sibling_node in enumerate(sibling_nodes, 1):
            sibling_type = sibling_node.get('node_type', 'unknown').lower()
            sibling_header = f"--- sibling {sibling_type} {i} -----" if len(sibling_nodes) > 1 else f"--- sibling {sibling_type} -------"
            lines.extend([
                create_line("----------------", sibling_header),
                create_line("name", sibling_node.get('name', '')),
                create_line("position", sibling_node.get('position', '')),
                create_line("IP", sibling_node.get('data_ip', '')),
                create_line("MGMT IP", sibling_node.get('mgmt_ip', '')),
                create_line("IPMI IP", sibling_node.get('ipmi_ip', '')),
                create_line("SerialNumber", sibling_node.get('serial_number', '')),
                create_line("MAC Address", sibling_node.get('mac_address', '')),
            ])
    
    return "\n".join(lines)


def format_drive_output(drive_info, node_info, sibling_nodes, case_number=None):
    """Format the drive (SSD/NVRAM) replacement output according to the specified format."""
    if not drive_info or not node_info:
        return None
    
    # Determine drive type and title
    drive_type = drive_info.get('drive_type', 'ssd')
    if drive_type == 'nvram':
        title = "NVRAM Replacement"
        fru_part = "FRU_..."  # Generic placeholder
    else:
        title = "SSD Replacement"  
        fru_part = "FRU_..."  # Generic placeholder
    
    # Determine location in box from management logs
    box_serial = node_info.get('box_serial', '')
    drive_serial = drive_info.get('serial', '')
    bundle_dir_full = node_info.get('bundle_dir_full', '')
    
    # Try to extract location from management logs using the dbox pattern
    location = "Unknown"
    if box_serial and drive_serial and bundle_dir_full:
        try:
            bundle_dir = Path(bundle_dir_full)
            extracted_location = extract_drive_location_from_logs(drive_serial, box_serial, bundle_dir)
            if extracted_location:
                location = extracted_location
            else:
                # Fallback to PCI switch information if available
                pci_position = drive_info.get('pci_switch_position', '').upper()
                pci_slot = drive_info.get('pci_switch_slot', 0)
                if pci_position and pci_slot:
                    location = f"{pci_position}-{pci_slot}"
        except (AttributeError, OSError):
            # Fallback to PCI switch information if path operations fail
            pci_position = drive_info.get('pci_switch_position', '').upper()
            pci_slot = drive_info.get('pci_switch_slot', 0)
            if pci_position and pci_slot:
                location = f"{pci_position}-{pci_slot}"
    
    # Determine index based on node position
    index = "1" if node_info.get('position') == 'bottom' else "2"
    
    # Get device path, removing /vast prefix if present
    device_path = drive_info.get('path', '')
    if device_path.startswith('/vast'):
        device_path = device_path.replace('/vast', '', 1)
    
    # Define column widths (NVRAMs need wider columns)
    if drive_type == 'nvram':
        left_col_width = 16
        right_col_width = 29  # 7 more characters for NVRAM
    else:
        left_col_width = 16
        right_col_width = 26
    
    # Helper function to create formatted lines
    def create_line(left_text, right_text=""):
        # Handle None values by converting them to empty strings
        left_text = left_text if left_text is not None else ""
        right_text = right_text if right_text is not None else ""
        return f"| {left_text:<{left_col_width}} | {right_text:<{right_col_width}} |"
    
    def create_separator():
        return f"| {'-' * left_col_width} | {'-' * right_col_width} |"
    
    # prepare case-number
    if case_number:
        # Format case number to 8 characters with leading zeros
        formatted_case = f"Case-{str(case_number).zfill(8)}"
    else:
        # Default case number
        formatted_case = "Case-000...."

    # Build output lines
    lines = [
        create_line(title, fru_part),
        create_separator(),
        create_line(formatted_case, "RMA-0000.... / FE-000....." ),
        create_line("Cluster", node_info.get('cluster_name', 'Unknown')),
        create_line("Tracking", "FedEx #  <TBD>"),
        create_line("Delivery ETA", ""),
        create_line("Room / Rack / RU", ""),
        create_line("DBox", node_info.get('box_serial', '')),
        create_line("Location in Box", location),
        create_line("Index", str(index)),
        create_line("DevicePath", device_path),
        create_line("ModelNumber", drive_info.get('model', '')),
        create_line("SerialNumber", drive_info.get('serial', '')),
        create_line("----------------", "--- associated dnode -----"),
        create_line("name", node_info.get('name', '')),
        create_line("position", node_info.get('position', '')),
        create_line("IP", node_info.get('data_ip', '')),
        create_line("MGMT IP", node_info.get('mgmt_ip', '')),
        create_line("IPMI IP", node_info.get('ipmi_ip', '')),
        create_line("SerialNumber", node_info.get('serial_number', '')),
        create_line("MAC Address", node_info.get('mac_address', '')),
    ]    
    
    # Add sibling nodes
    if sibling_nodes:
        for i, sibling_node in enumerate(sibling_nodes, 1):
            sibling_type = sibling_node.get('node_type', 'unknown').lower()
            sibling_header = f"-- sibling {sibling_type} {i} --" if len(sibling_nodes) > 1 else f"-- sibling {sibling_type} -----"
            lines.extend([
                create_line("----------------", sibling_header),
                create_line("name", sibling_node.get('name', '')),
                create_line("position", sibling_node.get('position', '')),
                create_line("IP", sibling_node.get('data_ip', '')),
                create_line("MGMT IP", sibling_node.get('mgmt_ip', '')),
                create_line("IPMI IP", sibling_node.get('ipmi_ip', '')),
                create_line("SerialNumber", sibling_node.get('serial_number', '')),
                create_line("MAC Address", sibling_node.get('mac_address', '')),
            ])
    
    return "\n".join(lines)


def list_available_nodes(bundle_dirs):
    """List all available nodes with their position within Box in tabular format."""
    box_nodes = {}  # Group nodes by Box serial number
    bundle_to_node = {}  # Map bundle_dir to node_info for path lookup
    
    # Calculate minimum unique paths for all bundle directories
    unique_paths = calculate_minimum_unique_paths(bundle_dirs)
    
    # Collect all node information and group by Box serial
    for bundle_dir in bundle_dirs:
        monitor_file = bundle_dir / 'monitor_result.json'
        if not monitor_file.exists():
            continue
            
        node_info = extract_node_info_from_monitor(monitor_file)
        if not node_info:
            continue
        
        # Extract hostname from systemctl output (preferred over system_product_name)
        hostname = extract_hostname_from_systemctl(bundle_dir)
        if hostname:
            node_info['name'] = hostname
            # Update node type with hostname information
            update_node_type_with_hostname(node_info, hostname)
        
        # Extract data IP from bundle directory
        data_ip = extract_data_ip_from_bundle(bundle_dir)
        node_info['data_ip'] = data_ip
        
        # Extract IPMI IP from bundle directory
        ipmi_ip = extract_ipmi_ip_from_bundle(bundle_dir)
        node_info['ipmi_ip'] = ipmi_ip
        
        # Extract create_time from BUNDLE_ARGS
        create_time = extract_create_time_from_bundle_args(bundle_dir)
        node_info['create_time'] = create_time
        
        # Add bundle path
        node_info['bundle_path'] = unique_paths.get(bundle_dir, str(bundle_dir))
        
        # Extract Box serial number from FRU file
        bundle_box_serial = None
        bundle_board_serial = None
        fru_file = bundle_dir / 'ipmitool' / 'ipmitool_fru_list.txt'
        if fru_file.exists():
            bundle_box_serial = extract_box_serial_from_fru(fru_file)
            bundle_board_serial = extract_board_serial_from_fru(fru_file)
        
        if data_ip and bundle_box_serial:
            node_info['box_serial'] = bundle_box_serial
            # Override system_serial_number with board serial if available
            if bundle_board_serial:
                node_info['serial_number'] = bundle_board_serial
            bundle_to_node[bundle_dir] = node_info
            
            # Group nodes by Box serial number
            if bundle_box_serial not in box_nodes:
                box_nodes[bundle_box_serial] = []
            box_nodes[bundle_box_serial].append(node_info)
    
    # Display available nodes in tabular format
    if not box_nodes:
        print("No nodes found with valid data", file=sys.stderr)
        return
    
    # Sort boxes by MGMT IP of first node in each group
    def get_first_node_mgmt_ip(box_serial_and_nodes):
        box_serial, nodes = box_serial_and_nodes
        if not nodes:
            return '0.0.0.0'  # Fallback for empty groups
        # Sort nodes by MGMT IP and take the first one
        sorted_nodes = sorted(nodes, key=lambda x: x.get('mgmt_ip', '0.0.0.0'))
        return sorted_nodes[0].get('mgmt_ip', '0.0.0.0')
    
    sorted_box_items = sorted(box_nodes.items(), key=get_first_node_mgmt_ip)
    
    print("Available Nodes:")
    print("=" * 240)
    
    # Define column widths
    col_widths = {
        'name': 18,
        'node_type': 6,
        'position': 12,
        'data_ip': 15,
        'mgmt_ip': 15,
        'ipmi_ip': 15,
        'node_serial': 28,
        'box_serial': 18,
        'mac_address': 18,
        'create_time': 19,
        'bundle_path': 25
    }
    
    # Create header
    header = f"| {'Name':<{col_widths['name']}} | {'Type':<{col_widths['node_type']}} | {'Position':<{col_widths['position']}} | {'Data IP':<{col_widths['data_ip']}} | {'MGMT IP':<{col_widths['mgmt_ip']}} | {'IPMI IP':<{col_widths['ipmi_ip']}} | {'Node S/N':<{col_widths['node_serial']}} | {'Box S/N':<{col_widths['box_serial']}} | {'MAC Address':<{col_widths['mac_address']}} | {'Create Time':<{col_widths['create_time']}} | {'Bundle Path':<{col_widths['bundle_path']}} |"
    separator = f"| {'-' * col_widths['name']} | {'-' * col_widths['node_type']} | {'-' * col_widths['position']} | {'-' * col_widths['data_ip']} | {'-' * col_widths['mgmt_ip']} | {'-' * col_widths['ipmi_ip']} | {'-' * col_widths['node_serial']} | {'-' * col_widths['box_serial']} | {'-' * col_widths['mac_address']} | {'-' * col_widths['create_time']} | {'-' * col_widths['bundle_path']} |"
    
    print(header)
    print(separator)
    
    # Display nodes grouped by box
    for box_serial, nodes in sorted_box_items:
        # Sort nodes within each box by position (bottom first, then by last octet of data IP)
        nodes.sort(key=lambda x: (x.get('position', '') != 'bottom', get_ip_last_octet(x.get('data_ip', ''))))
        
        # Add a visual separator between boxes (except for the first one)
        if box_serial != sorted_box_items[0][0]:  # Not the first box
            print(f"| {'-' * col_widths['name']} | {'-' * col_widths['node_type']} | {'-' * col_widths['position']} | {'-' * col_widths['data_ip']} | {'-' * col_widths['mgmt_ip']} | {'-' * col_widths['ipmi_ip']} | {'-' * col_widths['node_serial']} | {'-' * col_widths['box_serial']} | {'-' * col_widths['mac_address']} | {'-' * col_widths['create_time']} | {'-' * col_widths['bundle_path']} |")
        
        # Create rows for each node in this box
        for node in nodes:
            node_name = node.get('name', 'Unknown')
            node_type = node.get('node_type', 'unknown')
            position = node.get('position', 'Unknown')
            data_ip = node.get('data_ip', 'Unknown')
            mgmt_ip = node.get('mgmt_ip', 'Unknown')
            ipmi_ip = node.get('ipmi_ip', 'Unknown')
            node_serial = node.get('serial_number', 'Unknown')
            box_serial_val = node.get('box_serial', 'Unknown')
            mac_address = node.get('mac_address', 'Unknown')
            create_time = node.get('create_time', 'Unknown')
            bundle_path = node.get('bundle_path', 'Unknown')
            
            # Handle None values that might have been stored
            if node_name is None:
                node_name = 'Unknown'
            if node_type is None:
                node_type = 'unknown'
            if position is None:
                position = 'Unknown'
            if data_ip is None:
                data_ip = 'Unknown'
            if mgmt_ip is None:
                mgmt_ip = 'Unknown'
            if ipmi_ip is None:
                ipmi_ip = 'Unknown'
            if node_serial is None:
                node_serial = 'Unknown'
            if box_serial_val is None:
                box_serial_val = 'Unknown'
            if mac_address is None:
                mac_address = 'Unknown'
            if create_time is None:
                create_time = 'Unknown'
            if bundle_path is None:
                bundle_path = 'Unknown'
            
            # Convert node_type to uppercase after None check
            node_type = node_type.upper()
            
            row = f"| {node_name:<{col_widths['name']}} | {node_type:<{col_widths['node_type']}} | {position:<{col_widths['position']}} | {data_ip:<{col_widths['data_ip']}} | {mgmt_ip:<{col_widths['mgmt_ip']}} | {ipmi_ip:<{col_widths['ipmi_ip']}} | {node_serial:<{col_widths['node_serial']}} | {box_serial_val:<{col_widths['box_serial']}} | {mac_address:<{col_widths['mac_address']}} | {create_time:<{col_widths['create_time']}} | {bundle_path:<{col_widths['bundle_path']}} |"
            print(row)


def display_matched_nodes(matched_nodes, match_type="multiple"):
    """Display multiple matched nodes in a table format."""
    if not matched_nodes:
        return
    
    # Group nodes by box for better organization
    box_nodes = {}
    for node in matched_nodes:
        box_serial = node.get('box_serial', 'Unknown')
        if box_serial not in box_nodes:
            box_nodes[box_serial] = []
        box_nodes[box_serial].append(node)
    
    if match_type == "multiple":
        print("Multiple nodes match your query. Please be more specific:")
    elif match_type == "box_match":
        print("No direct node matches found. Showing nodes from matching boxes:")
    
    print("=" * 240)
    
    # Define column widths (same as list_available_nodes)
    col_widths = {
        'name': 18,
        'node_type': 6,
        'position': 12,
        'data_ip': 15,
        'mgmt_ip': 15,
        'ipmi_ip': 15,
        'node_serial': 28,
        'box_serial': 18,
        'mac_address': 18,
        'create_time': 19,
        'bundle_path': 25
    }
    
    # Create header
    header = f"| {'Name':<{col_widths['name']}} | {'Type':<{col_widths['node_type']}} | {'Position':<{col_widths['position']}} | {'Data IP':<{col_widths['data_ip']}} | {'MGMT IP':<{col_widths['mgmt_ip']}} | {'IPMI IP':<{col_widths['ipmi_ip']}} | {'Node S/N':<{col_widths['node_serial']}} | {'Box S/N':<{col_widths['box_serial']}} | {'MAC Address':<{col_widths['mac_address']}} | {'Create Time':<{col_widths['create_time']}} | {'Bundle Path':<{col_widths['bundle_path']}} |"
    separator = f"| {'-' * col_widths['name']} | {'-' * col_widths['node_type']} | {'-' * col_widths['position']} | {'-' * col_widths['data_ip']} | {'-' * col_widths['mgmt_ip']} | {'-' * col_widths['ipmi_ip']} | {'-' * col_widths['node_serial']} | {'-' * col_widths['box_serial']} | {'-' * col_widths['mac_address']} | {'-' * col_widths['create_time']} | {'-' * col_widths['bundle_path']} |"
    
    print(header)
    print(separator)
    
    # Sort boxes by MGMT IP of first node in each group
    def get_first_node_mgmt_ip(box_serial_and_nodes):
        box_serial, nodes = box_serial_and_nodes
        if not nodes:
            return '0.0.0.0'
        sorted_nodes = sorted(nodes, key=lambda x: x.get('mgmt_ip', '0.0.0.0'))
        return sorted_nodes[0].get('mgmt_ip', '0.0.0.0')
    
    sorted_box_items = sorted(box_nodes.items(), key=get_first_node_mgmt_ip)
    
    # Display nodes grouped by box
    for i, (box_serial, nodes) in enumerate(sorted_box_items):
        # Sort nodes within each box by position (bottom first, then by last octet of data IP)
        nodes.sort(key=lambda x: (x.get('position', '') != 'bottom', get_ip_last_octet(x.get('data_ip', ''))))
        
        # Add a visual separator between boxes (except for the first one)
        if i > 0:
            print(f"| {'-' * col_widths['name']} | {'-' * col_widths['node_type']} | {'-' * col_widths['position']} | {'-' * col_widths['data_ip']} | {'-' * col_widths['mgmt_ip']} | {'-' * col_widths['ipmi_ip']} | {'-' * col_widths['node_serial']} | {'-' * col_widths['box_serial']} | {'-' * col_widths['mac_address']} | {'-' * col_widths['create_time']} | {'-' * col_widths['bundle_path']} |")
        
        # Create rows for each node in this box
        for node in nodes:
            node_name = node.get('name', 'Unknown')
            node_type = node.get('node_type', 'unknown')
            position = node.get('position', 'Unknown')
            data_ip = node.get('data_ip', 'Unknown')
            mgmt_ip = node.get('mgmt_ip', 'Unknown')
            ipmi_ip = node.get('ipmi_ip', 'Unknown')
            node_serial = node.get('serial_number', 'Unknown')
            box_serial_val = node.get('box_serial', 'Unknown')
            mac_address = node.get('mac_address', 'Unknown')
            create_time = node.get('create_time', 'Unknown')
            bundle_path = node.get('bundle_path', 'Unknown')
            
            # Handle None values that might have been stored
            if node_name is None:
                node_name = 'Unknown'
            if node_type is None:
                node_type = 'unknown'
            if position is None:
                position = 'Unknown'
            if data_ip is None:
                data_ip = 'Unknown'
            if mgmt_ip is None:
                mgmt_ip = 'Unknown'
            if ipmi_ip is None:
                ipmi_ip = 'Unknown'
            if node_serial is None:
                node_serial = 'Unknown'
            if box_serial_val is None:
                box_serial_val = 'Unknown'
            if mac_address is None:
                mac_address = 'Unknown'
            if create_time is None:
                create_time = 'Unknown'
            if bundle_path is None:
                bundle_path = 'Unknown'
            
            # Convert node_type to uppercase after None check
            node_type = node_type.upper()
            
            row = f"| {node_name:<{col_widths['name']}} | {node_type:<{col_widths['node_type']}} | {position:<{col_widths['position']}} | {data_ip:<{col_widths['data_ip']}} | {mgmt_ip:<{col_widths['mgmt_ip']}} | {ipmi_ip:<{col_widths['ipmi_ip']}} | {node_serial:<{col_widths['node_serial']}} | {box_serial_val:<{col_widths['box_serial']}} | {mac_address:<{col_widths['mac_address']}} | {create_time:<{col_widths['create_time']}} | {bundle_path:<{col_widths['bundle_path']}} |"
            print(row)


def find_sibling_nodes_for_drive(target_node_info, bundle_dirs):
    """Find sibling nodes for a drive's host node."""
    if not target_node_info or not target_node_info.get('box_serial'):
        return []
    
    target_box_serial = target_node_info['box_serial']
    target_name = target_node_info.get('name')
    target_data_ip = target_node_info.get('data_ip')
    sibling_nodes = []
    seen_node_identifiers = set()
    
    # Calculate minimum unique paths for all bundle directories
    unique_paths = calculate_minimum_unique_paths(bundle_dirs)
    
    for bundle_dir in bundle_dirs:
        monitor_file = bundle_dir / 'monitor_result.json'
        if not monitor_file.exists():
            continue
            
        node_info = extract_node_info_from_monitor(monitor_file)
        if not node_info:
            continue
        
        # Extract hostname from systemctl output
        hostname = extract_hostname_from_systemctl(bundle_dir)
        if hostname:
            node_info['name'] = hostname
            # Update node type with hostname information
            update_node_type_with_hostname(node_info, hostname)
        
        # Extract data IP from bundle directory
        data_ip = extract_data_ip_from_bundle(bundle_dir)
        node_info['data_ip'] = data_ip
        
        # Extract IPMI IP from bundle directory
        ipmi_ip = extract_ipmi_ip_from_bundle(bundle_dir)
        node_info['ipmi_ip'] = ipmi_ip
        
        # Add bundle path
        node_info['bundle_path'] = unique_paths.get(bundle_dir, str(bundle_dir))
        
        # Extract create_time from BUNDLE_ARGS
        create_time = extract_create_time_from_bundle_args(bundle_dir)
        node_info['create_time'] = create_time
        
        # Extract Box serial number from FRU file
        fru_file = bundle_dir / 'ipmitool' / 'ipmitool_fru_list.txt'
        if fru_file.exists():
            bundle_box_serial = extract_box_serial_from_fru(fru_file)
            bundle_board_serial = extract_board_serial_from_fru(fru_file)
            node_info['box_serial'] = bundle_box_serial
            # Override system_serial_number with board serial if available
            if bundle_board_serial:
                node_info['serial_number'] = bundle_board_serial
            
            # Get node identifiers for deduplication
            node_name = node_info.get('name')
            node_data_ip = node_info.get('data_ip')
            node_identifier = f"{node_name}|{node_data_ip}"
            target_identifier = f"{target_name}|{target_data_ip}"
            
            # Check if this node is in the same box but is not the target node
            # and we haven't already seen this physical node
            if (bundle_box_serial == target_box_serial and 
                node_name and node_data_ip and
                node_identifier != target_identifier and
                node_identifier not in seen_node_identifiers and
                node_info.get('node_type') == 'dnode'):
                
                sibling_nodes.append(node_info)
                seen_node_identifiers.add(node_identifier)
    
    # Sort siblings by last octet of data IP
    sibling_nodes.sort(key=lambda x: get_ip_last_octet(x.get('data_ip', '')))
    return sibling_nodes


def main():
    try:
        main_impl()
    except BrokenPipeError:
        # Handle broken pipe gracefully (occurs when output is piped to head, less, etc.)
        import sys
        sys.stderr.close()
        sys.stdout.close()
        sys.exit(0)
    except KeyboardInterrupt:
        # Handle Ctrl+C gracefully
        sys.exit(1)


def main_impl():
    # Set up argument parsing
    parser = argparse.ArgumentParser(
        description='Extract node or drive (SSD/NVRAM) information from bundle directories',
        epilog='''
Examples:
  %(prog)s                                            # List all available nodes
  %(prog)s dnode-3-100                                # Show specific node (exact match)
  %(prog)s 'dnode.*100'                               # Regex match nodes
  %(prog)s --ssd PHAC2070006C30PGGN                   # Show SSD replacement info
  %(prog)s --nvram PHAC2070006C30PGGN                 # Show NVRAM replacement info
  %(prog)s --drive PHAC2070006C30PGGN                 # Show drive replacement info (SSD or NVRAM)
  %(prog)s --case 00090597 --drive PHAC207000DN30PGGN # Show drive replacement with case number
  %(prog)s --verbose --drive SERIAL123                # Show detailed debugging information
        ''',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('node_name', nargs='?', help='Node name to search for (regex supported)')
    
    # Create mutually exclusive group for drive serial arguments (all mean the same thing)
    drive_group = parser.add_mutually_exclusive_group()
    drive_group.add_argument('--ssd', metavar='DRIVE_SERIAL', help='Drive serial number to search for (DNodes only)')
    drive_group.add_argument('--drive', metavar='DRIVE_SERIAL', help='Drive serial number to search for (DNodes only)')
    drive_group.add_argument('--nvram', metavar='DRIVE_SERIAL', help='Drive serial number to search for (DNodes only)')
    drive_group.add_argument('--scm', metavar='DRIVE_SERIAL', help='Drive serial number to search for (DNodes only)')
    
    # Add verbose logging option
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose logging for debugging')
    
    # Add case number option
    parser.add_argument('--case', metavar='CASE_NUMBER', help='Case number to include in the output')
    
    args = parser.parse_args()
    
    # Configure logging based on verbose flag
    if args.verbose:
        logging.basicConfig(
            level=logging.DEBUG,
            format='[VERBOSE] %(message)s',
            stream=sys.stderr
        )
        logging.debug("Verbose logging enabled")
    else:
        logging.basicConfig(level=logging.WARNING)
    
    # Find all bundle directories first
    logging.debug("Starting bundle directory discovery...")
    all_bundle_dirs = find_bundle_directories()
    if not all_bundle_dirs:
        logging.debug("No bundle directories found")
        print("Error: No bundle directories found", file=sys.stderr)
        sys.exit(1)
    
    # Filter to keep only the latest bundle per node
    logging.debug("Filtering to latest bundles per node...")
    bundle_dirs = filter_latest_bundles_per_node(all_bundle_dirs)
    if not bundle_dirs:
        logging.debug("No valid bundles after filtering")
        print("Error: No valid bundle directories found after filtering", file=sys.stderr)
        sys.exit(1)
    
    # Handle drive mode (SSD/NVRAM/SCM)
    drive_serial = args.ssd or args.drive or args.nvram or args.scm
    if drive_serial:
        drive_info, node_info, bundle_dir = find_drive_in_bundles(drive_serial, bundle_dirs)
        
        if not drive_info:
            print(f"Error: Could not find drive with serial number '{drive_serial}'", file=sys.stderr)
            sys.exit(1)
            
        if not node_info:
            print(f"Error: Could not find node information for drive '{drive_serial}'", file=sys.stderr)
            sys.exit(1)
            
        if node_info.get('node_type') != 'dnode':
            print(f"Error: Drive '{drive_serial}' is not in a DNode. Drive replacement only works with DNodes.", file=sys.stderr)
            sys.exit(1)
        
        # Find sibling nodes
        sibling_nodes = find_sibling_nodes_for_drive(node_info, bundle_dirs)
        
        # Format and print drive replacement output
        output = format_drive_output(drive_info, node_info, sibling_nodes)
        if output:
            print(output)
        else:
            print("Error: Could not format drive output", file=sys.stderr)
            sys.exit(1)
        return
    
    # Handle node mode (original functionality)
    if not args.node_name:
        # No arguments provided, list all available nodes
        list_available_nodes(bundle_dirs)
        return
    
    # Find node information using enhanced matching
    match_type, target_node, sibling_nodes, box_serial, matched_nodes = find_node_in_bundles(args.node_name, bundle_dirs)
    
    if match_type == 'single':
        # Single match found, format and print output
        output = format_output(target_node, sibling_nodes, box_serial)
        if output:
            print(output)
        else:
            print("Error: Could not format output", file=sys.stderr)
            sys.exit(1)
    elif match_type == 'multiple':
        # Multiple matches found, display list
        display_matched_nodes(matched_nodes, "multiple")
        sys.exit(0)
    elif match_type == 'box_match':
        # Box serial matches found, display list
        display_matched_nodes(matched_nodes, "box_match")
        sys.exit(0)
    else:
        # No matches found
        print(f"Error: Could not find any matches for '{args.node_name}'", file=sys.stderr)
        print("Try using regex patterns or check available nodes with no arguments", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

