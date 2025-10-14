#!/usr/bin/env python3
"""
RMA Preparation Tool

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


This is a refactored version of rma_prep.py that follows Luna's architectural patterns:
- Object-oriented design with cached properties
- Hierarchical data model (Cluster -> Bundle -> Node -> Device)
- Separation of data loading from presentation
- Lazy evaluation for performance
"""

import sys
import os
import json
import re
import argparse
import logging
import gzip
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Union
from functools import cached_property

# Try to import vapi for PDB support (Luna protobuf files)
try:
    from vapi.commander import STR_TO_TYPE_ID, Commander  # type: ignore
    HAS_VAPI = True
except ImportError:
    HAS_VAPI = False
    logging.debug("vapi module not available - PDB support disabled, using fallback sources")


# ============================================================================
# Utility Decorators (Luna-style)
# ============================================================================

def cached_method(func):
    """Cache method results (similar to Luna's locking_cache)"""
    cache_attr = f'_cached_{func.__name__}'
    
    def wrapper(self, *args, **kwargs):
        if not hasattr(self, cache_attr):
            setattr(self, cache_attr, {})
        cache = getattr(self, cache_attr)
        
        key = (args, tuple(sorted(kwargs.items())))
        if key not in cache:
            cache[key] = func(self, *args, **kwargs)
        return cache[key]
    
    return wrapper


# ============================================================================
# PDB (Protobuf Database) Support - Luna-style
# ============================================================================

class PDB:
    """Read and parse PDB (protobuf) files from bundle directories
    
    This provides Luna-style access to protobuf data when available.
    Falls back gracefully when vapi module is not available.
    """
    
    def __init__(self, path: Optional[Path] = None):
        self._path = path
        self._cache = {}
    
    def __repr__(self):
        return f'PDB({self._path or "None"})'
    
    def __bool__(self):
        return bool(self._path and self._path.exists())
    
    @staticmethod
    def find_pdb_folder(bundle_path: Path) -> Optional[Path]:
        """Find the PDB directory in a bundle (usually pdb/<timestamp>/)"""
        pdb_dir = bundle_path / 'pdb'
        if not pdb_dir.exists():
            return None
        
        # Find timestamp folders (format: YYYYMMDD_HHMMSS)
        pdb_folders = [f for f in pdb_dir.iterdir() 
                      if f.is_dir() and re.match(r'\d{8}_\d{6}', f.name)]
        
        if not pdb_folders:
            return None
        
        # Return the latest one
        return max(pdb_folders, key=lambda f: f.name)
    
    def _read_raw_data(self, type_name: str) -> Optional[bytes]:
        """Read raw protobuf data from a PDB file"""
        if not self._path or not self._path.exists():
            return None
        
        # Look for files matching the type name (e.g., DriveType.gz, DriveType)
        file_paths = list(self._path.glob(f'{type_name}*'))
        if not file_paths:
            return None
        
        file_path = file_paths[0]
        
        # Handle gzipped or regular files
        file_open = gzip.open if file_path.suffix == '.gz' else open
        
        try:
            with file_open(file_path, 'rb') as f:
                return f.read()
        except (FileNotFoundError, IOError, OSError):
            return None
    
    def get(self, type_name: str) -> Optional[List]:
        """Get parsed protobuf objects of a specific type
        
        Returns a list of protobuf objects if vapi is available, None otherwise.
        """
        if not HAS_VAPI:
            return None
        
        if type_name in self._cache:
            return self._cache[type_name]
        
        raw_data = self._read_raw_data(type_name)
        if not raw_data:
            return None
        
        try:
            file_type_id = STR_TO_TYPE_ID.get(type_name)
            if file_type_id is None:
                return None
            
            objects = list(Commander.parse_objects(file_type_id, raw_data))
            self._cache[type_name] = objects
            return objects
        except Exception as e:
            logging.debug(f"Failed to parse PDB {type_name}: {e}")
            return None
    
    @cached_property
    def drive(self) -> Optional[List]:
        """Get all Drive objects from PDB"""
        return self.get('DriveType')
    
    @cached_property
    def nvram(self) -> Optional[List]:
        """Get all NVRAM objects from PDB"""
        return self.get('NVRAMType')
    
    @cached_property
    def dnode(self) -> Optional[List]:
        """Get all DNode objects from PDB"""
        return self.get('DNodeType')
    
    @cached_property
    def dbox(self) -> Optional[List]:
        """Get all DBox objects from PDB"""
        return self.get('DBoxType')
    
    def find_device_by_serial(self, serial: str):
        """Find a device (drive or nvram) by serial number"""
        for device_list in [self.drive, self.nvram]:
            if device_list:
                for device in device_list:
                    if hasattr(device, 'device_proto') and device.device_proto.serial == serial:
                        return device
        return None


class PlatformConfig:
    """Parse config/platform.config file (Luna's source for node type/IP)"""
    
    NODE_INFO_REGEX = re.compile(
        r'(?:.|\n)*ip: \"(?P<node_ip>.*)\"(?:.|\n)*port: (?P<node_port>\d+)'
        r'(?:.|\n)*node_type: \"(?P<node_type>.*)\"(?:.|\n)*'
    )
    NODE_ARCH_REGEX = re.compile(r'node_architecture: "(.*?)"')
    DNODE_INDEX_REGEX = re.compile(r'dnode_index: "(.*?)"')
    
    def __init__(self, config_file: Path):
        self.config_file = config_file
        self.node_ip = None
        self.node_port = None
        self.node_type = None
        self.node_architecture = None
        self.dnode_index = None
        
        if not config_file.exists():
            return
        
        try:
            content = config_file.read_text(encoding='utf-8')
            
            # Parse node info
            match = self.NODE_INFO_REGEX.match(content)
            if match:
                self.node_ip = match.group('node_ip')
                self.node_port = match.group('node_port')
                self.node_type = match.group('node_type')
            
            # Parse architecture
            arch_match = self.NODE_ARCH_REGEX.search(content)
            if arch_match:
                self.node_architecture = arch_match.group(1)
            
            # Parse dnode index
            index_match = self.DNODE_INDEX_REGEX.search(content)
            if index_match:
                self.dnode_index = index_match.group(1)
        
        except (IOError, OSError) as e:
            logging.debug(f"Failed to read platform.config: {e}")


# ============================================================================
# Core Data Model (Luna-inspired hierarchy)
# ============================================================================

class NetworkInfo:
    """Network configuration for a node"""
    def __init__(self, mgmt_ip=None, ipmi_ip=None, mac_address=None, data_ip=None):
        self.mgmt_ip = mgmt_ip
        self.ipmi_ip = ipmi_ip
        self.mac_address = mac_address
        self.data_ip = data_ip


class Device:
    """Base device class (SSD or NVRAM)"""
    
    def __init__(self, serial: str, bundle: 'Bundle', pdb_obj=None):
        self.serial = serial
        self._bundle = bundle
        self._pdb_obj = pdb_obj
        self._raw_data = None
    
    def __repr__(self):
        return f'<{self.__class__.__name__}-{self.serial}>'
    
    def __eq__(self, other):
        return self.serial == other.serial
    
    def __hash__(self):
        return hash(self.serial)
    
    @cached_property
    def pdb_device(self):
        """Get PDB protobuf object for this device (Luna's primary source)"""
        if self._pdb_obj:
            return self._pdb_obj
        
        if self._bundle.pdb:
            return self._bundle.pdb.find_device_by_serial(self.serial)
        
        return None
    
    @cached_property
    def data(self) -> Optional[Dict[str, Any]]:
        """Load device data from bundle (lazy)
        
        Priority:
        1. PDB (protobuf) - Luna's authoritative source
        2. nvme_cli_list.json - current exposure status
        3. nvme_list.json - fallback
        """
        result = {}
        
        # First: Try PDB (Luna's primary source)
        if self.pdb_device:
            try:
                device_proto = self.pdb_device.device_proto
                result['serial'] = device_proto.serial
                result['model'] = device_proto.model if hasattr(device_proto, 'model') else None
                result['pci_switch_position'] = device_proto.pci_switch_position if hasattr(device_proto, 'pci_switch_position') else None
                result['pci_switch_slot'] = device_proto.pci_switch_slot if hasattr(device_proto, 'pci_switch_slot') else None
                result['state'] = str(device_proto.state) if hasattr(device_proto, 'state') else None
                result['attached'] = device_proto.attached if hasattr(device_proto, 'attached') else None
                
                # Try to get path from nvme_cli_list (exposed devices)
                path = self._get_device_path_from_nvme_cli()
                if path:
                    result['path'] = path
                
                logging.debug(f"Device {self.serial}: loaded from PDB")
                return result
            except Exception as e:
                logging.debug(f"Device {self.serial}: PDB read failed ({e}), falling back")
        
        # Second: Try nvme_cli_list.json
        nvme_cli_file = self._bundle.path / 'nvme_cli_list.json'
        if nvme_cli_file.exists():
            try:
                with open(nvme_cli_file, 'r') as f:
                    nvme_data = json.load(f)
                
                all_drives = nvme_data.get('drives', []) + nvme_data.get('nvrams', [])
                for drive in all_drives:
                    if drive.get('serial') == self.serial:
                        logging.debug(f"Device {self.serial}: loaded from nvme_cli_list.json")
                        return drive
            except (json.JSONDecodeError, IOError):
                pass
        
        # Third: Fallback to nvme_list.json
        nvme_list_file = self._bundle.path / 'nvme_list.json'
        if nvme_list_file.exists():
            try:
                with open(nvme_list_file, 'r') as f:
                    nvme_data = json.load(f)
                
                devices = nvme_data.get('Devices', [])
                for device in devices:
                    if device.get('SerialNumber') == self.serial:
                        logging.debug(f"Device {self.serial}: loaded from nvme_list.json")
                        return {
                            'serial': device.get('SerialNumber'),
                            'model': device.get('ModelNumber'),
                            'path': device.get('DevicePath'),
                            'size': device.get('PhysicalSize'),
                            'firmware_rev': device.get('Firmware'),
                            'index': device.get('Index'),
                        }
            except (json.JSONDecodeError, IOError):
                pass
        
        return result if result else None
    
    def _get_device_path_from_nvme_cli(self) -> Optional[str]:
        """Get device path from nvme_cli_list.json"""
        nvme_cli_file = self._bundle.path / 'nvme_cli_list.json'
        if not nvme_cli_file.exists():
            return None
        
        try:
            with open(nvme_cli_file, 'r') as f:
                nvme_data = json.load(f)
            
            all_drives = nvme_data.get('drives', []) + nvme_data.get('nvrams', [])
            for drive in all_drives:
                if drive.get('serial') == self.serial:
                    return drive.get('path')
        except (json.JSONDecodeError, IOError):
            pass
        
        return None
    
    @cached_property
    def model(self) -> str:
        return self.data.get('model', 'Unknown') if self.data else 'Unknown'
    
    @cached_property
    def path(self) -> str:
        return self.data.get('path', 'Unknown') if self.data else 'Unknown'
    
    @cached_property
    def size(self) -> Optional[str]:
        return self.data.get('size') if self.data else None
    
    @cached_property
    def pci_switch_position(self) -> Optional[str]:
        return self.data.get('pci_switch_position') if self.data else None
    
    @cached_property
    def pci_switch_slot(self) -> Optional[int]:
        return self.data.get('pci_switch_slot') if self.data else None
    
    @cached_property
    def location_in_box(self) -> str:
        """Calculate location from PCI switch info"""
        if self.pci_switch_position and self.pci_switch_slot:
            return f"{self.pci_switch_position}-{self.pci_switch_slot}"
        return 'Unknown'
    
    @cached_property
    def drive_type(self) -> str:
        """Determine if this is SSD or NVRAM"""
        model_lower = self.model.lower()
        path_lower = self.path.lower()
        
        nvram_indicators = ['optane', 'dcpmm', 'ssdpe21k', 'scm', 'nvdimm', 'pmem', 'pascari']
        
        for indicator in nvram_indicators:
            if indicator in model_lower or indicator in path_lower:
                return 'nvram'
        
        return 'ssd'
    
    @cached_property
    def node(self) -> Optional['Node']:
        """Get the node this device belongs to"""
        return self._bundle.node


class Node:
    """Represents a compute or data node"""
    
    def __init__(self, bundle: 'Bundle'):
        self._bundle = bundle
    
    def __repr__(self):
        return f'<{self.__class__.__name__}-{self.name}>'
    
    @cached_property
    def platform_config(self) -> Optional[PlatformConfig]:
        """Load config/platform.config (Luna's source for node type/IP)"""
        config_file = self._bundle.path / 'config' / 'platform.config'
        if config_file.exists():
            return PlatformConfig(config_file)
        return None
    
    @cached_property
    def guid(self) -> Optional[str]:
        """Read self.guid file (Luna's node identifier)"""
        guid_file = self._bundle.path / 'self.guid'
        if guid_file.exists():
            try:
                return guid_file.read_text().strip()
            except (IOError, OSError):
                pass
        return None
    
    @cached_property
    def system_guid(self) -> Optional[str]:
        """Read system.guid file (Luna's system identifier)"""
        guid_file = self._bundle.path / 'system.guid'
        if guid_file.exists():
            try:
                return guid_file.read_text().strip()
            except (IOError, OSError):
                pass
        return None
    
    @cached_property
    def pdb_node(self):
        """Get PDB protobuf object for this node"""
        if not self._bundle.pdb or not self.guid:
            return None
        
        # Try to find the node in PDB by GUID
        for node_list in [self._bundle.pdb.dnode]:
            if node_list:
                for node_obj in node_list:
                    if hasattr(node_obj, 'base_proto'):
                        node_guid = str(node_obj.base_proto.guid)
                        if node_guid == self.guid:
                            return node_obj
        return None
    
    @cached_property
    def _monitor_data(self) -> Optional[Dict[str, Any]]:
        """Load monitor_result.json (fallback source)"""
        monitor_file = self._bundle.path / 'monitor_result.json'
        if not monitor_file.exists():
            return None
        
        try:
            with open(monitor_file, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return None
    
    @cached_property
    def _node_info(self) -> Dict[str, Any]:
        """Extract node info from monitor data"""
        if not self._monitor_data:
            return {}
        
        node_info = self._monitor_data.get('node', {}).get('info', {})
        return {
            'name': node_info.get('system_product_name', ''),
            'position': node_info.get('position', ''),
            'serial_number': node_info.get('system_serial_number', ''),
        }
    
    @cached_property
    def hostname(self) -> Optional[str]:
        """Extract hostname from systemctl output"""
        systemctl_file = self._bundle.path / 'systemctl_output' / 'systemctl_status.txt'
        if not systemctl_file.exists():
            return None
        
        try:
            with open(systemctl_file, 'r') as f:
                first_line = f.readline().strip()
            
            if first_line.startswith('●'):
                return first_line[1:].strip()
        except (IOError, OSError):
            pass
        
        return None
    
    @cached_property
    def name(self) -> str:
        """Node name (hostname preferred, fallback to system_product_name)"""
        return self.hostname or self._node_info.get('name', 'Unknown')
    
    @cached_property
    def serial_number(self) -> str:
        """Board serial number from FRU or system serial"""
        # Check FRU for board serial
        fru_file = self._bundle.path / 'ipmitool' / 'ipmitool_fru_list.txt'
        if fru_file.exists():
            board_serial = self._extract_board_serial_from_fru(fru_file)
            if board_serial:
                return board_serial
        
        return self._node_info.get('serial_number', 'Unknown')
    
    @cached_property
    def position(self) -> str:
        return self._node_info.get('position', 'Unknown')
    
    @cached_property
    def network(self) -> NetworkInfo:
        """Network configuration (lazy)
        
        Priority:
        1. config/platform.config for data IP (Luna's source)
        2. monitor_result.json for MGMT IP and MAC
        3. ipmitool for IPMI IP
        """
        mgmt_ip = None
        mac_address = None
        data_ip = None
        
        # First: Try to get data IP from platform.config (Luna's source)
        if self.platform_config and self.platform_config.node_ip:
            data_ip = self.platform_config.node_ip
            logging.debug(f"Node {self.name}: data IP from platform.config")
        
        # Second: Fall back to monitor_result.json
        if self._monitor_data:
            nics = self._monitor_data.get('nics', {})
            data_ips = []
            
            for nic_name, nic_info in nics.items():
                nic_data = nic_info.get('info', {})
                address = nic_data.get('address', '')
                nic_mac = nic_data.get('mac_address', '')
                
                # Management IP (10.x.x.x)
                if address and address.startswith('10.') and not mgmt_ip:
                    mgmt_ip = address
                    mac_address = nic_mac
                
                # Data IP (172.16.x.x) - only if not already set from platform.config
                if address and address.startswith('172.16.'):
                    data_ips.append(address)
            
            # Use monitor data for data_ip only if platform.config didn't provide it
            if not data_ip and data_ips:
                data_ip = min(data_ips)
                logging.debug(f"Node {self.name}: data IP from monitor_result.json")
        
        ipmi_ip = self._extract_ipmi_ip()
        
        return NetworkInfo(
            mgmt_ip=mgmt_ip,
            ipmi_ip=ipmi_ip,
            mac_address=mac_address,
            data_ip=data_ip
        )
    
    @cached_property
    def node_type(self) -> str:
        """Determine node type (dnode/cnode)
        
        Priority:
        1. config/platform.config (Luna's authoritative source)
        2. hostname parsing
        3. data IP last octet
        """
        # First: check platform.config (Luna's source)
        if self.platform_config and self.platform_config.node_type:
            node_type = self.platform_config.node_type.lower()
            if 'dnode' in node_type or 'data' in node_type:
                logging.debug(f"Node {self.name}: type 'dnode' from platform.config")
                return 'dnode'
            elif 'cnode' in node_type or 'control' in node_type or 'compute' in node_type:
                logging.debug(f"Node {self.name}: type 'cnode' from platform.config")
                return 'cnode'
        
        # Second: check hostname
        if self.hostname:
            hostname_lower = self.hostname.lower()
            if 'dnode' in hostname_lower:
                logging.debug(f"Node {self.name}: type 'dnode' from hostname")
                return 'dnode'
            elif 'cnode' in hostname_lower:
                logging.debug(f"Node {self.name}: type 'cnode' from hostname")
                return 'cnode'
        
        # Third: fallback to data IP last octet
        if self.network.data_ip:
            try:
                last_octet = int(self.network.data_ip.split('.')[-1])
                node_type = 'dnode' if last_octet >= 100 else 'cnode'
                logging.debug(f"Node {self.name}: type '{node_type}' from data IP")
                return node_type
            except (ValueError, IndexError):
                pass
        
        return 'unknown'
    
    @cached_property
    def box_serial(self) -> Optional[str]:
        """Box serial number from dmidecode (preferred) or FRU (fallback)"""
        # First: Try dmidecode.txt (more reliable for CBox serial)
        dmidecode_file = self._bundle.path / 'dmidecode.txt'
        if dmidecode_file.exists():
            serial = self._extract_box_serial_from_dmidecode(dmidecode_file)
            if serial and serial != 'Uninitialized':
                return serial
        
        # Second: Fall back to FRU
        fru_file = self._bundle.path / 'ipmitool' / 'ipmitool_fru_list.txt'
        if fru_file.exists():
            return self._extract_box_serial_from_fru(fru_file)
        return None
    
    @cached_property
    def manufacturer_id(self) -> Optional[str]:
        """Manufacturer ID from mc_info"""
        mc_info_file = self._bundle.path / 'ipmitool' / 'ipmitool_mc_info.txt'
        if mc_info_file.exists():
            return self._extract_manufacturer_id(mc_info_file)
        return None
    
    @cached_property
    def product_id(self) -> Optional[str]:
        """Product ID from mc_info"""
        mc_info_file = self._bundle.path / 'ipmitool' / 'ipmitool_mc_info.txt'
        if mc_info_file.exists():
            return self._extract_product_id(mc_info_file)
        return None
    
    @cached_property
    def nics(self) -> Optional[str]:
        """NIC cards from ibdev2netdev.txt
        
        Returns a comma-separated list of NIC types (e.g., "CX6, CX7")
        in PCI slot order.
        """
        ibdev_file = self._bundle.path / 'ibdev2netdev.txt'
        if ibdev_file.exists():
            return self._extract_nics_from_ibdev(ibdev_file)
        return None
    
    @cached_property
    def model(self) -> str:
        """Node model information
        
        Returns formatted Manufacturer and Product IDs if no explicit model is available.
        """
        # If we have explicit model info, return it (future enhancement)
        # For now, return Mfr/Prod IDs if available
        if self.manufacturer_id and self.product_id:
            return f"Mfr: {self.manufacturer_id}; Prod: {self.product_id}"
        return ""
    
    @cached_property
    def devices(self) -> List[Device]:
        """List all devices on this node (lazy)
        
        Priority:
        1. PDB (protobuf) - Luna's authoritative device list
        2. nvme_cli_list.json - fallback
        """
        devices = []
        
        # First: Try PDB (Luna's source)
        if self._bundle.pdb and self.pdb_node:
            try:
                # Get all devices from PDB
                all_pdb_devices = []
                for device_list in [self._bundle.pdb.drive, self._bundle.pdb.nvram]:
                    if device_list:
                        all_pdb_devices.extend(device_list)
                
                # Filter devices that belong to this node
                if self.guid:
                    for pdb_device in all_pdb_devices:
                        if hasattr(pdb_device, 'device_proto') and hasattr(pdb_device, 'base_proto'):
                            # Check if device belongs to this node
                            # Devices can be parented to DNode or DBox
                            is_native = False
                            
                            if hasattr(self.pdb_node, 'dnode_index') and hasattr(pdb_device.device_proto, 'native_dnode'):
                                is_native = pdb_device.device_proto.native_dnode == self.pdb_node.dnode_index
                            
                            if is_native:
                                serial = pdb_device.device_proto.serial
                                devices.append(Device(serial, self._bundle, pdb_obj=pdb_device))
                
                if devices:
                    logging.debug(f"Node {self.name}: loaded {len(devices)} devices from PDB")
                    return devices
            except Exception as e:
                logging.debug(f"Node {self.name}: PDB device loading failed ({e}), falling back")
        
        # Second: Fall back to nvme_cli_list.json
        nvme_cli_file = self._bundle.path / 'nvme_cli_list.json'
        if nvme_cli_file.exists():
            try:
                with open(nvme_cli_file, 'r') as f:
                    nvme_data = json.load(f)
                
                drives_list = nvme_data.get('drives', [])
                nvrams_list = nvme_data.get('nvrams', [])
                all_drives = drives_list + nvrams_list
                
                for drive_data in all_drives:
                    serial = drive_data.get('serial')
                    if serial:
                        devices.append(Device(serial, self._bundle))
                
                if devices:
                    logging.debug(f"Node {self.name}: loaded {len(devices)} devices from nvme_cli_list.json")
            except (json.JSONDecodeError, IOError):
                pass
        
        return devices
    
    # Private helper methods
    def _extract_ipmi_ip(self) -> Optional[str]:
        """Extract IPMI IP from lan print files"""
        ipmitool_dir = self._bundle.path / 'ipmitool'
        if not ipmitool_dir.exists():
            return None
        
        for lan_file in ipmitool_dir.glob('ipmitool_lan_print_*.txt'):
            try:
                with open(lan_file, 'r') as f:
                    content = f.read()
                
                match = re.search(r'IP Address\s+:\s+([0-9]+\.[0-9]+\.[0-9]+\.[0-9]+)', content)
                if match:
                    ipmi_ip = match.group(1)
                    if ipmi_ip != '0.0.0.0':
                        return ipmi_ip
            except IOError:
                continue
        
        return None
    
    @staticmethod
    def _extract_box_serial_from_dmidecode(dmidecode_file_path: Path) -> Optional[str]:
        """Extract Box serial from dmidecode.txt
        
        For multi-node boxes (CBox), dmidecode shows multiple Chassis Information sections.
        The LAST chassis serial is the CBox serial number.
        """
        try:
            with open(dmidecode_file_path, 'r') as f:
                content = f.read()
            
            # Find all "Serial Number:" lines that appear after "Chassis Information"
            # Pattern: Find "Chassis Information" section and extract its Serial Number
            chassis_sections = re.split(r'Handle 0x[0-9A-Fa-f]+, DMI type', content)
            
            last_chassis_serial = None
            for section in chassis_sections:
                if 'Chassis Information' in section:
                    # Extract Serial Number from this chassis section
                    match = re.search(r'Serial Number:\s*(.+)', section)
                    if match:
                        serial = match.group(1).strip()
                        if serial:  # Update to last found serial
                            last_chassis_serial = serial
            
            return last_chassis_serial
        except IOError:
            pass
        return None
    
    @staticmethod
    def _extract_box_serial_from_fru(fru_file_path: Path) -> Optional[str]:
        """Extract Box serial from FRU file"""
        try:
            with open(fru_file_path, 'r') as f:
                content = f.read()
            match = re.search(r'Chassis Serial\s+:\s+(\S+)', content)
            if match:
                return match.group(1)
        except IOError:
            pass
        return None
    
    @staticmethod
    def _extract_board_serial_from_fru(fru_file_path: Path) -> Optional[str]:
        """Extract Board serial from FRU file"""
        try:
            with open(fru_file_path, 'r') as f:
                content = f.read()
            match = re.search(r'Board Serial\s+:\s+(\S+)', content)
            if match:
                return match.group(1)
        except IOError:
            pass
        return None
    
    @staticmethod
    def _extract_manufacturer_id(mc_info_file: Path) -> Optional[str]:
        """Extract Manufacturer ID from mc_info"""
        try:
            with open(mc_info_file, 'r') as f:
                content = f.read()
            match = re.search(r'Manufacturer ID\s+:\s+(\d+)', content)
            if match:
                return match.group(1)
        except IOError:
            pass
        return None
    
    @staticmethod
    def _extract_product_id(mc_info_file: Path) -> Optional[str]:
        """Extract Product ID from mc_info"""
        try:
            with open(mc_info_file, 'r') as f:
                content = f.read()
            match = re.search(r'Product ID\s+:\s+(\d+)', content)
            if match:
                return match.group(1)
        except IOError:
            pass
        return None
    
    @staticmethod
    def _extract_nics_from_ibdev(ibdev_file: Path) -> Optional[str]:
        """Extract NIC types from ibdev2netdev.txt
        
        Parses the file to find ConnectX-5/6/7 cards and groups them by PCI slot.
        Returns a comma-separated list like "CX6, CX7" in PCI slot order.
        """
        try:
            with open(ibdev_file, 'r') as f:
                lines = f.readlines()
            
            # Dictionary to store PCI slot -> NIC type
            # Key is the first two parts of PCI address (e.g., "0000:63")
            pci_slots = {}
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # Extract PCI address (first field)
                pci_match = re.match(r'([0-9a-fA-F:\.]+)\s', line)
                if not pci_match:
                    continue
                
                pci_address = pci_match.group(1)
                # Get the slot identifier (e.g., "0000:63" from "0000:63:00.0")
                pci_parts = pci_address.split(':')
                if len(pci_parts) >= 2:
                    pci_slot = f"{pci_parts[0]}:{pci_parts[1]}"
                else:
                    continue
                
                # Skip if we already found a card in this slot
                if pci_slot in pci_slots:
                    continue
                
                # Extract ConnectX type
                cx_match = re.search(r'ConnectX-(\d+)', line)
                if cx_match:
                    pci_slots[pci_slot] = f'CX{cx_match.group(1)}'
                else:
                    pci_slots[pci_slot] = 'No CX found in ibdev2netdev.txt'
            
            if not pci_slots:
                return None
            
            # Sort by PCI address and return comma-separated list
            sorted_slots = sorted(pci_slots.items())
            nic_types = [nic_type for _, nic_type in sorted_slots]
            
            return ', '.join(nic_types)
            
        except IOError:
            pass
        return None


class Bundle:
    """Represents a bundle directory (similar to Luna's harvest)"""
    
    def __init__(self, path: Path, display_path: Optional[str] = None):
        self.path = path
        self.display_path = display_path or str(path)
    
    def __repr__(self):
        return f'<Bundle-{self.path.name}>'
    
    @cached_property
    def pdb(self) -> Optional[PDB]:
        """Get PDB (protobuf database) for this bundle (Luna's data source)"""
        pdb_folder = PDB.find_pdb_folder(self.path)
        if pdb_folder:
            logging.debug(f"Bundle {self.path.name}: found PDB at {pdb_folder.name}")
            return PDB(pdb_folder)
        logging.debug(f"Bundle {self.path.name}: no PDB found")
        return None
    
    @cached_property
    def node(self) -> Optional[Node]:
        """Get the node for this bundle (lazy)"""
        return Node(self)
    
    @cached_property
    def create_time(self) -> Optional[str]:
        """Extract bundle creation time from BUNDLE_ARGS"""
        bundle_args_file = self.path / 'METADATA' / 'BUNDLE_ARGS'
        if not bundle_args_file.exists():
            return None
        
        try:
            with open(bundle_args_file, 'r') as f:
                content = f.read()
            
            # Look for create_time or start_time
            for pattern in [r'create_time:\s+(.+)', r'start_time:\s+(.+)']:
                match = re.search(pattern, content)
                if match:
                    time_str = match.group(1).split('.')[0]  # Remove microseconds
                    return time_str
        except IOError:
            pass
        
        return None
    
    @cached_property
    def create_datetime(self) -> Optional[datetime]:
        """Parse create_time as datetime object"""
        if self.create_time:
            try:
                return datetime.strptime(self.create_time, '%Y-%m-%d %H:%M:%S')
            except ValueError:
                pass
        return None
    
    def find_device(self, serial: str) -> Optional[Device]:
        """Find a specific device by serial number"""
        for device in self.node.devices:
            if device.serial == serial:
                return device
        return None


class Cluster:
    """Cluster-level operations (similar to Luna's Cluster object)"""
    
    def __init__(self, bundles: List[Bundle]):
        self._bundles = bundles
    
    def __repr__(self):
        return f'<Cluster with {len(self._bundles)} bundles>'
    
    @cached_property
    def bundles(self) -> List[Bundle]:
        """All bundles in this cluster"""
        return self._bundles
    
    @cached_property
    def nodes(self) -> List[Node]:
        """All nodes in this cluster (lazy)"""
        return [bundle.node for bundle in self._bundles if bundle.node]
    
    @cached_property
    def dnodes(self) -> List[Node]:
        """All data nodes"""
        return [node for node in self.nodes if node.node_type == 'dnode']
    
    @cached_property
    def cnodes(self) -> List[Node]:
        """All compute nodes"""
        return [node for node in self.nodes if node.node_type == 'cnode']
    
    @cached_property
    def cluster_names(self) -> List[str]:
        """Extract all cluster names from nodes"""
        names = set()
        
        for node in self.nodes:
            # Try to extract from hostname (e.g., "shavast02-dnode143" -> "shavast02")
            if node.hostname:
                # Split on dash and take first part
                parts = node.hostname.split('-')
                if len(parts) >= 2:
                    # Check if it looks like a cluster name (not just "dnode" or "cnode")
                    cluster_part = parts[0]
                    if cluster_part.lower() not in ['dnode', 'cnode', 'node']:
                        names.add(cluster_part)
        
        # Also try to extract from vast-configure_network.py-params.ini
        for bundle in self._bundles:
            config_file = bundle.path / 'vast-configure_network.py-params.ini'
            if config_file.exists():
                try:
                    with open(config_file, 'r') as f:
                        for line in f:
                            if line.startswith('cluster_name'):
                                match = re.search(r'cluster_name\s*=\s*["\']?([^"\']+)["\']?', line)
                                if match:
                                    names.add(match.group(1).strip())
                except (IOError, OSError):
                    pass
        
        return sorted(list(names))
    
    @cached_property
    def cluster_name(self) -> str:
        """Get single cluster name or comma-separated list"""
        names = self.cluster_names
        if not names:
            return "Unknown"
        return ", ".join(names)
    
    @cached_method
    def nodes_by_box(self, box_serial: str) -> List[tuple[Node, Bundle]]:
        """Get all nodes in a specific box"""
        results = []
        for bundle in self._bundles:
            node = bundle.node
            if node and node.box_serial == box_serial:
                results.append((node, bundle))
        return results
    
    @cached_method
    def find_device(self, serial: str) -> Optional[tuple[Device, Node, Bundle]]:
        """Find a device across all bundles"""
        for bundle in self._bundles:
            device = bundle.find_device(serial)
            if device:
                return device, bundle.node, bundle
        return None
    
    @cached_method
    def find_node(self, identifier: str) -> List[tuple[Node, Bundle]]:
        """Find node(s) by name, serial, IP, or regex pattern"""
        results = []
        
        # Try exact match first
        for bundle in self._bundles:
            node = bundle.node
            if not node:
                continue
            
            if (node.name == identifier or
                node.serial_number == identifier or
                node.network.mgmt_ip == identifier or
                node.network.data_ip == identifier):
                results.append((node, bundle))
        
        if results:
            return results
        
        # Try regex match
        try:
            pattern = re.compile(identifier, re.IGNORECASE)
            for bundle in self._bundles:
                node = bundle.node
                if not node:
                    continue
                
                if (pattern.search(node.name) or
                    pattern.search(node.serial_number or '') or
                    pattern.search(node.network.mgmt_ip or '') or
                    pattern.search(node.network.data_ip or '') or
                    pattern.search(node.box_serial or '')):
                    results.append((node, bundle))
        except re.error:
            pass
        
        return results


# ============================================================================
# Cluster Initialization (similar to Luna's cluster discovery)
# ============================================================================

class ClusterDiscovery:
    """Discover and initialize cluster from bundle directories"""
    
    @staticmethod
    def find_bundle_directories(max_depth: int = 5) -> List[Path]:
        """Find all bundle directories by looking for METADATA/BUNDLE_ARGS"""
        bundle_dirs = []
        current_dir = Path('.')
        
        # Check current directory
        if (current_dir / 'METADATA' / 'BUNDLE_ARGS').exists():
            bundle_dirs.append(current_dir)
        
        # Recursively search subdirectories
        def search_directory(directory: Path, current_level: int = 0):
            if current_level > max_depth:
                return
            
            try:
                for item in directory.iterdir():
                    if item.is_dir():
                        if (item / 'METADATA' / 'BUNDLE_ARGS').exists():
                            bundle_dirs.append(item)
                        else:
                            search_directory(item, current_level + 1)
            except (PermissionError, OSError):
                pass
        
        search_directory(current_dir)
        return bundle_dirs
    
    @staticmethod
    def filter_latest_bundles_per_node(bundles: List[Bundle]) -> List[Bundle]:
        """Keep only the latest bundle per node (by hostname)"""
        node_bundles = defaultdict(list)
        
        for bundle in bundles:
            node = bundle.node
            if not node:
                continue
            
            hostname = node.hostname or node.name
            if not hostname:
                continue
            
            timestamp = bundle.create_datetime or datetime.min
            node_bundles[hostname].append((bundle, timestamp))
        
        # Keep latest per node
        latest_bundles = []
        for hostname, bundle_list in node_bundles.items():
            if bundle_list:
                latest_bundle = max(bundle_list, key=lambda x: x[1])
                latest_bundles.append(latest_bundle[0])
        
        return latest_bundles
    
    @staticmethod
    def calculate_display_paths(bundles: List[Bundle]) -> Dict[Bundle, str]:
        """Calculate minimum unique path components for display"""
        if not bundles:
            return {}
        
        current_dir = Path('.').resolve()
        relative_paths = {}
        
        for bundle in bundles:
            try:
                rel_path = bundle.path.resolve().relative_to(current_dir)
                relative_paths[bundle] = rel_path.parts
            except ValueError:
                relative_paths[bundle] = bundle.path.resolve().parts
        
        if not relative_paths:
            return {}
        
        # Find minimum components needed for uniqueness
        max_components = max(len(parts) for parts in relative_paths.values())
        
        for num_components in range(1, max_components + 1):
            shortened_paths = {}
            for bundle, parts in relative_paths.items():
                if len(parts) >= num_components:
                    shortened = '/'.join(parts[:num_components])
                else:
                    shortened = '/'.join(parts)
                shortened_paths[bundle] = shortened
            
            if len(set(shortened_paths.values())) == len(shortened_paths):
                return shortened_paths
        
        # Fallback: full paths
        return {bundle: '/'.join(parts) for bundle, parts in relative_paths.items()}
    
    @classmethod
    def discover(cls) -> Cluster:
        """Discover cluster from current directory"""
        logging.debug("Starting cluster discovery...")
        
        # Find bundle directories
        bundle_paths = cls.find_bundle_directories()
        logging.debug(f"Found {len(bundle_paths)} bundle directories")
        
        if not bundle_paths:
            raise RuntimeError("No bundle directories found")
        
        # Create Bundle objects
        bundles = [Bundle(path) for path in bundle_paths]
        
        # Filter to latest per node
        bundles = cls.filter_latest_bundles_per_node(bundles)
        logging.debug(f"After filtering: {len(bundles)} bundles (latest per node)")
        
        # Calculate display paths
        display_paths = cls.calculate_display_paths(bundles)
        for bundle in bundles:
            bundle.display_path = display_paths.get(bundle, str(bundle.path))
        
        return Cluster(bundles)


# ============================================================================
# RMA Form Rendering (kept from original)
# ============================================================================

@dataclass
class TableCell:
    content: str = ""
    
    def __str__(self) -> str:
        return self.content


@dataclass
class TableRow:
    cells: List[TableCell]
    style: str = "default"  # default, subtitle, separator
    
    def __init__(self, *cells: Union[str, TableCell], style: str = "default"):
        self.cells = []
        for cell in cells:
            if isinstance(cell, TableCell):
                self.cells.append(cell)
            else:
                self.cells.append(TableCell(str(cell)))
        self.style = style


@dataclass
class Table:
    rows: List[TableRow] = field(default_factory=list)
    
    def add_row(self, *cells: Union[str, TableCell], style: str = "default"):
        self.rows.append(TableRow(*cells, style=style))
    
    def add_separator(self):
        self.rows.append(TableRow(style="separator"))
    
    def calculate_column_widths(self) -> List[int]:
        if not self.rows:
            return []
        
        num_columns = 0
        for row in self.rows:
            if row.style != "separator":
                num_columns = len(row.cells)
                break
        
        if num_columns == 0:
            return []
        
        widths = [0] * num_columns
        
        for row in self.rows:
            if row.style == "separator":
                continue
            
            for i, cell in enumerate(row.cells):
                if i < num_columns:
                    content_len = len(cell.content)
                    if row.style == "subtitle" and i > 0:
                        content_len = content_len + 8
                    widths[i] = max(widths[i], content_len)
        
        if num_columns == 2:
            widths[0] = max(widths[0], 16)
            widths[1] = max(widths[1], 26)
        
        return widths


def render_table(table: Table) -> str:
    """Render a table to formatted string output"""
    if not table.rows:
        return ""
    
    widths = table.calculate_column_widths()
    if not widths:
        return ""
    
    lines = []
    
    for row in table.rows:
        if row.style == "separator":
            parts = ['-' * width for width in widths]
            lines.append(f"| {' | '.join(parts)} |")
        
        elif row.style == "subtitle":
            if len(widths) == 2:
                left = '-' * widths[0]
                if len(row.cells) > 1:
                    right_content = row.cells[1].content
                    available_width = widths[1]
                    content_with_prefix = f"--- {right_content} "
                    padding_needed = available_width - len(content_with_prefix)
                    
                    if padding_needed >= 3:
                        right = content_with_prefix + ('-' * padding_needed)
                    else:
                        right = content_with_prefix + '---'
                else:
                    right = '-' * widths[1]
                
                lines.append(f"| {left} | {right} |")
            else:
                parts = []
                for i, width in enumerate(widths):
                    if i == 0 and len(row.cells) > 0:
                        content = row.cells[0].content
                        content_with_prefix = f"--- {content} "
                        padding_needed = width - len(content_with_prefix)
                        
                        if padding_needed >= 3:
                            parts.append(content_with_prefix + ('-' * padding_needed))
                        else:
                            parts.append(content_with_prefix + '---')
                    else:
                        parts.append('-' * width)
                
                lines.append(f"| {' | '.join(parts)} |")
        
        else:
            parts = []
            for i, cell in enumerate(row.cells):
                if i < len(widths):
                    parts.append(f"{cell.content:<{widths[i]}}")
            lines.append(f"| {' | '.join(parts)} |")
    
    return "\n".join(lines)


# ============================================================================
# High-level presentation functions
# ============================================================================

def get_ip_last_octet(ip_address: Optional[str]) -> int:
    """Extract the last octet from an IP address for sorting purposes."""
    if not ip_address:
        return 0
    try:
        return int(ip_address.split('.')[-1])
    except (ValueError, IndexError):
        return 0


def ip_to_sort_key(ip_address: Optional[str]) -> tuple:
    """Convert IP address to tuple of integers for numerical sorting.
    
    Returns tuple of (octet1, octet2, octet3, octet4) for proper numerical comparison.
    Returns (0, 0, 0, 0) for invalid/missing IPs.
    """
    if not ip_address:
        return (0, 0, 0, 0)
    try:
        octets = ip_address.split('.')
        if len(octets) != 4:
            return (0, 0, 0, 0)
        return tuple(int(octet) for octet in octets)
    except (ValueError, AttributeError):
        return (0, 0, 0, 0)


def extract_case_from_path() -> Optional[str]:
    """Extract case number from current working directory path"""
    try:
        current_path = Path.cwd()
        path_str = str(current_path)
        
        # Look for Case-######## pattern
        match = re.search(r'Case-(\d{8})', path_str, re.IGNORECASE)
        if match:
            return match.group(1)
    except Exception:
        pass
    return None


def format_case_number(case_number: Optional[str] = None) -> str:
    """Format case number for display with appropriate default
    
    Returns tuple of (case_label, rma_label)
    """
    if case_number:
        # Explicitly provided case number
        formatted_case = str(case_number).zfill(8)
        return f"Case-{formatted_case}"
    
    # Try to extract from path
    path_case = extract_case_from_path()
    if path_case:
        formatted_case = str(path_case).zfill(8)
        return f"Case-{formatted_case}?"
    
    # Default
    return "Case-000....."


def list_nodes(node_bundle_list: List[tuple[Node, Bundle]], title: str = "Available Nodes"):
    """List specific nodes in tabular format"""
    if not node_bundle_list:
        print("No nodes found", file=sys.stderr)
        return
    
    # Group by box
    box_nodes = defaultdict(list)
    for node, bundle in node_bundle_list:
        if node and node.box_serial:
            box_nodes[node.box_serial].append((node, bundle))
    
    # Sort boxes by first node's MGMT IP (numerically)
    def get_first_mgmt_ip_key(item):
        box_serial, node_list = item
        if not node_list:
            return (0, 0, 0, 0)
        # Sort nodes within box by MGMT IP to find the first one
        sorted_nodes = sorted(node_list, key=lambda x: ip_to_sort_key(x[0].network.mgmt_ip))
        return ip_to_sort_key(sorted_nodes[0][0].network.mgmt_ip)
    
    sorted_boxes = sorted(box_nodes.items(), key=get_first_mgmt_ip_key)
    
    # Build table
    table = Table()
    table.add_row("Name", "Type", "Position", "Data IP", "MGMT IP", "IPMI IP",
                  "Node S/N", "Box S/N", "Mfr ID", "Prod ID", "MAC Address",
                  "Create Time", "Bundle Path")
    table.add_separator()
    
    first_box = True
    for box_serial, node_list in sorted_boxes:
        # Sort nodes within box (bottom first, then by last octet of data IP)
        node_list.sort(key=lambda x: (
            x[0].position != 'bottom',
            get_ip_last_octet(x[0].network.data_ip)
        ))
        
        if not first_box:
            table.add_separator()
        first_box = False
        
        for node, bundle in node_list:
            table.add_row(
                node.name,
                node.node_type.upper(),
                node.position,
                node.network.data_ip or 'Unknown',
                node.network.mgmt_ip or 'Unknown',
                node.network.ipmi_ip or 'Unknown',
                node.serial_number,
                node.box_serial or 'Unknown',
                node.manufacturer_id or '',
                node.product_id or '',
                node.network.mac_address or 'Unknown',
                bundle.create_time or 'Unknown',
                bundle.display_path
            )
    
    print(title + ":")
    print("=" * 240)
    print(render_table(table))


def list_all_nodes(cluster: Cluster):
    """List all available nodes in tabular format"""
    node_bundle_list = [(bundle.node, bundle) for bundle in cluster.bundles if bundle.node]
    list_nodes(node_bundle_list, "Available Nodes")


def show_node_rma_form(node: Node, sibling_nodes: List[Node], cluster: Cluster, case_number: Optional[str] = None):
    """Show RMA form for a node"""
    table = Table()
    
    # Header
    node_type_display = node.node_type.upper()
    table.add_row(f"{node_type_display} Replacement", f"FRU-___-{node_type_display}-___")
    table.add_separator()
    
    # Case number (always shown with smart default)
    case_label = format_case_number(case_number)
    table.add_row(case_label, "RMA-0000.... / FE-000.....")
    
    # Standard fields
    table.add_row("Cluster", cluster.cluster_name)
    table.add_row("Tracking", "FedEx #  <TBD>")
    table.add_row("Delivery ETA", "")
    table.add_row("Room / Rack / RU", "")
    table.add_row("Box S/N", node.box_serial or '')
    
    # Node information
    table.add_row("", node.node_type, style="subtitle")
    index = "1" if node.position == "bottom" else "2"
    table.add_row("Index", index)
    table.add_row("Model", node.model)
    if node.nics:
        table.add_row("NICs", node.nics)
    table.add_row("name", node.name)
    table.add_row("position", node.position)
    table.add_row("IP", node.network.data_ip or "")
    table.add_row("MGMT IP", node.network.mgmt_ip or "")
    table.add_row("IPMI IP", node.network.ipmi_ip or "")
    table.add_row("SerialNumber", node.serial_number)
    table.add_row("MAC Address", node.network.mac_address or "")
    
    # Sibling nodes
    for i, sibling in enumerate(sibling_nodes, 1):
        header = f"sibling {sibling.node_type}"
        if len(sibling_nodes) > 1:
            header += f" {i}"
        table.add_row("", header, style="subtitle")
        table.add_row("name", sibling.name)
        table.add_row("position", sibling.position)
        table.add_row("IP", sibling.network.data_ip or "")
        table.add_row("MGMT IP", sibling.network.mgmt_ip or "")
        table.add_row("IPMI IP", sibling.network.ipmi_ip or "")
        table.add_row("SerialNumber", sibling.serial_number)
        table.add_row("MAC Address", sibling.network.mac_address or "")
    
    print(render_table(table))


def show_drive_rma_form(device: Device, node: Node, sibling_nodes: List[Node], cluster: Cluster, case_number: Optional[str] = None):
    """Show RMA form for a drive"""
    table = Table()
    
    # Header
    title = "SSD Replacement" if device.drive_type == "ssd" else "NVRAM Replacement"
    table.add_row(title, "FRU_...")
    table.add_separator()
    
    # Case number (always shown with smart default)
    case_label = format_case_number(case_number)
    table.add_row(case_label, "RMA-0000.... / FE-000.....")
    
    # Standard fields
    table.add_row("Cluster", cluster.cluster_name)
    table.add_row("Tracking", "FedEx #  <TBD>")
    table.add_row("Delivery ETA", "")
    table.add_row("Room / Rack / RU", "")
    
    # Drive information
    table.add_row("DBox", node.box_serial or '')
    table.add_row("Location in Box", device.location_in_box)
    index = "1" if node.position == "bottom" else "2"
    table.add_row("Index", index)
    table.add_row("DevicePath", device.path)
    table.add_row("Model", device.model)
    table.add_row("SerialNumber", device.serial)
    
    # Associated node
    table.add_row("", "associated dnode", style="subtitle")
    table.add_row("name", node.name)
    table.add_row("position", node.position)
    table.add_row("IP", node.network.data_ip or "")
    table.add_row("MGMT IP", node.network.mgmt_ip or "")
    table.add_row("IPMI IP", node.network.ipmi_ip or "")
    table.add_row("SerialNumber", node.serial_number)
    table.add_row("MAC Address", node.network.mac_address or "")
    
    # Sibling nodes
    for sibling in sibling_nodes:
        table.add_row("", f"sibling {sibling.node_type}", style="subtitle")
        table.add_row("name", sibling.name)
        table.add_row("position", sibling.position)
        table.add_row("IP", sibling.network.data_ip or "")
        table.add_row("MGMT IP", sibling.network.mgmt_ip or "")
        table.add_row("IPMI IP", sibling.network.ipmi_ip or "")
        table.add_row("SerialNumber", sibling.serial_number)
        table.add_row("MAC Address", sibling.network.mac_address or "")
    
    print(render_table(table))


def show_device_list(node: Node, sibling_nodes: List[Node], drive_type_filter: Optional[str] = None, nodes_for_drives: Optional[List[Node]] = None):
    """Show list of devices for a node
    
    Args:
        node: Primary node to display
        sibling_nodes: Sibling nodes to display in info section
        drive_type_filter: Filter drives by type (ssd/nvram)
        nodes_for_drives: Nodes to include drives from (default: node + siblings)
    """
    # Determine which nodes to get drives from
    if nodes_for_drives is None:
        nodes_for_drives = [node] + sibling_nodes
    
    # Get devices from specified nodes only
    all_devices = []
    for n in nodes_for_drives:
        for device in n.devices:
            if drive_type_filter and device.drive_type != drive_type_filter:
                continue
            all_devices.append((device, n))
    
    if not all_devices:
        print(f"No devices found", file=sys.stderr)
        return
    
    # Render node section
    table = Table()
    table.add_row("DBox S/N", node.box_serial or '')
    table.add_row("", "dnode", style="subtitle")
    index = "1" if node.position == "bottom" else "2"
    table.add_row("Index", index)
    table.add_row("Model", node.model)
    table.add_row("name", node.name)
    table.add_row("position", node.position)
    table.add_row("IP", node.network.data_ip or '')
    table.add_row("MGMT IP", node.network.mgmt_ip or '')
    table.add_row("IPMI IP", node.network.ipmi_ip or '')
    table.add_row("SerialNumber", node.serial_number)
    table.add_row("MAC Address", node.network.mac_address or '')
    
    for sibling in sibling_nodes:
        table.add_row("", "sibling dnode", style="subtitle")
        table.add_row("name", sibling.name)
        table.add_row("position", sibling.position)
        table.add_row("IP", sibling.network.data_ip or '')
        table.add_row("MGMT IP", sibling.network.mgmt_ip or '')
        table.add_row("IPMI IP", sibling.network.ipmi_ip or '')
        table.add_row("SerialNumber", sibling.serial_number)
        table.add_row("MAC Address", sibling.network.mac_address or '')
    
    print(render_table(table))
    print()
    
    # Render devices table
    drive_label = "SSDs" if drive_type_filter == "ssd" else "NVRAMs" if drive_type_filter == "nvram" else "Drives"
    print(f"{drive_label}:")
    
    device_table = Table()
    device_table.add_row("Type", "Serial", "Location", "Node", "Index", "DevicePath", "Model")
    device_table.add_separator()
    
    # Sort by location
    all_devices.sort(key=lambda x: (x[0].pci_switch_slot or 999, x[1].name))
    
    for device, dev_node in all_devices:
        device_table.add_row(
            device.drive_type,
            device.serial,
            device.location_in_box,
            dev_node.name,
            str(device.data.get('index', 'N/A') if device.data else 'N/A'),
            device.path,
            device.model
        )
    
    print(render_table(device_table))


# ============================================================================
# Main CLI
# ============================================================================

def main():
    try:
        main_impl()
    except (BrokenPipeError, KeyboardInterrupt):
        sys.exit(0)


def main_impl():
    parser = argparse.ArgumentParser(
        description='Luna-style RMA Preparation Tool',
        epilog='''
Examples:
  %(prog)s                                            # List all nodes
  %(prog)s dnode-3-100                                # Show node RMA form
  %(prog)s --drive PHAC2070006C30PGGN                 # Show drive RMA form
  %(prog)s dnode161 --ssd                             # List SSDs in node
  %(prog)s --case 00090597 --drive SERIAL123          # RMA form with case
        ''',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument('node_name', nargs='?', help='Node identifier (name/serial/IP/regex)')
    
    drive_group = parser.add_mutually_exclusive_group()
    drive_group.add_argument('--ssd', nargs='?', const='LIST', metavar='SERIAL')
    drive_group.add_argument('--drive', nargs='?', const='LIST', metavar='SERIAL')
    drive_group.add_argument('--nvram', nargs='?', const='LIST', metavar='SERIAL')
    drive_group.add_argument('--scm', nargs='?', const='LIST', metavar='SERIAL')
    
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose logging')
    parser.add_argument('--case', metavar='CASE_NUMBER', help='Case number for RMA form')
    
    args = parser.parse_args()
    
    # Configure logging
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG, format='[VERBOSE] %(message)s', stream=sys.stderr)
    else:
        logging.basicConfig(level=logging.WARNING)
    
    # Discover cluster
    logging.debug("Discovering cluster...")
    try:
        cluster = ClusterDiscovery.discover()
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    
    logging.debug(f"Cluster initialized with {len(cluster.bundles)} bundles")
    
    # Handle drive mode
    drive_serial = args.ssd or args.drive or args.nvram or args.scm
    if drive_serial:
        if drive_serial == 'LIST':
            # List drives for a node or box
            if not args.node_name:
                print("Error: Please provide a node name to list drives", file=sys.stderr)
                sys.exit(1)
            
            matches = cluster.find_node(args.node_name)
            if not matches:
                print(f"Error: Node '{args.node_name}' not found", file=sys.stderr)
                sys.exit(1)
            
            # Check if all matches are dnodes from the same box
            dnodes = [(n, b) for n, b in matches if n.node_type == 'dnode']
            if not dnodes:
                print(f"Error: No DNodes found. Drive listing only works with DNodes.", file=sys.stderr)
                sys.exit(1)
            
            # If multiple nodes match, check if they're all from the same box
            if len(dnodes) > 1:
                # Check if all from same box
                box_serials = set(n.box_serial for n, b in dnodes)
                if len(box_serials) == 1:
                    # All from same box - show all nodes and all their drives
                    node, bundle = dnodes[0]
                    siblings = [n for n, b in dnodes[1:]]
                    # Sort siblings by last octet of data IP
                    siblings.sort(key=lambda n: get_ip_last_octet(n.network.data_ip))
                    nodes_for_drives = [node] + siblings
                else:
                    # Different boxes - need to be more specific
                    print(f"Multiple nodes from different boxes matched '{args.node_name}'. Please be more specific:", file=sys.stderr)
                    print(file=sys.stderr)
                    list_nodes(matches, "Matched Nodes")
                    sys.exit(1)
            else:
                # Single node match - show node and siblings, but only matched node's drives
                node, bundle = dnodes[0]
                # Get all siblings from the same box
                all_box_nodes = [n for n, b in cluster.nodes_by_box(node.box_serial) 
                                if n.node_type == 'dnode']
                siblings = [n for n in all_box_nodes if n != node]
                # Sort siblings by last octet of data IP
                siblings.sort(key=lambda n: get_ip_last_octet(n.network.data_ip))
                # Only get drives from the matched node
                nodes_for_drives = [node]
            
            # Filter by drive type
            filter_type = 'ssd' if args.ssd else 'nvram' if (args.nvram or args.scm) else None
            show_device_list(node, siblings, filter_type, nodes_for_drives)
            
        else:
            # Show drive RMA form
            result = cluster.find_device(drive_serial)
            if not result:
                print(f"Error: Drive '{drive_serial}' not found", file=sys.stderr)
                sys.exit(1)
            
            device, node, bundle = result
            if node.node_type != 'dnode':
                print(f"Error: Drive is not in a DNode", file=sys.stderr)
                sys.exit(1)
            
            # Get siblings
            siblings = [n for n, b in cluster.nodes_by_box(node.box_serial) 
                       if n != node and n.node_type == 'dnode']
            # Sort siblings by last octet of data IP
            siblings.sort(key=lambda n: get_ip_last_octet(n.network.data_ip))
            
            show_drive_rma_form(device, node, siblings, cluster, args.case)
        
        return
    
    # Handle node mode
    if not args.node_name:
        # List all nodes
        list_all_nodes(cluster)
        return
    
    # Find specific node
    matches = cluster.find_node(args.node_name)
    
    if not matches:
        print(f"Error: No matches found for '{args.node_name}'", file=sys.stderr)
        sys.exit(1)
    
    if len(matches) > 1:
        print(f"Multiple nodes matched '{args.node_name}'. Please be more specific:", file=sys.stderr)
        print(file=sys.stderr)
        list_nodes(matches, "Matched Nodes")
        sys.exit(1)
    
    # Single match - show RMA form
    node, bundle = matches[0]
    siblings = [n for n, b in cluster.nodes_by_box(node.box_serial) if n != node]
    # Sort siblings by last octet of data IP
    siblings.sort(key=lambda n: get_ip_last_octet(n.network.data_ip))
    show_node_rma_form(node, siblings, cluster, args.case)


if __name__ == "__main__":
    main()

