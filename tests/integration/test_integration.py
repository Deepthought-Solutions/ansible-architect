# -*- coding: utf-8 -*-
# GNU General Public License v3.0+
# (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""
Integration tests for the Structurizr inventory plugin.

These tests verify that the plugin works correctly with Ansible's inventory system.
Run with: pytest tests/integration/test_integration.py -v
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import json
import os
import subprocess
import pytest

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(TESTS_DIR))


def run_ansible_inventory(inventory_file, *args):
    """Run ansible-inventory command and return parsed output."""
    cmd = [
        'ansible-inventory',
        '-i', inventory_file,
        '--list',
    ] + list(args)

    env = os.environ.copy()
    env['ANSIBLE_COLLECTIONS_PATH'] = os.path.dirname(PROJECT_ROOT)

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=TESTS_DIR,
        env=env,
    )

    if result.returncode != 0:
        pytest.fail(f"ansible-inventory failed: {result.stderr}")

    return json.loads(result.stdout)


@pytest.mark.integration
class TestInventoryIntegration:
    """Integration tests for the inventory plugin."""

    def test_basic_inventory(self):
        """Test basic inventory generation."""
        inventory_file = os.path.join(TESTS_DIR, 'test_inventory.yml')
        result = run_ansible_inventory(inventory_file)

        # Check that hosts are present
        assert 'web-prod-01' in result['_meta']['hostvars']
        assert 'web-prod-02' in result['_meta']['hostvars']
        assert 'db-prod-01' in result['_meta']['hostvars']
        assert 'web-staging-01' in result['_meta']['hostvars']

    def test_host_variables(self):
        """Test that host variables are correctly extracted."""
        inventory_file = os.path.join(TESTS_DIR, 'test_inventory.yml')
        result = run_ansible_inventory(inventory_file)

        hostvars = result['_meta']['hostvars']

        # Check web-prod-01 variables
        web_prod_01 = hostvars['web-prod-01']
        assert web_prod_01['ansible_host'] == '10.0.1.10'
        assert web_prod_01['ansible_user'] == 'ubuntu'
        assert web_prod_01['technology'] == 'Ubuntu 22.04'
        assert web_prod_01['structurizr_environment'] == 'Production'

    def test_environment_filter(self):
        """Test filtering by environment."""
        inventory_file = os.path.join(TESTS_DIR, 'test_inventory_production.yml')
        result = run_ansible_inventory(inventory_file)

        hostvars = result['_meta']['hostvars']

        # Production hosts should be present
        assert 'web-prod-01' in hostvars
        assert 'web-prod-02' in hostvars

        # Staging hosts should not be present
        assert 'web-staging-01' not in hostvars
        assert 'db-staging-01' not in hostvars

    def test_environment_groups(self):
        """Test that environment groups are created."""
        inventory_file = os.path.join(TESTS_DIR, 'test_inventory.yml')
        result = run_ansible_inventory(inventory_file)

        # Check environment groups exist
        assert 'env_production' in result
        assert 'env_staging' in result

        # Check hosts are in correct groups
        assert 'web-prod-01' in result['env_production']['hosts']
        assert 'web-staging-01' in result['env_staging']['hosts']

    def test_tag_groups(self):
        """Test that tag groups are created."""
        inventory_file = os.path.join(TESTS_DIR, 'test_inventory.yml')
        result = run_ansible_inventory(inventory_file)

        # Check tag groups exist
        assert 'tag_web' in result
        assert 'tag_database' in result

        # Check hosts are in correct tag groups
        assert 'web-prod-01' in result['tag_web']['hosts']
        assert 'db-prod-01' in result['tag_database']['hosts']

    def test_technology_groups(self):
        """Test that technology groups are created."""
        inventory_file = os.path.join(TESTS_DIR, 'test_inventory.yml')
        result = run_ansible_inventory(inventory_file)

        # Check technology groups exist
        assert 'tech_ubuntu_22_04' in result
        assert 'tech_postgresql_15' in result

    def test_infrastructure_nodes_included(self):
        """Test that infrastructure nodes are included."""
        inventory_file = os.path.join(TESTS_DIR, 'test_inventory.yml')
        result = run_ansible_inventory(inventory_file)

        # Check infrastructure node is present
        assert 'lb-prod-01' in result['_meta']['hostvars']

        # Check it has correct variables
        lb_vars = result['_meta']['hostvars']['lb-prod-01']
        assert lb_vars['technology'] == 'AWS ALB'
