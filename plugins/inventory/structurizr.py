# -*- coding: utf-8 -*-
# GNU General Public License v3.0+
# (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
name: structurizr
short_description: Structurizr DSL/JSON inventory source
description:
    - Generates Ansible inventory from Structurizr workspace JSON export.
    - Parses DeploymentNodes and InfrastructureNodes to create hosts and groups.
    - Maps Structurizr properties to Ansible host variables.
    - Supports filtering by environment and tags.
author:
    - Nicolas Karageuzian (@nkarageuzian)
version_added: "0.1.0"
extends_documentation_fragment:
    - inventory_cache
    - constructed
options:
    plugin:
        description: Token that ensures this is a source file for the 'structurizr' plugin.
        required: true
        choices: ['deepthought_solutions.structurizr_inventory.structurizr', 'structurizr']
    source:
        description:
            - Path to the Structurizr JSON export file.
            - Can be a local file path or a URL (http/https).
        required: true
        type: str
    environment:
        description:
            - Filter deployment nodes by environment name.
            - If not specified, all environments are included.
        required: false
        type: str
    include_infrastructure_nodes:
        description:
            - Whether to include InfrastructureNodes as hosts.
            - When true, infrastructure nodes (load balancers, databases, etc.) become hosts.
        required: false
        type: bool
        default: true
    include_software_system_instances:
        description:
            - Whether to include SoftwareSystemInstances as hosts.
            - When true, software system instances become hosts.
        required: false
        type: bool
        default: false
    include_container_instances:
        description:
            - Whether to include ContainerInstances as hosts.
            - When true, container instances become hosts.
        required: false
        type: bool
        default: false
    group_by_environment:
        description:
            - Create groups based on deployment environment names.
        required: false
        type: bool
        default: true
    group_by_tags:
        description:
            - Create groups based on Structurizr tags.
        required: false
        type: bool
        default: true
    group_by_technology:
        description:
            - Create groups based on technology property.
        required: false
        type: bool
        default: false
    group_by_hierarchy:
        description:
            - Create nested groups based on deployment node hierarchy.
            - E.g., datacenter > rack > server creates datacenter and rack groups.
        required: false
        type: bool
        default: true
    host_identifier:
        description:
            - Which property to use as the Ansible host identifier.
            - Can be 'name', 'id', or a property name from the Structurizr model.
            - If a property is specified and not found, falls back to 'name'.
        required: false
        type: str
        default: name
    property_prefix:
        description:
            - Prefix to add to Structurizr properties when mapping to host variables.
            - E.g., 'structurizr_' would create 'structurizr_ansible_user' from 'ansible_user'.
            - Set to empty string to use property names directly.
        required: false
        type: str
        default: ""
    ansible_property_passthrough:
        description:
            - List of property names that should be passed directly as Ansible variables.
            - Properties starting with 'ansible_' are always passed through.
        required: false
        type: list
        elements: str
        default: []
"""

EXAMPLES = r"""
# Simple usage with a local JSON file
plugin: deepthought_solutions.structurizr_inventory.structurizr
source: ./workspace.json

# Filter by environment
plugin: deepthought_solutions.structurizr_inventory.structurizr
source: ./workspace.json
environment: Production

# Include infrastructure nodes and group by tags
plugin: deepthought_solutions.structurizr_inventory.structurizr
source: ./workspace.json
include_infrastructure_nodes: true
group_by_tags: true
group_by_technology: true

# Use a property as host identifier (e.g., FQDN stored in properties)
plugin: deepthought_solutions.structurizr_inventory.structurizr
source: ./workspace.json
host_identifier: fqdn

# Use with constructed groups
plugin: deepthought_solutions.structurizr_inventory.structurizr
source: ./workspace.json
strict: false
compose:
  ansible_host: structurizr_ip_address
groups:
  webservers: "'web' in tags"
  databases: "technology == 'PostgreSQL'"
"""

import json
import os
import re

from ansible.errors import AnsibleParserError
from ansible.plugins.inventory import BaseInventoryPlugin, Constructable, Cacheable


class InventoryModule(BaseInventoryPlugin, Constructable, Cacheable):
    """Inventory plugin for Structurizr workspace JSON."""

    NAME = "deepthought_solutions.structurizr_inventory.structurizr"

    def __init__(self):
        super(InventoryModule, self).__init__()
        self._hosts = []
        self._cache_key = None
        self._inventory_path = None

    def verify_file(self, path):
        """Verify this is a valid inventory source file."""
        valid = False
        if super(InventoryModule, self).verify_file(path):
            if path.endswith((".yml", ".yaml")):
                valid = True
        return valid

    def _read_source(self, source):
        """Read Structurizr JSON from file or URL."""
        if source.startswith(("http://", "https://")):
            return self._fetch_url(source)
        else:
            return self._read_file(source)

    def _read_file(self, path):
        """Read JSON from local file."""
        if not os.path.isabs(path):
            # Make path relative to inventory file location
            base_dir = os.path.dirname(self._inventory_path or "")
            path = os.path.join(base_dir, path)

        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except IOError as e:
            raise AnsibleParserError(f"Unable to read Structurizr JSON file: {e}")
        except json.JSONDecodeError as e:
            raise AnsibleParserError(f"Invalid JSON in Structurizr file: {e}")

    def _fetch_url(self, url):
        """Fetch JSON from URL."""
        try:
            from ansible.module_utils.urls import open_url

            response = open_url(url)
            return json.loads(response.read().decode("utf-8"))
        except Exception as e:
            raise AnsibleParserError(f"Unable to fetch Structurizr JSON from URL: {e}")

    def _sanitize_group_name(self, name):
        """Convert a name to a valid Ansible group name."""
        # Replace spaces and special characters with underscores
        sanitized = re.sub(r"[^a-zA-Z0-9_]", "_", name)
        # Ensure it starts with a letter or underscore
        if sanitized and sanitized[0].isdigit():
            sanitized = "_" + sanitized
        return sanitized.lower()

    def _normalize_properties(self, node):
        """Normalize properties to a dict regardless of input format.

        Handles both formats:
        - List format: [{"name": "key", "value": "val"}, ...]
        - Dict format: {"key": "val", ...}
        """
        props = node.get("properties", {})
        if isinstance(props, list):
            return {p["name"]: p["value"] for p in props}
        elif isinstance(props, dict):
            return props
        return {}

    def _get_host_identifier(self, node):
        """Get the host identifier based on configuration."""
        host_id_option = self.get_option("host_identifier")

        if host_id_option == "id":
            return str(node.get("id", node.get("name")))
        elif host_id_option == "name":
            return node.get("name")
        else:
            # Look for property
            properties = self._normalize_properties(node)
            return properties.get(host_id_option, node.get("name"))

    def _extract_host_vars(self, node, environment=None, hierarchy=None):
        """Extract host variables from a Structurizr node."""
        host_vars = {}
        prefix = self.get_option("property_prefix")
        passthrough = self.get_option("ansible_property_passthrough") or []

        # Basic node properties
        host_vars["structurizr_id"] = node.get("id")
        host_vars["structurizr_name"] = node.get("name")

        if node.get("description"):
            host_vars["structurizr_description"] = node.get("description")

        if node.get("technology"):
            host_vars["technology"] = node.get("technology")

        if node.get("tags"):
            host_vars["structurizr_tags"] = [t.strip() for t in node.get("tags", "").split(",")]

        if environment:
            host_vars["structurizr_environment"] = environment

        if hierarchy:
            host_vars["structurizr_hierarchy"] = hierarchy

        # Extract custom properties (handles both list and dict formats)
        properties = self._normalize_properties(node)
        for prop_name, prop_value in properties.items():
            # Pass through ansible_* properties directly
            if prop_name.startswith("ansible_") or prop_name in passthrough:
                host_vars[prop_name] = prop_value
            else:
                # Apply prefix if configured
                var_name = f"{prefix}{prop_name}" if prefix else prop_name
                host_vars[var_name] = prop_value

        return host_vars

    def _add_host_to_inventory(
        self, node, environment=None, hierarchy=None, parent_groups=None
    ):
        """Add a single host to the inventory."""
        host_name = self._get_host_identifier(node)
        if not host_name:
            return

        # Add host to inventory
        self.inventory.add_host(host_name)
        self._hosts.append(host_name)

        # Add host variables
        host_vars = self._extract_host_vars(node, environment, hierarchy)
        for var_name, var_value in host_vars.items():
            self.inventory.set_variable(host_name, var_name, var_value)

        # Add to environment group
        if environment and self.get_option("group_by_environment"):
            env_group = self._sanitize_group_name(f"env_{environment}")
            self.inventory.add_group(env_group)
            self.inventory.add_child(env_group, host_name)

        # Add to tag groups
        if self.get_option("group_by_tags") and node.get("tags"):
            for tag in node.get("tags", "").split(","):
                tag = tag.strip()
                if tag and tag not in ("Element", "Deployment Node", "Infrastructure Node"):
                    tag_group = self._sanitize_group_name(f"tag_{tag}")
                    self.inventory.add_group(tag_group)
                    self.inventory.add_child(tag_group, host_name)

        # Add to technology group
        if self.get_option("group_by_technology") and node.get("technology"):
            tech_group = self._sanitize_group_name(f"tech_{node['technology']}")
            self.inventory.add_group(tech_group)
            self.inventory.add_child(tech_group, host_name)

        # Add to hierarchy groups
        if self.get_option("group_by_hierarchy") and parent_groups:
            for group in parent_groups:
                # Skip adding host to a group with the same name (Ansible disallows this)
                if group == host_name:
                    continue
                self.inventory.add_group(group)
                self.inventory.add_child(group, host_name)

        return host_name

    def _is_leaf_deployment_node(self, node):
        """Check if a deployment node is a leaf (has no child deployment nodes)."""
        return not node.get("children", [])

    def _process_deployment_node(
        self, node, environment=None, hierarchy=None, parent_groups=None
    ):
        """Recursively process a deployment node and its children."""
        if hierarchy is None:
            hierarchy = []
        if parent_groups is None:
            parent_groups = []

        node_name = node.get("name", "")
        current_hierarchy = hierarchy + [node_name]
        current_group = self._sanitize_group_name("_".join(current_hierarchy))

        # Create group for this level if it has children
        if node.get("children") and self.get_option("group_by_hierarchy"):
            self.inventory.add_group(current_group)
            # Add parent relationship
            if parent_groups:
                for parent_group in parent_groups:
                    # Skip self-referential groups
                    if parent_group == current_group:
                        continue
                    self.inventory.add_child(parent_group, current_group)

        new_parent_groups = parent_groups + [current_group] if current_group else parent_groups

        # Process child deployment nodes
        for child in node.get("children", []):
            self._process_deployment_node(
                child, environment, current_hierarchy, new_parent_groups
            )

        # Add leaf deployment nodes as hosts
        if self._is_leaf_deployment_node(node):
            self._add_host_to_inventory(
                node, environment, current_hierarchy, new_parent_groups
            )

        # Process infrastructure nodes
        if self.get_option("include_infrastructure_nodes"):
            for infra_node in node.get("infrastructureNodes", []):
                self._add_host_to_inventory(
                    infra_node, environment, current_hierarchy, new_parent_groups
                )

        # Process software system instances
        if self.get_option("include_software_system_instances"):
            for instance in node.get("softwareSystemInstances", []):
                self._add_host_to_inventory(
                    instance, environment, current_hierarchy, new_parent_groups
                )

        # Process container instances
        if self.get_option("include_container_instances"):
            for instance in node.get("containerInstances", []):
                self._add_host_to_inventory(
                    instance, environment, current_hierarchy, new_parent_groups
                )

    def _parse_workspace(self, workspace_data):
        """Parse the Structurizr workspace and populate inventory."""
        model = workspace_data.get("model", {})
        deployment_nodes = model.get("deploymentNodes", [])
        filter_environment = self.get_option("environment")

        for env_node in deployment_nodes:
            env_name = env_node.get("environment", env_node.get("name"))

            # Filter by environment if specified
            if filter_environment and env_name != filter_environment:
                continue

            # Process all deployment nodes in this environment
            for node in env_node.get("children", [env_node]):
                if node == env_node and not env_node.get("children"):
                    # Single-level deployment node
                    self._process_deployment_node(node, env_name)
                elif node != env_node:
                    self._process_deployment_node(node, env_name)

    def parse(self, inventory, loader, path, cache=True):
        """Parse the inventory source and populate inventory."""
        super(InventoryModule, self).parse(inventory, loader, path, cache)

        # Store path for relative file resolution
        self._inventory_path = path

        # Read configuration
        self._read_config_data(path)

        # Get source path
        source = self.get_option("source")
        if not source:
            raise AnsibleParserError("'source' option is required")

        # Check cache
        cache_key = self.get_cache_key(path)
        user_cache_setting = self.get_option("cache")
        attempt_to_read_cache = user_cache_setting and cache
        cache_needs_update = user_cache_setting and not cache

        if attempt_to_read_cache:
            try:
                cached_data = self._cache.get(cache_key)
                if cached_data:
                    self._parse_workspace(cached_data)
                    return
            except KeyError:
                cache_needs_update = True

        # Read and parse workspace data
        workspace_data = self._read_source(source)

        if cache_needs_update:
            self._cache[cache_key] = workspace_data

        # Parse workspace
        self._parse_workspace(workspace_data)

        # Apply constructed features (compose, groups, keyed_groups)
        strict = self.get_option("strict")
        for host in self._hosts:
            hostvars = self.inventory.get_host(host).get_vars()
            self._set_composite_vars(
                self.get_option("compose"), hostvars, host, strict=strict
            )
            self._add_host_to_composed_groups(
                self.get_option("groups"), hostvars, host, strict=strict
            )
            self._add_host_to_keyed_groups(
                self.get_option("keyed_groups"), hostvars, host, strict=strict
            )
