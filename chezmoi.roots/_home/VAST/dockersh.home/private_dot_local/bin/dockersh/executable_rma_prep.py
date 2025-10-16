#!/usr/bin/env python3
"""
RMA Preparation Tool

This script extracts node information (dnodes and cnodes) and SSD information from 
bundle directories and formats it according to the specified output format. It can 
list all available nodes, show detailed information for a specific node, or show 
SSD replacement information for a specific SSD.

PDB (Protobuf Database) Discovery:
- First searches the current bundle's pdb/ directory
- Then prioritizes sibling leader bundles (primary source for cluster-wide PDB)
- Falls back to other sibling bundles and parent directory
- This supports the common pattern where a leader/CNode bundle contains 
  cluster-wide PDB with complete device metadata while DNode bundles contain only local data

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
from typing import List, Optional, Dict, Any, Union, Tuple

# Python 3.6/3.7 compatibility: cached_property was added in Python 3.8
try:
    from functools import cached_property
except ImportError:
    # Fallback for Python < 3.8
    class cached_property:
        """A property that is only computed once and then replaces itself with an ordinary attribute."""
        def __init__(self, func):
            self.func = func
            self.__doc__ = func.__doc__
        
        def __get__(self, obj, objtype=None):
            if obj is None:
                return self
            value = self.func(obj)
            setattr(obj, self.func.__name__, value)
            return value

# Placeholder for vapi - will be imported dynamically per bundle
HAS_VAPI = False
STR_TO_TYPE_ID = None
Commander = None


# ============================================================================
# Constants
# ============================================================================

# File paths (relative to bundle directory)
METADATA_BUNDLE_ARGS = 'METADATA/BUNDLE_ARGS'
SYSTEMCTL_STATUS_PATH = 'systemctl_output/systemctl_status.txt'
PLATFORM_CONFIG_PATH = 'config/platform.config'
NVME_CLI_LIST_PATH = 'nvme_cli_list.json'
NVME_LIST_PATH = 'nvme_list.json'
IPMITOOL_FRU_PATH = 'ipmitool/ipmitool_fru_list.txt'
IPMITOOL_MC_INFO_PATH = 'ipmitool/ipmitool_mc_info.txt'
BMC_LOGS_PATH = 'bmc_logs'
LSPCI_VVV_PATH = 'lspci_vvv_info'
DMIDECODE_PATH = 'dmidecode.txt'
IBDEV2NETDEV_PATH = 'ibdev2netdev.txt'
MONITOR_RESULT_PATH = 'monitor_result.json'
CONFIGURE_NETWORK_PARAMS = 'vast-configure_network.py-params.ini'
SELF_GUID_PATH = 'self.guid'

# Default values
UNKNOWN_VALUE = 'Unknown'
UNKNOWN_IP = (0, 0, 0, 0)

# Invalid serial number indicators
INVALID_SERIALS = {'Unspecified', 'Not Specified', '0'}

# Node types
NODE_TYPE_DNODE = 'dnode'
NODE_TYPE_CNODE = 'cnode'
NODE_TYPE_UNKNOWN = 'unknown'

# Drive type indicators (NVRAM/SCM identifiers)
NVRAM_INDICATORS = ['optane', 'dcpmm', 'ssdpe21k', 'ssdpf21', 'scm', 'nvdimm', 'pmem', 'pascari']

# Directories to skip when searching for bundles
SKIP_BUNDLE_DIRS = {
    'compatible_vapi', 'venv', '__pycache__', 'node_modules',
    'pdb', 'config', 'ipmitool', 'bmc_logs', 'systemctl_output',
    'METADATA', 'ipmi_cmds_logs', 'nvme_cli_list', 'dmidecode',
    'ipmi_lan_print', 'lspci', 'ibdev2netdev'
}


# ============================================================================
# Regex Patterns
# ============================================================================

class RegexPatterns:
    """Centralized regex patterns for parsing various files"""
    
    # Platform config patterns
    NODE_INFO = re.compile(
        r'(?:.|\n)*ip: "(?P<node_ip>.*)"(?:.|\n)*port: (?P<node_port>\d+)'
        r'(?:.|\n)*node_type: "(?P<node_type>.*)"(?:.|\n)*'
    )
    NODE_ARCH = re.compile(r'node_architecture: "(.*?)"')
    DNODE_INDEX = re.compile(r'dnode_index: "(.*?)"')
    
    # Serial number patterns
    LSPCI_VPD_SERIAL = re.compile(r'\[SN\]\s+Serial number:\s+(\S+)')
    CHASSIS_SERIAL = re.compile(r'Chassis Serial\s+:\s+(\S+)')
    BOARD_SERIAL = re.compile(r'Board Serial\s+:\s+(\S+)')
    
    # IPMI patterns
    IPMI_IP_ADDRESS = re.compile(r'IP Address\s+:\s+([0-9]+\.[0-9]+\.[0-9]+\.[0-9]+)')
    MANUFACTURER_ID = re.compile(r'Manufacturer ID\s+:\s+(\d+)')
    PRODUCT_ID = re.compile(r'Product ID\s+:\s+(\d+)')
    
    # NIC patterns
    PCI_ADDRESS = re.compile(r'([0-9a-fA-F:\.]+)\s')
    CONNECTX_TYPE = re.compile(r'ConnectX-(\d+)')
    NIC_SPEED = re.compile(r'(\d+)Gb')
    
    # Path patterns
    CASE_NUMBER = re.compile(r'Case-(\d{8})', re.IGNORECASE)
    PDB_TIMESTAMP = re.compile(r'\d{8}_\d{6}')
    
    # DMI type pattern
    DMI_HANDLE = re.compile(r'Handle 0x[0-9A-Fa-f]+, DMI type')


def try_import_vapi_from_path(vapi_path: Path) -> bool:
    """Dynamically import vapi from a specific bundle path
    
    Returns True if successful, False otherwise.
    
    Note: vapi requires the 'vproto' package to be available in the Python environment.
    If vproto is not installed, vapi import will fail and the script will fall back
    to parsing JSON files directly. This means some metadata (e.g., PCI switch location
    for devices) may not be available if the device wasn't exposed/attached when the
    bundle was collected.
    """
    global HAS_VAPI, STR_TO_TYPE_ID, Commander
    
    if not vapi_path or not vapi_path.exists():
        return False
    
    # Add to sys.path if not already there
    vapi_path_str = str(vapi_path)
    if vapi_path_str not in sys.path:
        sys.path.insert(0, vapi_path_str)
        logging.debug(f"Added {vapi_path_str} to sys.path")
    
    try:
        # Import fresh from the path
        import importlib
        if 'vapi.commander' in sys.modules:
            # Reload if already imported
            import vapi.commander  # type: ignore
            importlib.reload(vapi.commander)
        else:
            import vapi.commander  # type: ignore
        
        from vapi.commander import STR_TO_TYPE_ID as _STR_TO_TYPE_ID  # type: ignore
        from vapi.commander import Commander as _Commander  # type: ignore
        
        STR_TO_TYPE_ID = _STR_TO_TYPE_ID
        Commander = _Commander
        HAS_VAPI = True
        logging.debug(f"Successfully imported vapi from {vapi_path}")
        return True
    except ImportError as e:
        if 'vproto' in str(e):
            logging.debug(f"vapi import requires 'vproto' package (not available): {e}")
            logging.debug("Falling back to JSON parsing (some PDB metadata may be unavailable)")
        else:
            logging.debug(f"Failed to import vapi from {vapi_path}: {e}")
        return False
    except Exception as e:
        logging.debug(f"Failed to import vapi from {vapi_path}: {e}")
        return False


# ============================================================================
# File Reading Utilities
# ============================================================================

def _read_text_file(path: Path) -> Optional[str]:
    """Read text file with standard error handling
    
    Args:
        path: Path to file to read
        
    Returns:
        File contents as string, or None if file doesn't exist or can't be read
    """
    if not path.exists():
        return None
    try:
        return path.read_text(encoding='utf-8')
    except (IOError, OSError) as e:
        logging.debug(f"Failed to read {path}: {e}")
        return None


def _read_json_file(path: Path) -> Optional[Dict[str, Any]]:
    """Read JSON file with standard error handling
    
    Args:
        path: Path to JSON file to read
        
    Returns:
        Parsed JSON as dict, or None if file doesn't exist or can't be parsed
    """
    if not path.exists():
        return None
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logging.debug(f"Failed to parse JSON {path}: {e}")
        return None


def _search_file_for_pattern(path: Path, pattern, group: int = 1) -> Optional[str]:
    """Search file for regex pattern and return first match
    
    Args:
        path: Path to file to search
        pattern: Regex pattern (string or compiled Pattern)
        group: Capture group to return (default: 1)
        
    Returns:
        Matched group string, or None if not found
    """
    content = _read_text_file(path)
    if not content:
        return None
    
    if isinstance(pattern, str):
        pattern = re.compile(pattern)
    
    match = pattern.search(content)
    if match:
        return match.group(group)
    return None


def _search_file_for_patterns(path: Path, patterns: Dict[str, Any]) -> Dict[str, Optional[str]]:
    """Search file for multiple patterns and return dict of results
    
    Args:
        path: Path to file to search
        patterns: Dict of {key: pattern} to search for
        
    Returns:
        Dict of {key: matched_value} with None for patterns not found
    """
    content = _read_text_file(path)
    results = {}
    
    if not content:
        return {key: None for key in patterns}
    
    for key, pattern in patterns.items():
        if isinstance(pattern, str):
            pattern = re.compile(pattern)
        match = pattern.search(content)
        results[key] = match.group(1) if match else None
    
    return results


# ============================================================================
# FRU (Field Replaceable Unit) Parser
# ============================================================================

class FRUParser:
    """Parser for IPMI FRU (Field Replaceable Unit) files
    
    Handles both ipmitool FRU files and bmc_logs FRU files.
    Provides methods to extract serial numbers from different FRU devices.
    """
    
    def __init__(self, fru_file_path: Path):
        """Initialize FRU parser
        
        Args:
            fru_file_path: Path to FRU file (ipmitool/ipmitool_fru_list.txt or bmc_logs/*/fru.log)
        """
        self.path = fru_file_path
        self._content = None
    
    @property
    def content(self) -> Optional[str]:
        """Lazy load file content"""
        if self._content is None:
            self._content = _read_text_file(self.path)
        return self._content
    
    def get_chassis_serial(self, fru_id: Optional[int] = None) -> Optional[str]:
        """Get Chassis Serial from specific FRU ID or first found
        
        Args:
            fru_id: Specific FRU ID (0, 1, etc.) or None for first found
            
        Returns:
            Chassis serial number, or None if not found
        """
        if not self.content:
            return None
        
        if fru_id is not None:
            # Search for specific FRU device
            pattern = re.compile(
                rf'FRU Device Description.*\(ID {fru_id}\).*?Chassis Serial\s+:\s+(\S+)',
                re.DOTALL
            )
            match = pattern.search(self.content)
        else:
            # Search for any Chassis Serial
            match = RegexPatterns.CHASSIS_SERIAL.search(self.content)
        
        if match:
            serial = match.group(1).strip()
            if serial and serial not in INVALID_SERIALS:
                return serial
        return None
    
    def get_board_serial(self) -> Optional[str]:
        """Get Board Serial Number
        
        Returns:
            Board serial number, or None if not found
        """
        if not self.content:
            return None
        
        match = RegexPatterns.BOARD_SERIAL.search(self.content)
        if match:
            return match.group(1)
        return None
    
    def get_all_chassis_serials(self) -> List[Tuple[int, str]]:
        """Get all Chassis Serial numbers with their FRU IDs
        
        Returns:
            List of (fru_id, serial) tuples
        """
        if not self.content:
            return []
        
        results = []
        pattern = re.compile(
            r'FRU Device Description.*\(ID (\d+)\).*?Chassis Serial\s+:\s+(\S+)',
            re.DOTALL
        )
        
        for match in pattern.finditer(self.content):
            fru_id = int(match.group(1))
            serial = match.group(2).strip()
            if serial and serial not in INVALID_SERIALS:
                results.append((fru_id, serial))
        
        return results


class BMCLogsFRUParser(FRUParser):
    """Parser for BMC logs FRU files (bmc_logs/*/fru.log)
    
    BMC logs contain FRU data split by "fru print <id>" commands.
    This parser handles the different format from ipmitool FRU files.
    """
    
    def get_chassis_serial_by_section(self, fru_id: int) -> Optional[str]:
        """Extract Chassis Serial from specific FRU ID section in bmc_logs
        
        BMC logs format: Content is split by "fru print <id>" commands
        
        Args:
            fru_id: FRU ID (0, 1, etc.)
            
        Returns:
            Chassis serial number, or None if not found
        """
        if not self.content:
            return None
        
        # Split by "fru print" commands
        sections = re.split(r'fru print \d+', self.content)
        
        # Section index is fru_id + 1 (split creates empty first element)
        if fru_id + 1 < len(sections):
            section = sections[fru_id + 1]
            match = RegexPatterns.CHASSIS_SERIAL.search(section)
            if match:
                serial = match.group(1).strip()
                if serial and serial not in INVALID_SERIALS:
                    return serial
        
        return None


# ============================================================================
# Serial Number Extraction
# ============================================================================

class SerialNumberExtractor:
    """Extract serial numbers from various system information sources
    
    Consolidates serial extraction logic for nodes and boxes from multiple
    file types (lspci, FRU, BMC logs, dmidecode).
    """
    
    def __init__(self, bundle_path: Path):
        """Initialize serial extractor
        
        Args:
            bundle_path: Path to bundle directory
        """
        self.bundle_path = bundle_path
    
    def get_node_serial_from_lspci(self) -> Optional[str]:
        """Extract node serial from lspci VPD section (BlueField DPU)
        
        Extracts serial number from VPD (Vital Product Data) section:
        Pattern: [SN] Serial number: MT2326XZ0DRJ
        
        Returns:
            Node serial number, or None if not found
        """
        lspci_file = self.bundle_path / LSPCI_VVV_PATH
        if not lspci_file.exists():
            return None
        
        serial = _search_file_for_pattern(lspci_file, RegexPatterns.LSPCI_VPD_SERIAL)
        if serial and serial not in INVALID_SERIALS:
            logging.debug(f"Node serial from lspci VPD: {serial}")
            return serial
        return None
    
    def get_box_serial_from_bmc_logs(self) -> Optional[str]:
        """Extract box serial from bmc_logs/*/fru.log
        
        For multi-node DBox systems (AIC DF-30):
        - FRU 0 = Dtray (individual node tray) 
        - FRU 1 = DBox (multi-node enclosure) - has Chassis Serial
        
        For single-node servers (Viking NSS2560):
        - FRU 0 = Server chassis - has Chassis Serial
        - FRU 1 = Riser board - no Chassis Serial
        
        Strategy: Try FRU 1 Chassis Serial first (DBox), fall back to FRU 0 (single-node)
        
        Returns:
            Box serial number, or None if not found
        """
        bmc_logs_dir = self.bundle_path / BMC_LOGS_PATH
        if not bmc_logs_dir.exists():
            return None
        
        # Find fru.log files in bmc_logs subdirectories
        fru_log_files = list(bmc_logs_dir.glob('*/fru.log'))
        if not fru_log_files:
            return None
        
        # Use the first fru.log found
        fru_log_file = fru_log_files[0]
        parser = BMCLogsFRUParser(fru_log_file)
        
        # Try FRU 1 first (multi-node DBox systems)
        serial = parser.get_chassis_serial_by_section(fru_id=1)
        if serial:
            logging.debug(f"Box serial from bmc_logs FRU 1 (DBox): {serial}")
            return serial
        
        # Fall back to FRU 0 (single-node traditional servers)
        serial = parser.get_chassis_serial_by_section(fru_id=0)
        if serial:
            logging.debug(f"Box serial from bmc_logs FRU 0 (single-node): {serial}")
            return serial
        
        return None
    
    def get_box_serial_from_dmidecode(self) -> Optional[str]:
        """Extract box serial from dmidecode.txt
        
        For multi-node boxes (CBox), dmidecode shows multiple Chassis Information sections.
        The LAST chassis serial is the CBox serial number.
        
        Returns:
            Box serial number, or None if not found
        """
        dmidecode_file = self.bundle_path / DMIDECODE_PATH
        content = _read_text_file(dmidecode_file)
        if not content:
            return None
        
        # Find all "Serial Number:" lines that appear after "Chassis Information"
        chassis_sections = RegexPatterns.DMI_HANDLE.split(content)
        
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


# ============================================================================
# IPMI Data Extraction
# ============================================================================

class IPMIExtractor:
    """Extract IPMI-related information from various sources
    
    Consolidates IPMI data extraction logic (IP, manufacturer/product IDs) from
    multiple file types (ipmitool outputs, ipmi_cmds_logs, mc_info).
    """
    
    def __init__(self, bundle_path: Path):
        """Initialize IPMI extractor
        
        Args:
            bundle_path: Path to bundle directory
        """
        self.bundle_path = bundle_path
    
    def get_ipmi_ip(self) -> Optional[str]:
        """Extract IPMI IP from multiple sources
        
        Priority:
        1. ipmitool/ipmitool_lan_print_*.txt
        2. ipmi_cmds_logs/ipmi_cmds.log (fallback for harvest bundles)
        
        Returns:
            IPMI IP address, or None if not found
        """
        # First: Try ipmitool lan print files
        ipmitool_dir = self.bundle_path / 'ipmitool'
        if ipmitool_dir.exists():
            for lan_file in ipmitool_dir.glob('ipmitool_lan_print_*.txt'):
                ip = _search_file_for_pattern(lan_file, RegexPatterns.IPMI_IP_ADDRESS)
                if ip and ip != '0.0.0.0':
                    logging.debug(f"IPMI IP from ipmitool lan print: {ip}")
                    return ip
        
        # Second: Try ipmi_cmds_logs (harvest bundles)
        ipmi_cmds_log = self.bundle_path / 'ipmi_cmds_logs' / 'ipmi_cmds.log'
        if ipmi_cmds_log.exists():
            try:
                with open(ipmi_cmds_log, 'r') as f:
                    # Read in chunks to avoid loading huge files
                    for line in f:
                        if 'stdout IP Address' in line and ':' in line:
                            match = RegexPatterns.IPMI_IP_ADDRESS.search(line)
                            if match:
                                ip = match.group(1)
                                if ip != '0.0.0.0':
                                    logging.debug(f"IPMI IP from ipmi_cmds_logs: {ip}")
                                    return ip
            except IOError:
                pass
        
        return None
    
    def get_manufacturer_id(self) -> Optional[str]:
        """Extract Manufacturer ID from mc_info
        
        Returns:
            Manufacturer ID, or None if not found
        """
        mc_info_file = self.bundle_path / IPMITOOL_MC_INFO_PATH
        return _search_file_for_pattern(mc_info_file, RegexPatterns.MANUFACTURER_ID)
    
    def get_product_id(self) -> Optional[str]:
        """Extract Product ID from mc_info
        
        Returns:
            Product ID, or None if not found
        """
        mc_info_file = self.bundle_path / IPMITOOL_MC_INFO_PATH
        return _search_file_for_pattern(mc_info_file, RegexPatterns.PRODUCT_ID)


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
    
    def __init__(self, path: Optional[Path] = None, bundle_path: Optional[Path] = None):
        self._path = path
        self._bundle_path = bundle_path
        self._cache = {}
        self._vapi_loaded = False
        
        # Try to load vapi from bundle if available
        if bundle_path:
            self._try_load_vapi_from_bundle(bundle_path)
    
    def __repr__(self):
        return f'PDB({self._path or "None"})'
    
    def __bool__(self):
        return bool(self._path and self._path.exists())
    
    def _try_load_vapi_from_bundle(self, bundle_path: Path):
        """Try to load vapi from the bundle's vapi directory"""
        if self._vapi_loaded:
            return
        
        # Check bundle's vapi directory
        vapi_dir = bundle_path / 'vapi'
        if vapi_dir.exists():
            if try_import_vapi_from_path(vapi_dir.parent):
                self._vapi_loaded = True
                logging.debug(f"Loaded vapi from bundle: {bundle_path.name}")
                return
        
        # Check parent directory for sibling bundles with vapi
        try:
            parent_dir = bundle_path.parent
            if parent_dir and parent_dir.exists():
                # Try leader bundles first
                for sibling in sorted(parent_dir.iterdir()):
                    if not sibling.is_dir() or sibling == bundle_path:
                        continue
                    
                    if 'leader' in sibling.name.lower():
                        vapi_dir = sibling / 'vapi'
                        if vapi_dir.exists():
                            if try_import_vapi_from_path(vapi_dir.parent):
                                self._vapi_loaded = True
                                logging.debug(f"Loaded vapi from leader bundle: {sibling.name}")
                                return
        except (OSError, PermissionError) as e:
            logging.debug(f"Error searching for vapi in sibling bundles: {e}")
    
    @staticmethod
    def _is_leader_bundle(bundle_path: Path) -> bool:
        """Check if a bundle is a leader bundle
        
        A leader bundle is identified by having a non-empty leader_pid.info file.
        """
        leader_pid_file = bundle_path / 'leader_pid.info'
        if leader_pid_file.exists():
            try:
                return leader_pid_file.stat().st_size > 0
            except (OSError, PermissionError):
                pass
        return False
    
    @staticmethod
    def _is_vms_bundle(bundle_path: Path) -> bool:
        """Check if a bundle is a VMS bundle
        
        A VMS bundle is identified by having a docker_inspect_vast_vms file.
        """
        return (bundle_path / 'docker_inspect_vast_vms').exists()
    
    @staticmethod
    def _get_pdb_from_bundle(bundle: Path) -> Optional[Tuple[Path, Path]]:
        """Check if bundle has PDB and return (pdb_folder, bundle) or None
        
        Args:
            bundle: Path to bundle directory
            
        Returns:
            Tuple of (pdb_folder, bundle) or None if no PDB found
        """
        pdb_dir = bundle / 'pdb'
        if pdb_dir.exists():
            pdb_folders = [f for f in pdb_dir.iterdir() 
                          if f.is_dir() and RegexPatterns.PDB_TIMESTAMP.match(f.name)]
            if pdb_folders:
                latest_pdb = max(pdb_folders, key=lambda f: f.name)
                return (latest_pdb, bundle)
        return None
    
    @staticmethod
    def _categorize_sibling_bundles(parent_dir: Path, exclude: Path) -> Dict[str, List[Path]]:
        """Categorize bundles by type: leader, vms, other
        
        Args:
            parent_dir: Parent directory containing bundles
            exclude: Bundle path to exclude (usually current bundle)
            
        Returns:
            Dict with keys 'leader', 'vms', 'other' containing lists of bundle paths
        """
        categories = {'leader': [], 'vms': [], 'other': []}
        
        for sibling in parent_dir.iterdir():
            if not sibling.is_dir() or sibling == exclude:
                continue
            if not (sibling / METADATA_BUNDLE_ARGS).exists():
                continue
            
            if PDB._is_leader_bundle(sibling):
                categories['leader'].append(sibling)
                logging.debug(f"Detected leader bundle (non-empty leader_pid.info): {sibling.name}")
            elif PDB._is_vms_bundle(sibling):
                categories['vms'].append(sibling)
                logging.debug(f"Detected VMS bundle (docker_inspect_vast_vms exists): {sibling.name}")
            else:
                categories['other'].append(sibling)
        
        return categories
    
    @staticmethod
    def _search_priority_bundles(categories: Dict[str, List[Path]]) -> Optional[Tuple[Path, Path]]:
        """Search bundles in priority order: leader > vms
        
        Args:
            categories: Dict from _categorize_sibling_bundles
            
        Returns:
            Tuple of (pdb_folder, bundle) or None if no PDB found
        """
        # Search leader bundles first (highest priority)
        for sibling in categories['leader']:
            result = PDB._get_pdb_from_bundle(sibling)
            if result:
                logging.debug(f"Found PDB in leader bundle: {sibling.name}")
                return result
        
        # Then search VMS bundles
        for sibling in categories['vms']:
            result = PDB._get_pdb_from_bundle(sibling)
            if result:
                logging.debug(f"Found PDB in VMS bundle: {sibling.name}")
                return result
        
        return None
    
    @staticmethod
    def find_pdb_folder(bundle_path: Path) -> Optional[Tuple[Path, Path]]:
        """Find the PDB directory in a bundle (usually pdb/<timestamp>/)
        
        Search order:
        1. Sibling leader bundles (primary source - has cluster-wide PDB with device metadata)
        2. Sibling VMS bundles (secondary source - also has cluster-wide PDB)
        3. Current bundle's pdb/ directory (local node data)
        4. Other sibling bundles
        5. Parent directory's pdb/ (for standalone PDB)
        
        Leader/VMS bundle detection:
        - Leader: non-empty leader_pid.info file
        - VMS: docker_inspect_vast_vms file exists
        
        Returns:
            Tuple of (pdb_folder, bundle_containing_pdb) or None
        """
        # First: Check sibling leader and VMS bundles (ALWAYS prioritize these)
        parent_dir = bundle_path.parent
        if parent_dir and parent_dir.exists():
            try:
                categories = PDB._categorize_sibling_bundles(parent_dir, bundle_path)
                result = PDB._search_priority_bundles(categories)
                if result:
                    return result
            except (OSError, PermissionError) as e:
                logging.debug(f"Error searching for leader/VMS bundles: {e}")
        
        # Second: Check current bundle (local node data)
        result = PDB._get_pdb_from_bundle(bundle_path)
        if result:
            logging.debug(f"Found PDB in current bundle: {bundle_path.name}")
            return result
        
        # Third: Check other sibling bundles
        if parent_dir and parent_dir.exists():
            try:
                categories = PDB._categorize_sibling_bundles(parent_dir, bundle_path)
                for sibling in categories['other']:
                    result = PDB._get_pdb_from_bundle(sibling)
                    if result:
                        logging.debug(f"Found PDB in sibling bundle: {sibling.name}")
                        return result
                
                # Finally: Check parent directory's pdb/ (standalone case)
                parent_pdb_dir = parent_dir / 'pdb'
                if parent_pdb_dir.exists():
                    pdb_folders = [f for f in parent_pdb_dir.iterdir() 
                                  if f.is_dir() and RegexPatterns.PDB_TIMESTAMP.match(f.name)]
                    if pdb_folders:
                        latest_pdb = max(pdb_folders, key=lambda f: f.name)
                        logging.debug(f"Found PDB in parent directory")
                        return (latest_pdb, parent_dir)
            except (OSError, PermissionError) as e:
                logging.debug(f"Error searching for PDB in sibling bundles: {e}")
        
        return None
    
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
    
    def __init__(self, config_file: Path):
        self.config_file = config_file
        self.node_ip = None
        self.node_port = None
        self.node_type = None
        self.node_architecture = None
        self.dnode_index = None
        
        content = _read_text_file(config_file)
        if not content:
            return
        
        # Parse node info
        match = RegexPatterns.NODE_INFO.match(content)
        if match:
            self.node_ip = match.group('node_ip')
            self.node_port = match.group('node_port')
            self.node_type = match.group('node_type')
        
        # Parse architecture
        arch_match = RegexPatterns.NODE_ARCH.search(content)
        if arch_match:
            self.node_architecture = arch_match.group(1)
        
        # Parse dnode index
        index_match = RegexPatterns.DNODE_INDEX.search(content)
        if index_match:
            self.dnode_index = index_match.group(1)


# ============================================================================
# Core Data Model (Luna-inspired hierarchy)
# ============================================================================

class NetworkInfo:
    """Network configuration for a node"""
    def __init__(self, mgmt_ip=None, ipmi_ip=None, mac_address=None, data_ip=None,
                 mgmt_ip_from_cn=False, ipmi_ip_from_cn=False, data_ip_from_cn=False):
        self.mgmt_ip = mgmt_ip
        self.ipmi_ip = ipmi_ip
        self.mac_address = mac_address
        self.data_ip = data_ip
        # Track which fields came from configure_network (not from actual system output)
        self.mgmt_ip_from_cn = mgmt_ip_from_cn
        self.ipmi_ip_from_cn = ipmi_ip_from_cn
        self.data_ip_from_cn = data_ip_from_cn


class DTrayInfo:
    """DTray (Data Tray) information for multi-node DBox systems"""
    def __init__(self, serial_number=None, position=None, mcu_state=None, ipmi_ip=None):
        self.serial_number = serial_number
        self.position = position  # "Right" or "Left"
        self.mcu_state = mcu_state  # "active", "standby", etc.
        self.ipmi_ip = ipmi_ip


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
                else:
                    # Fallback to nvme_list.json for devices not currently exposed
                    path = self._get_device_path_from_nvme_list()
                    if path:
                        result['path'] = path
                
                logging.debug(f"Device {self.serial}: loaded from PDB")
                return result
            except Exception as e:
                logging.debug(f"Device {self.serial}: PDB read failed ({e}), falling back")
        
        # Second: Try nvme_cli_list.json
        nvme_cli_file = self._bundle.path / NVME_CLI_LIST_PATH
        nvme_data = _read_json_file(nvme_cli_file)
        if nvme_data:
            all_drives = nvme_data.get('drives', []) + nvme_data.get('nvrams', [])
            for drive in all_drives:
                if drive.get('serial') == self.serial:
                    logging.debug(f"Device {self.serial}: loaded from nvme_cli_list.json")
                    return drive
        
        # Third: Fallback to nvme_list.json
        # Try to enrich with location data from nvme_cli_list by matching device path
        nvme_list_file = self._bundle.path / NVME_LIST_PATH
        nvme_data = _read_json_file(nvme_list_file)
        if nvme_data:
            devices = nvme_data.get('Devices', [])
            for device in devices:
                if device.get('SerialNumber') == self.serial:
                    logging.debug(f"Device {self.serial}: loaded from nvme_list.json")
                    result = {
                        'serial': device.get('SerialNumber'),
                        'model': device.get('ModelNumber'),
                        'path': device.get('DevicePath'),
                        'size': device.get('PhysicalSize'),
                        'firmware_rev': device.get('Firmware'),
                        'index': device.get('Index'),
                    }
                    
                    # Try to enrich with location data from nvme_cli_list
                    # by matching DevicePath
                    location_info = self._get_location_from_nvme_cli_by_path(result['path'])
                    if location_info:
                        result['pci_switch_position'] = location_info.get('pci_switch_position')
                        result['pci_switch_slot'] = location_info.get('pci_switch_slot')
                        logging.debug(f"Device {self.serial}: enriched with location from nvme_cli_list.json")
                    
                    return result
        
        return result if result else None
    
    def _get_device_path_from_nvme_cli(self) -> Optional[str]:
        """Get device path from nvme_cli_list.json"""
        nvme_cli_file = self._bundle.path / NVME_CLI_LIST_PATH
        nvme_data = _read_json_file(nvme_cli_file)
        if nvme_data:
            all_drives = nvme_data.get('drives', []) + nvme_data.get('nvrams', [])
            for drive in all_drives:
                if drive.get('serial') == self.serial:
                    return drive.get('path')
        return None
    
    def _get_device_path_from_nvme_list(self) -> Optional[str]:
        """Get device path from nvme_list.json (fallback for devices not currently exposed)"""
        nvme_list_file = self._bundle.path / NVME_LIST_PATH
        nvme_data = _read_json_file(nvme_list_file)
        if nvme_data:
            devices = nvme_data.get('Devices', [])
            for device in devices:
                if device.get('SerialNumber') == self.serial:
                    return device.get('DevicePath')
        return None
    
    def _get_location_from_nvme_cli_by_path(self, device_path: str) -> Optional[Dict[str, Any]]:
        """Get location info from nvme_cli_list.json by matching device path
        
        This helps when a device is in nvme_list.json but not in nvme_cli_list.json by serial,
        but we can match by device path to get location metadata.
        """
        if not device_path:
            return None
        
        nvme_cli_file = self._bundle.path / NVME_CLI_LIST_PATH
        nvme_data = _read_json_file(nvme_cli_file)
        if nvme_data:
            all_drives = nvme_data.get('drives', []) + nvme_data.get('nvrams', [])
            for drive in all_drives:
                # Match by path (e.g., "/vast/dev/nvme10n1" or "/dev/nvme10n1")
                drive_path = drive.get('path', '')
                if drive_path == device_path or drive_path.endswith(device_path.replace('/dev/', '/')):
                    return {
                        'pci_switch_position': drive.get('pci_switch_position'),
                        'pci_switch_slot': drive.get('pci_switch_slot'),
                    }
        return None
    
    @cached_property
    def model(self) -> str:
        return self.data.get('model', UNKNOWN_VALUE) if self.data else UNKNOWN_VALUE
    
    @cached_property
    def path(self) -> str:
        return self.data.get('path', UNKNOWN_VALUE) if self.data else UNKNOWN_VALUE
    
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
        """Calculate location from PCI switch info
        
        Handles both string values (from JSON) and enum values (from PDB protobuf).
        """
        if self.pci_switch_position and self.pci_switch_slot:
            # Handle enum values from PDB (e.g., PCISwitchPosition.RIGHT)
            position = self.pci_switch_position
            if not isinstance(position, str):
                # If it's an enum, convert to string
                # This handles protobuf enums like "PCISwitchPosition.RIGHT" -> "RIGHT"
                position = str(position).split('.')[-1] if '.' in str(position) else str(position)
            
            return f"{position}-{self.pci_switch_slot}"
        return 'Unknown'
    
    @cached_property
    def drive_type(self) -> str:
        """Determine if this is SSD or NVRAM"""
        model_lower = self.model.lower()
        path_lower = self.path.lower()
        
        nvram_indicators = ['optane', 'dcpmm', 'ssdpe21k', 'ssdpf21', 'scm', 'nvdimm', 'pmem', 'pascari']
        
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
        config_file = self._bundle.path / PLATFORM_CONFIG_PATH
        if config_file.exists():
            return PlatformConfig(config_file)
        return None
    
    @cached_property
    def guid(self) -> Optional[str]:
        """Read self.guid file (Luna's node identifier)"""
        guid_file = self._bundle.path / SELF_GUID_PATH
        content = _read_text_file(guid_file)
        if content:
            return content.strip()
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
        monitor_file = self._bundle.path / MONITOR_RESULT_PATH
        return _read_json_file(monitor_file)
    
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
        """Node serial number with priority for BlueField vs traditional systems
        
        Priority:
        1. lspci_vvv_info VPD serial (ONLY for DNodes with BlueField DPU)
        2. FRU board serial (traditional servers and CNodes)
        3. monitor_result.json fallback
        
        Note: For CNodes, lspci VPD serial would be the NIC card serial, not the node serial.
        """
        extractor = SerialNumberExtractor(self._bundle.path)
        
        # First: Check if this is a DNode (BlueField DPU system)
        # Only use lspci serial for DNodes, as CNodes would return NIC card serial
        if self.node_type == 'dnode':
            lspci_serial = extractor.get_node_serial_from_lspci()
            if lspci_serial:
                return lspci_serial
        
        # Second: Check FRU for board serial (traditional servers and CNodes)
        fru_file = self._bundle.path / IPMITOOL_FRU_PATH
        if fru_file.exists():
            parser = FRUParser(fru_file)
            board_serial = parser.get_board_serial()
            if board_serial:
                return board_serial
        
        # Third: For DNodes without BlueField or FRU, try lspci as last resort
        if self.node_type == 'dnode':
            lspci_serial = extractor.get_node_serial_from_lspci()
            if lspci_serial:
                return lspci_serial
        
        # Fourth: Fallback to monitor data
        return self._node_info.get('serial_number', 'Unknown')
    
    @cached_property
    def position(self) -> str:
        return self._node_info.get('position', 'Unknown')
    
    @cached_property
    def _configure_network_params(self) -> Optional[Dict[str, str]]:
        """Parse vast-configure_network.py-params.ini file
        
        Returns dict of key=value pairs from the config file
        """
        config_file = self._bundle.path / 'vast-configure_network.py-params.ini'
        if not config_file.exists():
            return None
        
        try:
            params = {}
            with open(config_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        # Remove quotes and list brackets
                        value = value.strip().strip('"').strip("'").strip('[]')
                        params[key] = value
            return params if params else None
        except (IOError, OSError):
            return None
    
    def _get_data_ip_from_platform_config(self) -> Optional[str]:
        """Get data IP from platform.config (primary source)
        
        Returns:
            Data IP from platform.config or None
        """
        if self.platform_config and self.platform_config.node_ip:
            logging.debug(f"Node {self.name}: data IP from platform.config")
            return self.platform_config.node_ip
        return None
    
    def _get_ips_from_monitor_data(self) -> Dict[str, Optional[str]]:
        """Get IPs from monitor_result.json
        
        Returns:
            Dict with keys 'mgmt_ip', 'data_ip', 'mac_address'
        """
        result = {'mgmt_ip': None, 'data_ip': None, 'mac_address': None}
        
        if not self._monitor_data:
            return result
        
        nics = self._monitor_data.get('nics', {})
        data_ips = []
        
        for nic_name, nic_info in nics.items():
            nic_data = nic_info.get('info', {})
            address = nic_data.get('address', '')
            nic_mac = nic_data.get('mac_address', '')
            
            # Management IP (10.x.x.x)
            if address and address.startswith('10.') and not result['mgmt_ip']:
                result['mgmt_ip'] = address
                result['mac_address'] = nic_mac
            
            # Data IP (172.16.x.x)
            if address and address.startswith('172.16.'):
                data_ips.append(address)
        
        # Use the lowest data IP if found
        if data_ips:
            result['data_ip'] = min(data_ips)
            logging.debug(f"Node {self.name}: data IP from monitor_result.json")
        
        return result
    
    def _get_ips_from_configure_network(self) -> Dict[str, Any]:
        """Get IPs from configure_network params (fallback)
        
        Returns:
            Dict with keys: data_ip, mgmt_ip, ipmi_ip, and _from_cn flags
        """
        result = {
            'data_ip': None, 'mgmt_ip': None, 'ipmi_ip': None,
            'data_ip_from_cn': False, 'mgmt_ip_from_cn': False, 'ipmi_ip_from_cn': False
        }
        
        if not self._configure_network_params:
            return result
        
        cn_params = self._configure_network_params
        
        # Data IP from configure_network
        if 'template' in cn_params and 'node' in cn_params:
            try:
                template = cn_params['template']
                node_num = cn_params['node']
                # Parse template like "172.16.{network}.{node}"
                # Assume network=2 or 3 based on node number
                network = '3' if int(node_num) >= 100 else '2'
                result['data_ip'] = template.replace('{network}', network).replace('{node}', node_num)
                result['data_ip_from_cn'] = True
                logging.debug(f"Node {self.name}: data IP from configure_network")
            except (ValueError, KeyError):
                pass
        
        # MGMT IP from configure_network
        if 'ext_ip' in cn_params:
            result['mgmt_ip'] = cn_params['ext_ip']
            result['mgmt_ip_from_cn'] = True
            logging.debug(f"Node {self.name}: mgmt IP from configure_network")
        
        # IPMI IP from configure_network
        if 'ipmi_ip' in cn_params:
            result['ipmi_ip'] = cn_params['ipmi_ip']
            result['ipmi_ip_from_cn'] = True
            logging.debug(f"Node {self.name}: IPMI IP from configure_network")
        
        return result
    
    @cached_property
    def network(self) -> NetworkInfo:
        """Network configuration (lazy)
        
        Priority:
        1. config/platform.config for data IP (Luna's source)
        2. monitor_result.json for MGMT IP and MAC
        3. ipmitool for IPMI IP
        4. vast-configure_network.py-params.ini (fallback, marked with (!cn))
        """
        # Try platform.config first for data IP
        data_ip = self._get_data_ip_from_platform_config()
        
        # Try monitor data for MGMT IP, MAC, and data IP (if not from platform.config)
        monitor_ips = self._get_ips_from_monitor_data()
        mgmt_ip = monitor_ips['mgmt_ip']
        mac_address = monitor_ips['mac_address']
        if not data_ip:
            data_ip = monitor_ips['data_ip']
        
        # Try IPMI
        extractor = IPMIExtractor(self._bundle.path)
        ipmi_ip = extractor.get_ipmi_ip()
        
        # Fall back to configure_network
        cn_ips = self._get_ips_from_configure_network()
        if not data_ip:
            data_ip = cn_ips['data_ip']
            data_ip_from_cn = cn_ips['data_ip_from_cn']
        else:
            data_ip_from_cn = False
        
        if not mgmt_ip:
            mgmt_ip = cn_ips['mgmt_ip']
            mgmt_ip_from_cn = cn_ips['mgmt_ip_from_cn']
        else:
            mgmt_ip_from_cn = False
        
        if not ipmi_ip:
            ipmi_ip = cn_ips['ipmi_ip']
            ipmi_ip_from_cn = cn_ips['ipmi_ip_from_cn']
        else:
            ipmi_ip_from_cn = False
        
        return NetworkInfo(
            mgmt_ip=mgmt_ip,
            ipmi_ip=ipmi_ip,
            mac_address=mac_address,
            data_ip=data_ip,
            mgmt_ip_from_cn=mgmt_ip_from_cn,
            ipmi_ip_from_cn=ipmi_ip_from_cn,
            data_ip_from_cn=data_ip_from_cn
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
        """Box serial number with priority for DBox systems
        
        Priority:
        1. bmc_logs/*/fru.log (FRU 1 Chassis Serial - DBox serial)
        2. dmidecode.txt (last Chassis Serial - CBox serial)
        3. ipmitool FRU (fallback - Dtray serial)
        """
        extractor = SerialNumberExtractor(self._bundle.path)
        
        # First: Try bmc_logs FRU 1 (DBox serial for multi-node systems)
        bmc_fru_serial = extractor.get_box_serial_from_bmc_logs()
        if bmc_fru_serial and bmc_fru_serial != 'Uninitialized':
            return bmc_fru_serial
        
        # Second: Try dmidecode.txt (CBox serial)
        serial = extractor.get_box_serial_from_dmidecode()
        if serial and serial != 'Uninitialized':
            return serial
        
        # Third: Fall back to FRU (Dtray serial)
        fru_file = self._bundle.path / IPMITOOL_FRU_PATH
        if fru_file.exists():
            parser = FRUParser(fru_file)
            return parser.get_chassis_serial()
        return None
    
    @cached_property
    def dtray_info(self) -> Optional[DTrayInfo]:
        """DTray (Data Tray) information for multi-node DBox systems
        
        Returns DTray info only for DNodes in multi-node DBox systems.
        For single-node servers, DTray serial == Box serial, so we don't show it.
        """
        if self.node_type != 'dnode':
            return None
        
        # Extract DTray serial from FRU 0 Chassis Serial
        dtray_serial = None
        fru_file = self._bundle.path / IPMITOOL_FRU_PATH
        if fru_file.exists():
            parser = FRUParser(fru_file)
            dtray_serial = parser.get_chassis_serial(fru_id=0)
        
        # Skip if DTray serial is the same as Box serial (single-node server)
        if dtray_serial and dtray_serial == self.box_serial:
            return None
        
        # Determine position based on node position
        # Right side: "right" in position, Left side: "left" in position
        position = None
        if self.position:
            pos_lower = self.position.lower()
            if 'right' in pos_lower:
                position = 'Right'
            elif 'left' in pos_lower:
                position = 'Left'
        
        # Extract MCU state from BMC logs
        mcu_state = self._extract_mcu_state()
        
        # IPMI IP is shared by nodes on the same DTray
        ipmi_ip = self.network.ipmi_ip
        
        # Only return DTray info if we have at least the serial
        if dtray_serial:
            return DTrayInfo(
                serial_number=dtray_serial,
                position=position,
                mcu_state=mcu_state,
                ipmi_ip=ipmi_ip
            )
        
        return None
    
    @cached_property
    def manufacturer_id(self) -> Optional[str]:
        """Manufacturer ID from mc_info"""
        extractor = IPMIExtractor(self._bundle.path)
        return extractor.get_manufacturer_id()
    
    @cached_property
    def product_id(self) -> Optional[str]:
        """Product ID from mc_info"""
        extractor = IPMIExtractor(self._bundle.path)
        return extractor.get_product_id()
    
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
    def is_node_ipmi(self) -> bool:
        """Determine if IPMI IP should be shown in node section
        
        Returns:
            True: Show IPMI in node section (no DTray, or node has its own BMC)
            False: Don't show IPMI in node section (shown in DTray section instead)
        
        Logic:
            - Nodes with DTray: IPMI IP belongs to DTray (shared BMC), shown in DTray section
            - Nodes without DTray: IPMI IP belongs to node, shown in node section
        """
        return not bool(self.dtray_info)
    
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
        3. nvme_list.json - last resort fallback
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
        
        # Second: Fall back to nvme_cli_list.json and nvme_list.json (merge both sources)
        # Track which serials we've already added to avoid duplicates
        seen_serials = set()
        
        # Try nvme_cli_list.json first (preferred for current system state)
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
                    if serial and serial not in seen_serials:
                        devices.append(Device(serial, self._bundle))
                        seen_serials.add(serial)
                
                if devices:
                    logging.debug(f"Node {self.name}: loaded {len(devices)} devices from nvme_cli_list.json")
            except (json.JSONDecodeError, IOError):
                pass
        
        # Also try nvme_list.json (may have additional devices not in nvme_cli_list)
        nvme_list_file = self._bundle.path / 'nvme_list.json'
        if nvme_list_file.exists():
            try:
                with open(nvme_list_file, 'r') as f:
                    nvme_data = json.load(f)
                
                devices_list = nvme_data.get('Devices', [])
                devices_before = len(devices)
                
                for device_data in devices_list:
                    serial = device_data.get('SerialNumber')
                    if serial and serial not in seen_serials:
                        devices.append(Device(serial, self._bundle))
                        seen_serials.add(serial)
                
                devices_added = len(devices) - devices_before
                if devices_added > 0:
                    logging.debug(f"Node {self.name}: loaded {devices_added} additional devices from nvme_list.json")
            except (json.JSONDecodeError, IOError):
                pass
        
        return devices
    
    # Private helper methods
    def _extract_mcu_state(self) -> Optional[str]:
        """Extract MCU state from BMC logs and position
        
        For multi-node DBox systems with dual DTray controllers:
        - Right DTray (position "Right") = active (primary controller)
        - Left DTray (position "Left") = standby (secondary controller)
        
        Returns "active" or "standby" based on DTray position.
        """
        # Determine MCU state based on DTray position
        # Right side = active, Left side = standby
        if self.position:
            pos_lower = self.position.lower()
            if 'right' in pos_lower:
                return 'active?'
            elif 'left' in pos_lower:
                return 'standby?'
        
        # Fallback: try to detect from misc_info.log
        bmc_logs_dir = self._bundle.path / 'bmc_logs'
        if bmc_logs_dir.exists():
            misc_info_files = list(bmc_logs_dir.glob('*/misc_info.log'))
            if misc_info_files:
                try:
                    with open(misc_info_files[0], 'r') as f:
                        lines = f.readlines()
                    
                    for line in lines:
                        line_stripped = line.strip()
                        if line_stripped in ['Standby', 'Inactive']:
                            return line_stripped.lower()
                        elif line_stripped == 'Master':
                            return 'active'
                except IOError:
                    pass
        
        return None
    
    @staticmethod
    def _extract_nics_from_ibdev(ibdev_file: Path) -> Optional[str]:
        """Extract NIC types from ibdev2netdev.txt
        
        Parses the file to find ConnectX-5/6/7 and BlueField cards, groups by PCI slot.
        
        Returns:
        - ConnectX cards: "CX5, CX6, CX7"
        - BlueField cards: "IB BF 2x100Gbs" (format: IB BF {ports}x{speed}Gbs)
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
                
                # Check for BlueField card first
                if 'BlueField Controller card' in line:
                    # Extract port count: "Dual Port" -> 2, "Single Port" -> 1
                    port_count = 1  # Default
                    if 'Dual Port' in line:
                        port_count = 2
                    elif 'Quad Port' in line:
                        port_count = 4
                    elif 'Single Port' in line:
                        port_count = 1
                    
                    # Extract speed: "100Gbs" -> 100, "200Gbs" -> 200
                    speed_match = re.search(r'(\d+)Gb', line)
                    speed = speed_match.group(1) if speed_match else '?'
                    
                    pci_slots[pci_slot] = f'IB BF {port_count}x{speed}Gbs'
                    continue
                
                # Extract ConnectX type
                cx_match = re.search(r'ConnectX-(\d+)', line)
                if cx_match:
                    pci_slots[pci_slot] = f'CX{cx_match.group(1)}'
                else:
                    pci_slots[pci_slot] = 'Unknown NIC'
            
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
        pdb_result = PDB.find_pdb_folder(self.path)
        if pdb_result:
            pdb_folder, bundle_with_pdb = pdb_result
            logging.debug(f"Bundle {self.path.name}: found PDB at {pdb_folder.name}")
            return PDB(pdb_folder, bundle_path=bundle_with_pdb)
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
    def nodes_by_box(self, box_serial: str) -> List[Tuple[Node, Bundle]]:
        """Get all nodes in a specific box"""
        results = []
        for bundle in self._bundles:
            node = bundle.node
            if node and node.box_serial == box_serial:
                results.append((node, bundle))
        return results
    
    @cached_method
    def find_device(self, serial: str) -> Optional[Tuple[Device, Node, Bundle]]:
        """Find a device across all bundles"""
        for bundle in self._bundles:
            device = bundle.find_device(serial)
            if device:
                return device, bundle.node, bundle
        return None
    
    def _quick_hostname_check(self, bundle: Bundle) -> Optional[str]:
        """Quickly extract hostname without loading full node data
        
        Args:
            bundle: Bundle to check
            
        Returns:
            Hostname or None
        """
        systemctl_file = bundle.path / SYSTEMCTL_STATUS_PATH
        if systemctl_file.exists():
            try:
                with open(systemctl_file, 'r') as f:
                    first_line = f.readline().strip()
                if first_line.startswith('●'):
                    return first_line[1:].strip()
            except (IOError, OSError):
                pass
        return None
    
    def _create_search_pattern(self, identifier: str) -> Tuple[Optional[Any], bool]:
        """Create regex pattern if identifier looks like regex
        
        Args:
            identifier: Search identifier
            
        Returns:
            Tuple of (compiled_pattern, is_regex)
        """
        if any(c in identifier for c in ['.*', '[', ']', '^', '$', '\\', '|']):
            try:
                return re.compile(identifier, re.IGNORECASE), True
            except re.error:
                pass
        return None, False
    
    def _fast_hostname_search(self, identifier: str, pattern: Optional[Any]) -> List[Bundle]:
        """Quick search using just hostname without loading full nodes
        
        Args:
            identifier: Search identifier
            pattern: Compiled regex pattern (if any)
            
        Returns:
            List of candidate bundles
        """
        candidate_bundles = []
        for bundle in self._bundles:
            hostname = self._quick_hostname_check(bundle)
            if not hostname:
                continue
            
            # Exact match on hostname
            if hostname == identifier:
                candidate_bundles.append(bundle)
                continue
            
            # Regex match on hostname
            if pattern and pattern.search(hostname):
                candidate_bundles.append(bundle)
                continue
            
            # Partial match for common patterns like "dnode213" matching "cluster-dnode213"
            if identifier.lower() in hostname.lower():
                candidate_bundles.append(bundle)
        
        return candidate_bundles
    
    def _exact_match_search(self, identifier: str) -> List[Tuple[Node, Bundle]]:
        """Search for exact matches on node fields
        
        Args:
            identifier: Search identifier
            
        Returns:
            List of (node, bundle) tuples
        """
        results = []
        for bundle in self._bundles:
            node = bundle.node
            if not node:
                continue
            
            if (node.name == identifier or
                node.serial_number == identifier or
                node.network.mgmt_ip == identifier or
                node.network.data_ip == identifier or
                node.box_serial == identifier):
                if (node, bundle) not in results:
                    results.append((node, bundle))
        
        return results
    
    def _regex_match_search(self, pattern: Any) -> List[Tuple[Node, Bundle]]:
        """Search for regex matches on node fields
        
        Args:
            pattern: Compiled regex pattern
            
        Returns:
            List of (node, bundle) tuples
        """
        results = []
        for bundle in self._bundles:
            node = bundle.node
            if not node:
                continue
            
            if (pattern.search(node.name) or
                pattern.search(node.serial_number or '') or
                pattern.search(node.network.mgmt_ip or '') or
                pattern.search(node.network.data_ip or '') or
                pattern.search(node.box_serial or '')):
                if (node, bundle) not in results:
                    results.append((node, bundle))
        
        return results
    
    @cached_method
    def find_node(self, identifier: str) -> List[Tuple[Node, Bundle]]:
        """Find node(s) by name, serial, IP, or regex pattern
        
        Optimized to quickly check node identity without loading full node data.
        
        Search strategies:
        1. Fast hostname check (no full node load)
        2. Full exact match search
        3. Regex search (if identifier looks like regex)
        4. Fallback regex search (treat as regex even if not obvious)
        """
        results = []
        pattern, is_regex = self._create_search_pattern(identifier)
        
        # Strategy 1: Fast hostname check
        candidate_bundles = self._fast_hostname_search(identifier, pattern)
        if candidate_bundles:
            logging.debug(f"Fast hostname check found {len(candidate_bundles)} candidate bundles")
            for bundle in candidate_bundles:
                node = bundle.node
                if node:
                    results.append((node, bundle))
            
            # If we found exact matches, return them
            if any(node.name == identifier for node, _ in results):
                return results
            
            # If we have results from hostname match and not regex, return them
            if results and not is_regex:
                return results
        
        # Strategy 2: Full exact match search
        if not results:
            logging.debug(f"No fast matches, doing full node scan for '{identifier}'")
            results = self._exact_match_search(identifier)
        
        # Strategy 3: Regex search (if identifier looks like regex)
        if not results and is_regex and pattern:
            results = self._regex_match_search(pattern)
        
        # Strategy 4: Fallback regex search (treat as regex even if not obvious)
        if not results and not is_regex:
            logging.debug(f"No exact matches, trying regex fallback for '{identifier}'")
            try:
                pattern = re.compile(identifier, re.IGNORECASE)
                results = self._regex_match_search(pattern)
            except re.error:
                pass  # If it's not a valid regex, just return empty results
        
        return results


# ============================================================================
# Cluster Initialization (similar to Luna's cluster discovery)
# ============================================================================

class ClusterDiscovery:
    """Discover and initialize cluster from bundle directories"""
    
    @staticmethod
    def find_bundle_directories(max_depth: int = 5) -> List[Path]:
        """Find all bundle directories by looking for METADATA/BUNDLE_ARGS
        
        Optimized for file servers: stops at depth 5 and only searches likely bundle locations.
        """
        bundle_dirs = []
        current_dir = Path('.')
        
        # Check current directory first
        if (current_dir / 'METADATA' / 'BUNDLE_ARGS').exists():
            bundle_dirs.append(current_dir)
            logging.debug(f"Found bundle in current directory")
            return bundle_dirs  # Stop if current dir is a bundle
        
        # Recursively search subdirectories, with aggressive early termination
        def search_directory(directory: Path, current_level: int = 0) -> bool:
            """Returns True if bundles were found at this level"""
            if current_level > max_depth:
                return False
            
            found_at_level = False
            dirs_to_recurse = []
            
            # Skip known non-bundle directory names
            skip_dirs = {'compatible_vapi', 'venv', '__pycache__', 'node_modules', 
                        'pdb', 'config', 'ipmitool', 'bmc_logs', 'systemctl_output',
                        'METADATA', 'ipmi_cmds_logs', 'nvme_cli_list', 'dmidecode',
                        'ipmi_lan_print', 'lspci', 'ibdev2netdev'}
            
            try:
                # Single pass through directory items
                for item in directory.iterdir():
                    # Skip non-directories and hidden directories immediately
                    if not item.is_dir() or item.name.startswith('.'):
                        continue
                    
                    # Skip known non-bundle directories
                    if item.name in skip_dirs:
                        continue
                    
                    # Check if this is a bundle directory
                    if (item / 'METADATA' / 'BUNDLE_ARGS').exists():
                        bundle_dirs.append(item)
                        found_at_level = True
                        logging.debug(f"Found bundle: {item.name} at level {current_level}")
                    else:
                        # Remember to recurse into this directory later (if needed)
                        dirs_to_recurse.append(item)
                
                # If bundles found at this level, STOP - don't search deeper
                # Bundles are typically all at the same level (e.g., harvest-* directories)
                if found_at_level and current_level > 0:
                    logging.debug(f"Bundles found at level {current_level}, stopping deeper search")
                    return True
                
                # Only recurse if no bundles found at this level
                if not found_at_level:
                    for item in dirs_to_recurse:
                        search_directory(item, current_level + 1)
                    
            except (PermissionError, OSError) as e:
                logging.debug(f"Skipping {directory}: {e}")
                pass
            
            return found_at_level
        
        search_directory(current_dir)
        logging.debug(f"Found {len(bundle_dirs)} total bundles")
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


def extract_case_from_path(path_str: str) -> Optional[str]:
    """Extract case number from path string
    
    Args:
        path_str: Path string to search for case number
    """
    try:
        # Look for Case-######## pattern
        match = re.search(r'Case-(\d{8})', path_str, re.IGNORECASE)
        if match:
            return match.group(1)
    except Exception:
        pass
    return None


def resolve_case_number(explicit_case: Optional[str], original_path: str) -> Optional[str]:
    """Resolve case number from explicit argument or path (data collection)
    
    Args:
        explicit_case: Explicitly provided case number (--case argument)
        original_path: Path to search for case number
    
    Returns:
        Case number if found (with '?' suffix if auto-detected), None otherwise
    """
    if explicit_case:
        # Explicitly provided case number - return as-is
        return explicit_case
    
    # Try to extract from path (auto-detect)
    path_case = extract_case_from_path(original_path)
    if path_case:
        # Add '?' suffix to indicate auto-detected
        return path_case + '?'
    
    return None


def format_case_number(case_number: Optional[str]) -> str:
    """Format case number for display (rendering only)
    
    Args:
        case_number: Case number to format (may include '?' suffix), None for default
    
    Returns: Formatted case label
    """
    if case_number:
        # Check if this is auto-detected (has '?' suffix)
        if case_number.endswith('?'):
            formatted_case = str(case_number[:-1]).zfill(8)
            return f"Case-{formatted_case}?"
        else:
            # Explicitly provided case number
            formatted_case = str(case_number).zfill(8)
            return f"Case-{formatted_case}"
    
    # Default
    return "Case-000....."


def list_nodes(node_bundle_list: List[Tuple[Node, Bundle]], title: str = "Available Nodes"):
    """List specific nodes in tabular format"""
    if not node_bundle_list:
        print("No nodes found", file=sys.stderr)
        return
    
    # Group by box (but don't group nodes with Unknown box serial)
    box_nodes = defaultdict(list)
    unknown_box_nodes = []
    for node, bundle in node_bundle_list:
        if node:
            if node.box_serial and node.box_serial != 'Unknown':
                box_nodes[node.box_serial].append((node, bundle))
            else:
                # Each node with Unknown box serial gets its own group
                unknown_box_nodes.append([(node, bundle)])
    
    # Sort boxes by first node's MGMT IP (numerically)
    def get_first_mgmt_ip_key(item):
        box_serial, node_list = item
        if not node_list:
            return (0, 0, 0, 0)
        # Sort nodes within box by MGMT IP to find the first one
        sorted_nodes = sorted(node_list, key=lambda x: ip_to_sort_key(x[0].network.mgmt_ip))
        return ip_to_sort_key(sorted_nodes[0][0].network.mgmt_ip)
    
    sorted_boxes = sorted(box_nodes.items(), key=get_first_mgmt_ip_key)
    
    # Add unknown box nodes (each as a separate "box")
    for unknown_node_list in unknown_box_nodes:
        sorted_boxes.append(('Unknown', unknown_node_list))
    
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
            # Add (!cn) marker for IPs from configure_network
            data_ip_str = node.network.data_ip or 'Unknown'
            if node.network.data_ip_from_cn:
                data_ip_str += ' (!cn)'
            
            mgmt_ip_str = node.network.mgmt_ip or 'Unknown'
            if node.network.mgmt_ip_from_cn:
                mgmt_ip_str += ' (!cn)'
            
            ipmi_ip_str = node.network.ipmi_ip or 'Unknown'
            if node.network.ipmi_ip_from_cn:
                ipmi_ip_str += ' (!cn)'
            
            table.add_row(
                node.name,
                node.node_type.upper(),
                node.position,
                data_ip_str,
                mgmt_ip_str,
                ipmi_ip_str,
                node.serial_number,
                node.box_serial or 'Unknown',
                node.manufacturer_id or '',
                node.product_id or '',
                node.network.mac_address or 'Unknown',
                bundle.create_time or 'Unknown',
                bundle.display_path
            )
    
    print(title + ":")
    print(render_table(table))
    
    # Check if any (!cn) markers were added and print legend
    _print_cn_legend([node for node, _ in node_bundle_list])


def list_all_nodes(cluster: Cluster):
    """List all available nodes in tabular format"""
    node_bundle_list = [(bundle.node, bundle) for bundle in cluster.bundles if bundle.node]
    list_nodes(node_bundle_list, "Available Nodes")


# ============================================================================
# Helper Functions for RMA Form Rendering
# ============================================================================

def _format_node_type(node_type: str) -> str:
    """Format node type for display by uppercasing first 2 chars.
    
    Examples: 'dnode' -> 'DNode', 'cnode' -> 'CNode'
    """
    if len(node_type) >= 2:
        return node_type[:2].upper() + node_type[2:]
    return node_type.upper()


def _has_cn_marker(node: Node) -> bool:
    """Check if a single node has any (!cn) markers from configure_network"""
    return (node.network.data_ip_from_cn or 
            node.network.mgmt_ip_from_cn or 
            node.network.ipmi_ip_from_cn)


def _print_cn_legend(nodes: List[Node], newline: bool = True):
    """Print (!cn) legend if any nodes have configure_network markers
    
    Args:
        nodes: List of nodes to check for markers
        newline: Whether to add a newline before the legend
    """
    if any(_has_cn_marker(n) for n in nodes):
        prefix = "\n" if newline else ""
        print(f"{prefix}(!cn) = Value from vast-configure_network.py-params.ini (not from actual system output)")


def _group_siblings_by_dtray(node: Node, sibling_nodes: List[Node]) -> tuple:
    """Group sibling nodes by DTray for multi-node DBox systems.
    
    Siblings are grouped into:
    - Same DTray as primary node (including those with no DTray info)
    - Other DTrays (grouped by DTray serial number)
    
    Args:
        node: Primary node being displayed
        sibling_nodes: List of sibling nodes to group
    
    Returns:
        Tuple of (same_dtray_siblings, other_dtray_siblings_dict)
        where other_dtray_siblings_dict is {dtray_serial: [nodes]}
    """
    primary_dtray_serial = node.dtray_info.serial_number if node.dtray_info else None
    same_dtray_siblings = []
    other_dtray_siblings = {}
    
    for sibling in sibling_nodes:
        sib_dtray_serial = sibling.dtray_info.serial_number if sibling.dtray_info else None
        
        if sib_dtray_serial == primary_dtray_serial or sib_dtray_serial is None:
            same_dtray_siblings.append(sibling)
        else:
            if sib_dtray_serial not in other_dtray_siblings:
                other_dtray_siblings[sib_dtray_serial] = []
            other_dtray_siblings[sib_dtray_serial].append(sibling)
    
    return same_dtray_siblings, other_dtray_siblings


def _add_node_details_to_table(table: Table, node: Node):
    """Helper function to add node SerialNumber, MAC, and IPs to table
    
    The node's metadata (is_node_ipmi) determines whether to show IPMI IP.
    
    Args:
        table: Table object to add rows to
        node: Node object with network information
    """
    # SerialNumber and MAC first
    table.add_row("SerialNumber", node.serial_number)
    table.add_row("MAC Address", node.network.mac_address or "")
    
    # Then all IPs at the end
    # Add (!cn) markers for IPs from configure_network
    data_ip_str = node.network.data_ip or ""
    if node.network.data_ip_from_cn and data_ip_str:
        data_ip_str += " (!cn)"
    table.add_row("IP", data_ip_str)
    
    mgmt_ip_str = node.network.mgmt_ip or ""
    if node.network.mgmt_ip_from_cn and mgmt_ip_str:
        mgmt_ip_str += " (!cn)"
    table.add_row("MGMT IP", mgmt_ip_str)
    
    # IPMI IP: use node's metadata to decide
    if node.is_node_ipmi:
        ipmi_ip_str = node.network.ipmi_ip or ""
        if node.network.ipmi_ip_from_cn and ipmi_ip_str:
            ipmi_ip_str += " (!cn)"
        table.add_row("IPMI IP", ipmi_ip_str)


def _render_node_and_siblings(table: Table, node: Node, sibling_nodes: List[Node], 
                               include_dtray: bool = True, include_index: bool = True,
                               include_model: bool = False, include_nics: bool = False,
                               node_section_label: Optional[str] = None):
    """Unified function to render primary node and siblings with DTray awareness.
    
    This function provides consistent rendering across all display modes (drive listing,
    drive RMA form, node RMA form) with DTray-aware sibling grouping.
    
    Args:
        table: Table object to add rows to
        node: Primary node to display
        sibling_nodes: List of sibling nodes
        include_dtray: Whether to show DTray information (for multi-node DBox systems)
        include_index: Whether to show Index field for primary node
        include_model: Whether to show Model field for primary node
        include_nics: Whether to show NICs field for primary node
        node_section_label: Custom label for node section (default: auto-detect from node_type)
    """
    # DTray information (only for DNodes in multi-node systems)
    if include_dtray and node.dtray_info:
        dtray = node.dtray_info
        table.add_row("", "associated DTray", style="subtitle")
        table.add_row("Position", dtray.position or '')
        table.add_row("SerialNumber", dtray.serial_number or '')
        table.add_row("MCU State", dtray.mcu_state or '')
        table.add_row("IPMI IP", dtray.ipmi_ip or '')
    
    # Primary node information
    if node_section_label is None:
        node_section_label = _format_node_type(node.node_type)
    
    table.add_row("", node_section_label, style="subtitle")
    
    if include_index:
        index = "1" if node.position == "bottom" else "2"
        table.add_row("Index", index)
    
    if include_model:
        table.add_row("Model", node.model)
    
    if include_nics and node.nics:
        table.add_row("NICs", node.nics)
    
    table.add_row("name", node.name)
    table.add_row("position", node.position)
    _add_node_details_to_table(table, node)
    
    # Group sibling nodes by DTray (for multi-node DBox systems)
    same_dtray_siblings, other_dtray_siblings = _group_siblings_by_dtray(node, sibling_nodes)
    
    # Display siblings on same DTray first
    sibling_counter = 1
    for sibling in same_dtray_siblings:
        node_type_display = _format_node_type(sibling.node_type)
        
        header = f"sibling {node_type_display}"
        if len(sibling_nodes) > 1:
            header += f" {sibling_counter}"
        sibling_counter += 1
        table.add_row("", header, style="subtitle")
        table.add_row("name", sibling.name)
        table.add_row("position", sibling.position)
        _add_node_details_to_table(table, sibling)
    
    # Display siblings on other DTrays with DTray info headers
    if include_dtray:
        for dtray_serial, dtray_siblings in sorted(other_dtray_siblings.items()):
            # Show "other DTray" section
            if dtray_siblings and dtray_siblings[0].dtray_info:
                other_dtray = dtray_siblings[0].dtray_info
                table.add_row("", "other DTray", style="subtitle")
                table.add_row("Position", other_dtray.position or '')
                table.add_row("SerialNumber", other_dtray.serial_number or '')
                table.add_row("MCU State", other_dtray.mcu_state or '')
                table.add_row("IPMI IP", other_dtray.ipmi_ip or '')
            
            # Display siblings on this DTray
            # Sort by position (bottom first, then top) for consistent ordering
            dtray_siblings_sorted = sorted(dtray_siblings, key=lambda s: (s.position != 'bottom' if s.position else True))
            
            for sibling in dtray_siblings_sorted:
                # Format node type
                node_type_display = _format_node_type(sibling.node_type)
                
                # For nodes on other DTrays, use "other DNode bottom/top" format
                position_desc = ''
                if sibling.position:
                    pos_lower = sibling.position.lower()
                    if 'bottom' in pos_lower:
                        position_desc = ' bottom'
                    elif 'top' in pos_lower:
                        position_desc = ' top'
                
                header = f"other {node_type_display}{position_desc}"
                table.add_row("", header, style="subtitle")
                table.add_row("name", sibling.name)
                table.add_row("position", sibling.position)
                _add_node_details_to_table(table, sibling)


# ============================================================================
# RMA Form Builder
# ============================================================================

class RMAFormBuilder:
    """Builder for RMA forms with common structure and fields
    
    Consolidates the repetitive form construction logic used in node and drive RMA forms.
    """
    
    def __init__(self, cluster: Cluster, case_number: Optional[str]):
        """Initialize RMA form builder
        
        Args:
            cluster: Cluster object containing cluster name
            case_number: Case number from path or None
        """
        self.table = Table()
        self.cluster = cluster
        self.case_number = case_number
        self.nodes = []  # Track nodes for legend
    
    def add_header(self, title: str, fru_code: str = "") -> 'RMAFormBuilder':
        """Add form header (title and FRU code)
        
        Args:
            title: Form title (e.g., "DNODE Replacement", "SSD Replacement")
            fru_code: FRU code placeholder (e.g., "FRU-___-DNODE-___")
        
        Returns:
            Self for method chaining
        """
        self.table.add_row(title, fru_code)
        self.table.add_separator()
        return self
    
    def add_standard_fields(self) -> 'RMAFormBuilder':
        """Add standard RMA fields (case, cluster, tracking, delivery, room)
        
        Returns:
            Self for method chaining
        """
        # Case number (with smart default)
        case_label = format_case_number(self.case_number)
        self.table.add_row(case_label, "RMA-0000.... / FE-000.....")
        
        # Standard fields
        self.table.add_row("Cluster", self.cluster.cluster_name)
        self.table.add_row("Tracking", "FedEx #  <TBD>")
        self.table.add_row("Delivery ETA", "")
        self.table.add_row("Room / Rack / RU", "")
        return self
    
    def add_box_serial(self, box_serial: Optional[str], label: str = "Box S/N") -> 'RMAFormBuilder':
        """Add box serial number field
        
        Args:
            box_serial: Box serial number or None
            label: Field label (default: "Box S/N")
        
        Returns:
            Self for method chaining
        """
        self.table.add_row(label, box_serial or '')
        return self
    
    def add_drive_info(self, device: Device, node: Node) -> 'RMAFormBuilder':
        """Add drive-specific information (location, index, path, model, serial)
        
        Args:
            device: Device object
            node: Node containing the device (for position/index)
        
        Returns:
            Self for method chaining
        """
        self.table.add_row("Location in Box", device.location_in_box)
        index = "1" if node.position == "bottom" else "2"
        self.table.add_row("Index", index)
        self.table.add_row("DevicePath", device.path)
        self.table.add_row("Model", device.model)
        self.table.add_row("SerialNumber", device.serial)
        return self
    
    def add_node_and_siblings(self, node: Node, sibling_nodes: List[Node],
                              include_dtray: bool = True, include_index: bool = True,
                              include_model: bool = False, include_nics: bool = False,
                              node_section_label: Optional[str] = None) -> 'RMAFormBuilder':
        """Add node and sibling node information
        
        Args:
            node: Primary node
            sibling_nodes: List of sibling nodes
            include_dtray: Whether to show DTray info
            include_index: Whether to show Index field
            include_model: Whether to show Model field
            include_nics: Whether to show NICs field
            node_section_label: Custom label for node section
        
        Returns:
            Self for method chaining
        """
        _render_node_and_siblings(self.table, node, sibling_nodes,
                                  include_dtray=include_dtray, include_index=include_index,
                                  include_model=include_model, include_nics=include_nics,
                                  node_section_label=node_section_label)
        self.nodes = [node] + sibling_nodes
        return self
    
    def render(self, print_legend: bool = True) -> str:
        """Render the form and optionally print legend
        
        Args:
            print_legend: Whether to print the (!cn) legend if applicable
        
        Returns:
            Rendered table string
        """
        result = render_table(self.table)
        print(result)
        
        if print_legend:
            _print_cn_legend(self.nodes)
        
        return result


def show_node_rma_form(node: Node, sibling_nodes: List[Node], cluster: Cluster, case_number: Optional[str]):
    """Show RMA form for a node"""
    node_type_display = node.node_type.upper()
    
    (RMAFormBuilder(cluster, case_number)
        .add_header(f"{node_type_display} Replacement", f"FRU-___-{node_type_display}-___")
        .add_standard_fields()
        .add_box_serial(node.box_serial, "Box S/N")
        .add_node_and_siblings(node, sibling_nodes, 
                               include_dtray=True, include_model=True, include_nics=True)
        .render())


def show_drive_rma_form(device: Device, node: Node, sibling_nodes: List[Node], cluster: Cluster, case_number: Optional[str]):
    """Show RMA form for a drive"""
    title = "SSD Replacement" if device.drive_type == "ssd" else "NVRAM Replacement"
    node_type_display = _format_node_type(node.node_type)
    
    (RMAFormBuilder(cluster, case_number)
        .add_header(title, "FRU_...")
        .add_standard_fields()
        .add_box_serial(node.box_serial, "DBox")
        .add_drive_info(device, node)
        .add_node_and_siblings(node, sibling_nodes,
                               include_dtray=True, include_index=False,
                               node_section_label=f"associated {node_type_display}")
        .render())


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
            # Skip boot drives (typically /dev/nvme0n1)
            if device.path == '/dev/nvme0n1':
                continue
            all_devices.append((device, n))
    
    if not all_devices:
        print(f"No devices found", file=sys.stderr)
        return
    
    # Render node section
    table = Table()
    table.add_row("DBox S/N", node.box_serial or '')
    
    # Render node and siblings with DTray awareness
    _render_node_and_siblings(table, node, sibling_nodes,
                              include_dtray=True, include_index=True, include_model=True)
    
    print(render_table(table))
    
    # Check if any (!cn) markers were added and print legend
    _print_cn_legend([node] + sibling_nodes, newline=False)
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
    parser.add_argument('--original-path-name', metavar='PATH', default=str(Path.cwd()), help=argparse.SUPPRESS)  # Undocumented: for Docker wrapper
    
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
    
    # Resolve case number (data collection - do this once)
    resolved_case = resolve_case_number(args.case, args.original_path_name)
    
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
            
            show_drive_rma_form(device, node, siblings, cluster, resolved_case)
        
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
    show_node_rma_form(node, siblings, cluster, resolved_case)


if __name__ == "__main__":
    main()

