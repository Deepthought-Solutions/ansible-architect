# -*- coding: utf-8 -*-
# GNU General Public License v3.0+
# (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import json
import os
import pytest
from unittest.mock import MagicMock, patch, mock_open

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../plugins'))

from inventory.structurizr import InventoryModule


@pytest.fixture
def sample_workspace():
    """Load sample workspace JSON."""
    fixtures_dir = os.path.join(os.path.dirname(__file__), '../fixtures')
    with open(os.path.join(fixtures_dir, 'sample_workspace.json'), 'r') as f:
        return json.load(f)


@pytest.fixture
def inventory_plugin():
    """Create an inventory plugin instance."""
    plugin = InventoryModule()
    plugin.inventory = MagicMock()
    plugin.inventory.get_host.return_value.get_vars.return_value = {}
    plugin._options = {}
    return plugin


@pytest.fixture
def mock_options():
    """Default plugin options."""
    return {
        'source': './workspace.json',
        'environment': None,
        'include_infrastructure_nodes': True,
        'include_software_system_instances': False,
        'include_container_instances': False,
        'group_by_environment': True,
        'group_by_tags': True,
        'group_by_technology': False,
        'group_by_hierarchy': True,
        'host_identifier': 'name',
        'property_prefix': '',
        'ansible_property_passthrough': [],
        'compose': {},
        'groups': {},
        'keyed_groups': [],
        'strict': False,
    }


class TestInventoryModule:
    """Tests for the Structurizr inventory plugin."""

    def test_verify_file_yaml(self, inventory_plugin):
        """Test that YAML files are accepted."""
        with patch('ansible.plugins.inventory.BaseInventoryPlugin.verify_file', return_value=True):
            assert inventory_plugin.verify_file('/path/to/inventory.yml') is True
            assert inventory_plugin.verify_file('/path/to/inventory.yaml') is True

    def test_verify_file_non_yaml(self, inventory_plugin):
        """Test that non-YAML files are rejected."""
        with patch('ansible.plugins.inventory.BaseInventoryPlugin.verify_file', return_value=True):
            assert inventory_plugin.verify_file('/path/to/inventory.json') is False
            assert inventory_plugin.verify_file('/path/to/inventory.txt') is False

    def test_sanitize_group_name(self, inventory_plugin):
        """Test group name sanitization."""
        assert inventory_plugin._sanitize_group_name('Production') == 'production'
        assert inventory_plugin._sanitize_group_name('EU-West') == 'eu_west'
        assert inventory_plugin._sanitize_group_name('US East 1') == 'us_east_1'
        assert inventory_plugin._sanitize_group_name('123-numeric') == '_123_numeric'
        assert inventory_plugin._sanitize_group_name('web@server#1') == 'web_server_1'

    def test_get_host_identifier_name(self, inventory_plugin, mock_options):
        """Test host identifier extraction by name."""
        mock_options['host_identifier'] = 'name'
        with patch.object(inventory_plugin, 'get_option', side_effect=lambda x: mock_options.get(x)):
            node = {'name': 'web-server-01', 'id': '123'}
            assert inventory_plugin._get_host_identifier(node) == 'web-server-01'

    def test_get_host_identifier_id(self, inventory_plugin, mock_options):
        """Test host identifier extraction by ID."""
        mock_options['host_identifier'] = 'id'
        with patch.object(inventory_plugin, 'get_option', side_effect=lambda x: mock_options.get(x)):
            node = {'name': 'web-server-01', 'id': '123'}
            assert inventory_plugin._get_host_identifier(node) == '123'

    def test_get_host_identifier_property(self, inventory_plugin, mock_options):
        """Test host identifier extraction from property."""
        mock_options['host_identifier'] = 'fqdn'
        with patch.object(inventory_plugin, 'get_option', side_effect=lambda x: mock_options.get(x)):
            node = {
                'name': 'web-server-01',
                'id': '123',
                'properties': [
                    {'name': 'fqdn', 'value': 'web-server-01.example.com'}
                ]
            }
            assert inventory_plugin._get_host_identifier(node) == 'web-server-01.example.com'

    def test_get_host_identifier_property_fallback(self, inventory_plugin, mock_options):
        """Test host identifier falls back to name if property not found."""
        mock_options['host_identifier'] = 'fqdn'
        with patch.object(inventory_plugin, 'get_option', side_effect=lambda x: mock_options.get(x)):
            node = {'name': 'web-server-01', 'id': '123', 'properties': []}
            assert inventory_plugin._get_host_identifier(node) == 'web-server-01'

    def test_extract_host_vars(self, inventory_plugin, mock_options):
        """Test host variable extraction."""
        with patch.object(inventory_plugin, 'get_option', side_effect=lambda x: mock_options.get(x)):
            node = {
                'id': '111',
                'name': 'web-prod-01',
                'description': 'Primary web server',
                'technology': 'Ubuntu 22.04',
                'tags': 'Element,Deployment Node,Web',
                'properties': [
                    {'name': 'ansible_host', 'value': '10.0.1.10'},
                    {'name': 'ansible_user', 'value': 'ubuntu'},
                    {'name': 'instance_type', 'value': 't3.large'}
                ]
            }
            host_vars = inventory_plugin._extract_host_vars(node, 'Production', ['EU-West'])

            assert host_vars['structurizr_id'] == '111'
            assert host_vars['structurizr_name'] == 'web-prod-01'
            assert host_vars['structurizr_description'] == 'Primary web server'
            assert host_vars['technology'] == 'Ubuntu 22.04'
            assert host_vars['structurizr_tags'] == ['Element', 'Deployment Node', 'Web']
            assert host_vars['ansible_host'] == '10.0.1.10'
            assert host_vars['ansible_user'] == 'ubuntu'
            assert host_vars['instance_type'] == 't3.large'
            assert host_vars['structurizr_environment'] == 'Production'
            assert host_vars['structurizr_hierarchy'] == ['EU-West']

    def test_extract_host_vars_with_prefix(self, inventory_plugin, mock_options):
        """Test host variable extraction with prefix."""
        mock_options['property_prefix'] = 'structurizr_'
        with patch.object(inventory_plugin, 'get_option', side_effect=lambda x: mock_options.get(x)):
            node = {
                'id': '111',
                'name': 'web-prod-01',
                'properties': [
                    {'name': 'ansible_host', 'value': '10.0.1.10'},
                    {'name': 'custom_var', 'value': 'custom_value'}
                ]
            }
            host_vars = inventory_plugin._extract_host_vars(node)

            # ansible_* should pass through without prefix
            assert host_vars['ansible_host'] == '10.0.1.10'
            # custom vars should get prefix
            assert host_vars['structurizr_custom_var'] == 'custom_value'

    def test_is_leaf_deployment_node(self, inventory_plugin):
        """Test leaf node detection."""
        leaf_node = {'name': 'server', 'children': []}
        parent_node = {'name': 'datacenter', 'children': [{'name': 'server'}]}

        assert inventory_plugin._is_leaf_deployment_node(leaf_node) is True
        assert inventory_plugin._is_leaf_deployment_node(parent_node) is False

    def test_parse_workspace_production_only(self, inventory_plugin, sample_workspace, mock_options):
        """Test parsing with environment filter."""
        mock_options['environment'] = 'Production'
        hosts_added = []
        groups_added = []

        def track_add_host(host):
            hosts_added.append(host)

        def track_add_group(group):
            groups_added.append(group)

        inventory_plugin.inventory.add_host = track_add_host
        inventory_plugin.inventory.add_group = track_add_group

        with patch.object(inventory_plugin, 'get_option', side_effect=lambda x: mock_options.get(x)):
            inventory_plugin._parse_workspace(sample_workspace)

        # Should have production hosts only
        assert 'web-prod-01' in hosts_added
        assert 'web-prod-02' in hosts_added
        assert 'db-prod-01' in hosts_added
        assert 'web-prod-03' in hosts_added
        assert 'lb-prod-01' in hosts_added  # infrastructure node
        # Should not have staging hosts
        assert 'web-staging-01' not in hosts_added
        assert 'db-staging-01' not in hosts_added

    def test_parse_workspace_all_environments(self, inventory_plugin, sample_workspace, mock_options):
        """Test parsing all environments."""
        mock_options['environment'] = None
        hosts_added = []

        def track_add_host(host):
            hosts_added.append(host)

        inventory_plugin.inventory.add_host = track_add_host
        inventory_plugin.inventory.add_group = MagicMock()

        with patch.object(inventory_plugin, 'get_option', side_effect=lambda x: mock_options.get(x)):
            inventory_plugin._parse_workspace(sample_workspace)

        # Should have all hosts
        assert 'web-prod-01' in hosts_added
        assert 'web-staging-01' in hosts_added
        assert 'db-staging-01' in hosts_added

    def test_parse_workspace_no_infrastructure_nodes(self, inventory_plugin, sample_workspace, mock_options):
        """Test parsing without infrastructure nodes."""
        mock_options['include_infrastructure_nodes'] = False
        mock_options['environment'] = 'Production'
        hosts_added = []

        def track_add_host(host):
            hosts_added.append(host)

        inventory_plugin.inventory.add_host = track_add_host
        inventory_plugin.inventory.add_group = MagicMock()

        with patch.object(inventory_plugin, 'get_option', side_effect=lambda x: mock_options.get(x)):
            inventory_plugin._parse_workspace(sample_workspace)

        # Should not have infrastructure nodes
        assert 'lb-prod-01' not in hosts_added
        # But should have deployment nodes
        assert 'web-prod-01' in hosts_added

    def test_environment_groups_created(self, inventory_plugin, sample_workspace, mock_options):
        """Test that environment groups are created."""
        mock_options['group_by_environment'] = True
        groups_with_children = {}

        def track_add_child(group, child):
            if group not in groups_with_children:
                groups_with_children[group] = []
            groups_with_children[group].append(child)

        inventory_plugin.inventory.add_host = MagicMock()
        inventory_plugin.inventory.add_group = MagicMock()
        inventory_plugin.inventory.add_child = track_add_child

        with patch.object(inventory_plugin, 'get_option', side_effect=lambda x: mock_options.get(x)):
            inventory_plugin._parse_workspace(sample_workspace)

        # Check environment groups were created with correct hosts
        assert 'env_production' in groups_with_children
        assert 'web-prod-01' in groups_with_children['env_production']
        assert 'env_staging' in groups_with_children
        assert 'web-staging-01' in groups_with_children['env_staging']

    def test_tag_groups_created(self, inventory_plugin, sample_workspace, mock_options):
        """Test that tag groups are created."""
        mock_options['group_by_tags'] = True
        mock_options['environment'] = 'Production'
        groups_with_children = {}

        def track_add_child(group, child):
            if group not in groups_with_children:
                groups_with_children[group] = []
            groups_with_children[group].append(child)

        inventory_plugin.inventory.add_host = MagicMock()
        inventory_plugin.inventory.add_group = MagicMock()
        inventory_plugin.inventory.add_child = track_add_child

        with patch.object(inventory_plugin, 'get_option', side_effect=lambda x: mock_options.get(x)):
            inventory_plugin._parse_workspace(sample_workspace)

        # Check tag groups were created
        assert 'tag_web' in groups_with_children
        assert 'web-prod-01' in groups_with_children['tag_web']
        assert 'tag_database' in groups_with_children
        assert 'db-prod-01' in groups_with_children['tag_database']


class TestReadSource:
    """Tests for source reading functionality."""

    def test_read_file(self, inventory_plugin):
        """Test reading from local file."""
        test_data = {'model': {'deploymentNodes': []}}
        with patch('builtins.open', mock_open(read_data=json.dumps(test_data))):
            result = inventory_plugin._read_file('/path/to/workspace.json')
            assert result == test_data

    def test_read_file_not_found(self, inventory_plugin):
        """Test error when file not found."""
        from ansible.errors import AnsibleParserError
        with patch('builtins.open', side_effect=IOError("File not found")):
            with pytest.raises(AnsibleParserError):
                inventory_plugin._read_file('/nonexistent/workspace.json')

    def test_read_file_invalid_json(self, inventory_plugin):
        """Test error when JSON is invalid."""
        from ansible.errors import AnsibleParserError
        with patch('builtins.open', mock_open(read_data='not valid json {')):
            with pytest.raises(AnsibleParserError):
                inventory_plugin._read_file('/path/to/workspace.json')

    def test_read_source_detects_url(self, inventory_plugin):
        """Test that URLs are detected correctly."""
        with patch.object(inventory_plugin, '_fetch_url') as mock_fetch:
            mock_fetch.return_value = {'model': {}}
            inventory_plugin._read_source('https://example.com/workspace.json')
            mock_fetch.assert_called_once_with('https://example.com/workspace.json')

    def test_read_source_detects_file(self, inventory_plugin):
        """Test that file paths are detected correctly."""
        with patch.object(inventory_plugin, '_read_file') as mock_read:
            mock_read.return_value = {'model': {}}
            inventory_plugin._read_source('/path/to/workspace.json')
            mock_read.assert_called_once_with('/path/to/workspace.json')


class TestNormalizeProperties:
    """Tests for property normalization (list vs dict format)."""

    def test_normalize_properties_list_format(self, inventory_plugin):
        """Test normalization of list-format properties."""
        node = {
            'name': 'test-node',
            'properties': [
                {'name': 'ansible_host', 'value': '10.0.0.1'},
                {'name': 'custom_var', 'value': 'custom_value'}
            ]
        }
        result = inventory_plugin._normalize_properties(node)
        assert result == {'ansible_host': '10.0.0.1', 'custom_var': 'custom_value'}

    def test_normalize_properties_dict_format(self, inventory_plugin):
        """Test normalization of dict-format properties (Structurizr CLI export)."""
        node = {
            'name': 'test-node',
            'properties': {
                'ansible_host': '10.0.0.1',
                'custom_var': 'custom_value'
            }
        }
        result = inventory_plugin._normalize_properties(node)
        assert result == {'ansible_host': '10.0.0.1', 'custom_var': 'custom_value'}

    def test_normalize_properties_empty(self, inventory_plugin):
        """Test normalization with no properties."""
        node = {'name': 'test-node'}
        result = inventory_plugin._normalize_properties(node)
        assert result == {}

    def test_normalize_properties_empty_list(self, inventory_plugin):
        """Test normalization with empty list."""
        node = {'name': 'test-node', 'properties': []}
        result = inventory_plugin._normalize_properties(node)
        assert result == {}

    def test_normalize_properties_empty_dict(self, inventory_plugin):
        """Test normalization with empty dict."""
        node = {'name': 'test-node', 'properties': {}}
        result = inventory_plugin._normalize_properties(node)
        assert result == {}


class TestForceHostProperty:
    """Tests for ansible_force_host property functionality."""

    def test_force_host_with_children(self, inventory_plugin, mock_options):
        """Test that ansible_force_host=true makes parent node a host."""
        hosts_added = []

        def track_add_host(host):
            hosts_added.append(host)

        inventory_plugin.inventory.add_host = track_add_host
        inventory_plugin.inventory.add_group = MagicMock()
        inventory_plugin.inventory.add_child = MagicMock()

        # Parent node with children and ansible_force_host=true
        workspace = {
            'model': {
                'deploymentNodes': [{
                    'id': '1',
                    'name': 'hypervisor-01',
                    'environment': 'Production',
                    'properties': {
                        'ansible_force_host': 'true',
                        'ansible_host': '192.168.1.10'
                    },
                    'children': [{
                        'id': '2',
                        'name': 'vm-01',
                        'properties': {
                            'ansible_host': '10.0.0.1'
                        }
                    }]
                }]
            }
        }

        with patch.object(inventory_plugin, 'get_option', side_effect=lambda x: mock_options.get(x)):
            inventory_plugin._parse_workspace(workspace)

        # Both parent (forced) and child (leaf) should be hosts
        assert 'hypervisor-01' in hosts_added
        assert 'vm-01' in hosts_added

    def test_force_host_false_with_children(self, inventory_plugin, mock_options):
        """Test that parent without force_host is not a host."""
        hosts_added = []

        def track_add_host(host):
            hosts_added.append(host)

        inventory_plugin.inventory.add_host = track_add_host
        inventory_plugin.inventory.add_group = MagicMock()
        inventory_plugin.inventory.add_child = MagicMock()

        # Parent node with children but no ansible_force_host
        workspace = {
            'model': {
                'deploymentNodes': [{
                    'id': '1',
                    'name': 'datacenter',
                    'environment': 'Production',
                    'children': [{
                        'id': '2',
                        'name': 'server-01',
                        'properties': {'ansible_host': '10.0.0.1'}
                    }]
                }]
            }
        }

        with patch.object(inventory_plugin, 'get_option', side_effect=lambda x: mock_options.get(x)):
            inventory_plugin._parse_workspace(workspace)

        # Only child should be a host
        assert 'datacenter' not in hosts_added
        assert 'server-01' in hosts_added

    def test_force_host_case_insensitive(self, inventory_plugin, mock_options):
        """Test that ansible_force_host is case-insensitive."""
        hosts_added = []

        def track_add_host(host):
            hosts_added.append(host)

        inventory_plugin.inventory.add_host = track_add_host
        inventory_plugin.inventory.add_group = MagicMock()
        inventory_plugin.inventory.add_child = MagicMock()

        workspace = {
            'model': {
                'deploymentNodes': [{
                    'id': '1',
                    'name': 'hypervisor-01',
                    'environment': 'Production',
                    'properties': {'ansible_force_host': 'TRUE'},  # uppercase
                    'children': [{'id': '2', 'name': 'vm-01'}]
                }]
            }
        }

        with patch.object(inventory_plugin, 'get_option', side_effect=lambda x: mock_options.get(x)):
            inventory_plugin._parse_workspace(workspace)

        assert 'hypervisor-01' in hosts_added


class TestSelfReferentialGroupPrevention:
    """Tests for preventing self-referential group issues."""

    def test_host_not_added_to_same_name_group(self, inventory_plugin, mock_options):
        """Test that a host is not added to a group with the same name."""
        add_child_calls = []

        def track_add_child(group, child):
            add_child_calls.append((group, child))

        inventory_plugin.inventory.add_host = MagicMock()
        inventory_plugin.inventory.add_group = MagicMock()
        inventory_plugin.inventory.add_child = track_add_child
        inventory_plugin.inventory.set_variable = MagicMock()

        # Single leaf node that would create a group with same name
        workspace = {
            'model': {
                'deploymentNodes': [{
                    'id': '1',
                    'name': 'mainwork',
                    'environment': 'Production',
                    'properties': {}
                }]
            }
        }

        with patch.object(inventory_plugin, 'get_option', side_effect=lambda x: mock_options.get(x)):
            inventory_plugin._parse_workspace(workspace)

        # Should not have any self-referential calls
        for group, child in add_child_calls:
            assert group != child, f"Self-referential: {group} -> {child}"
