---
tool: ansible
category: configuration_management
version: "2.15"
topics:
  - playbooks
  - roles
  - tasks
---
# Ansible Playbooks

## Common Patterns

### Basic Playbook
```yaml
---
- name: Configure webserver
  hosts: webservers
  become: yes
  tasks:
    - name: Install nginx
      apt:
        name: nginx
        state: present
```

## Common Issues and Solutions

### Error: SSH Connection Failed
```error
Failed to connect to the host via ssh: Permission denied (publickey,password)
```

Solution:
1. Check SSH key:
```bash
ssh-add ~/.ssh/id_rsa
ansible-playbook playbook.yml -vvv
```

2. Configure SSH in ansible.cfg:
```ini
[defaults]
private_key_file = ~/.ssh/id_rsa
remote_user = ansible
```

### Error: Privilege Escalation Failed
```error
Failed to set permissions on the temporary files Ansible needs to create
```

Solution:
1. Configure sudo access:
```yaml
- hosts: all
  become: yes
  become_method: sudo
  become_user: root
```

2. Update sudoers file:
```bash
ansible ALL=(ALL) NOPASSWD: ALL
```

### Error: Module Not Found
```error
Could not find the required module
```

Solution:
1. Install collection:
```bash
ansible-galaxy collection install community.general
```

2. Add to requirements.yml:
```yaml
collections:
  - name: community.general
    version: 3.0.0
```
