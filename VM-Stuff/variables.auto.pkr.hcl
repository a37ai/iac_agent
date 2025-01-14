# Shared variables for the Linux DevOps base image
# (Much like your Windows file, but adapted for Linux.)
 
# ----------------------------------------------------------------------------
# Basic Parameters
# ----------------------------------------------------------------------------
variable "ami_name_prefix" {
  type    = string
  default = "linux-devops-base"
}

variable "environment_tag" {
  type    = string
  default = "Build"
}

# For Linux, a typical place for temp is /tmp, but you can keep or remove if you like
variable "temp_path" {
  type    = string
  default = "/tmp"
}

# SSH username for Amazon Linux 2 is typically "ec2-user".
variable "ssh_username" {
  type    = string
  default = "ec2-user"
}

# ----------------------------------------------------------------------------
# AWS Settings
# ----------------------------------------------------------------------------
variable "aws_region" {
  type    = string
  default = "us-east-1"
}

# Example Amazon Linux 2 AMI in us-east-1:
variable "source_ami" {
  type    = string
  default = "ami-0454e52560c7f5c55"
}

variable "instance_type" {
  type    = string
  default = "t3.large"
}

# ----------------------------------------------------------------------------
# Tool Versions (Pinnable)
# ----------------------------------------------------------------------------
variable "terraform_version" {
  type    = string
  default = "1.5.5"
}

variable "helm_version" {
  type    = string
  default = "v3.12.3"
}

variable "chef_workstation_version" {
  type    = string
  default = "23.6.1031"
}

variable "puppet_agent_version" {
  type    = string
  default = "latest"
}

variable "jenkins_version" {
  type    = string
  default = "2.401.3"
}

# Python version doesn’t matter as much on Linux if we’re installing from yum/apt
# but we’ll keep it for consistency
variable "python_version" {
  type    = string
  default = "3.11.5"
}

variable "aws_cli_version" {
  type    = string
  default = "2.11.26"
}

variable "prometheus_version" {
  type    = string
  default = "2.45.0"
}

variable "vault_version" {
  type    = string
  default = "1.14.2"
}
