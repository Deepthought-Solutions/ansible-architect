# Structurizr Inventory Collection

An Ansible collection that generates dynamic inventory from Structurizr architecture models.

## Description

This collection provides an inventory plugin that transforms Structurizr DSL/JSON exports into Ansible inventory. It bridges the gap between "Architecture as Code" (C4 Model) and "Infrastructure as Code" (Ansible).

## Requirements

- Ansible >= 2.9
- Python >= 3.8
- Structurizr CLI (for exporting workspace to JSON)

## Installation

```bash
ansible-galaxy collection install deepthought_solutions.structurizr_inventory
```

Or from source:

```bash
cd ansible-structurizr-inventory
ansible-galaxy collection build
ansible-galaxy collection install deepthought_solutions-structurizr_inventory-0.1.0.tar.gz
```

## Usage

### 1. Export your Structurizr workspace to JSON

```bash
structurizr-cli export -workspace workspace.dsl -format json -output workspace.json
```

### 2. Create an inventory configuration file

```yaml
# inventory.yml
plugin: deepthought_solutions.structurizr_inventory.structurizr
source: ./workspace.json

# Optional: Filter by environment
environment: Production

# Grouping options
group_by_environment: true
group_by_tags: true
group_by_technology: true
group_by_hierarchy: true
```

### 3. Use with Ansible

```bash
ansible-inventory -i inventory.yml --list
ansible-playbook -i inventory.yml site.yml
```

## Plugin Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `source` | string | (required) | Path to Structurizr JSON file or URL |
| `environment` | string | null | Filter by environment name |
| `include_infrastructure_nodes` | bool | true | Include infrastructure nodes as hosts |
| `include_software_system_instances` | bool | false | Include software system instances |
| `include_container_instances` | bool | false | Include container instances |
| `group_by_environment` | bool | true | Create groups by environment |
| `group_by_tags` | bool | true | Create groups by tags |
| `group_by_technology` | bool | false | Create groups by technology |
| `group_by_hierarchy` | bool | true | Create nested hierarchy groups |
| `host_identifier` | string | "name" | Property to use as host name (name, id, or property) |
| `property_prefix` | string | "" | Prefix for Structurizr properties |
| `ansible_property_passthrough` | list | [] | Additional properties to pass through |

## Structurizr DSL Example

```dsl
workspace {
    model {
        deploymentEnvironment "Production" {
            deploymentNode "EU-West" {
                technology "AWS"

                deploymentNode "web-prod-01" {
                    technology "Ubuntu 22.04"
                    properties {
                        "ansible_host" "10.0.1.10"
                        "ansible_user" "ubuntu"
                        "fqdn" "web-prod-01.example.com"
                    }
                }

                infrastructureNode "lb-prod-01" {
                    technology "AWS ALB"
                    properties {
                        "ansible_host" "lb.example.com"
                    }
                }
            }
        }
    }
}
```

## Generated Inventory Structure

The plugin generates:

- **Hosts**: Leaf deployment nodes and infrastructure nodes become Ansible hosts
- **Groups**:
  - `env_<environment>`: Hosts grouped by deployment environment
  - `tag_<tag>`: Hosts grouped by Structurizr tags
  - `tech_<technology>`: Hosts grouped by technology
  - Hierarchy groups based on deployment node structure

## Host Variables

The plugin automatically maps:

- `ansible_*` properties directly as Ansible connection variables
- Structurizr metadata (`structurizr_id`, `structurizr_name`, `structurizr_description`)
- `technology` property
- `tags` as a list
- All custom properties from the Structurizr model

## Security Best Practices

**Never store secrets in Structurizr!**

Use Structurizr for non-sensitive data only:
- Host names and IPs
- User names
- Port numbers
- Instance types

Store secrets in:
- Ansible Vault (`host_vars/`)
- HashiCorp Vault
- AWS Secrets Manager

## Development

### Running Tests

```bash
# Unit tests
pytest tests/unit/ -v

# Integration tests
pytest tests/integration/ -v -m integration
```

### Building the Collection

```bash
ansible-galaxy collection build
```

## License

GPL-3.0-or-later

## Author

Nicolas Karageuzian (@nkarageuzian)
